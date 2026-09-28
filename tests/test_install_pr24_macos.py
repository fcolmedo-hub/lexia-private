import importlib.util
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/install_pr24_macos.py'
spec = importlib.util.spec_from_file_location('install_mac', SCRIPT)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class MacInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        self.root.mkdir()
        self.backups = Path(self.temp.name) / 'backups'
        self.backups.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Installer test')
        self.write('services/sample.py', b'a = 1\nb = 1\nc = 1\n')
        self.write('app/ui2/index.html', b'local index')
        self.write('runtime/catalog.sqlite3', b'catalog sentinel')
        self.git('add', '.')
        self.git('commit', '-qm', 'base')
        self.base = self.git('rev-parse', 'HEAD').decode().strip()
        self.write('services/sample.py', b'a = 2\nb = 1\nc = 1\n')
        self.write('services/new.py', b'value = 1\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'target')
        self.target = self.git('rev-parse', 'HEAD').decode().strip()
        files = []
        for name, status in [('services/sample.py', 'modified'), ('services/new.py', 'added')]:
            sha = self.git('rev-parse', f'HEAD:{name}').decode().strip()
            files.append((name, status, sha))
        self.git('checkout', '-q', self.base)
        for key, value in [('BASE', self.base), ('TARGET', self.target), ('FILES', files)]:
            p = patch.object(installer, key, value)
            p.start()
            self.addCleanup(p.stop)

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, stderr=subprocess.PIPE)

    def write(self, name, data):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def test_merge_backup_repeat_and_protected_files(self):
        original = b'a = 1\nb = 1\nc = 7\n'
        self.write('services/sample.py', original)
        (self.root / 'services/sample.py').chmod(0o755)
        planned = installer.plan(self.root)
        self.assertEqual((self.root / 'services/sample.py').read_bytes(), original)
        backup = installer.install(self.root, planned, self.backups)
        self.assertEqual((backup / 'services/sample.py').read_bytes(), original)
        self.assertEqual((self.root / 'services/sample.py').read_bytes(), b'a = 2\nb = 1\nc = 7\n')
        self.assertEqual((self.root / 'services/sample.py').stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.root / 'app/ui2/index.html').read_bytes(), b'local index')
        self.assertEqual((self.root / 'runtime/catalog.sqlite3').read_bytes(), b'catalog sentinel')
        self.assertEqual(installer.plan(self.root), {})

    def test_conflict_has_no_partial_writes(self):
        self.write('services/sample.py', b'a = 9\nb = 1\nc = 1\n')
        with self.assertRaisesRegex(ValueError, 'Conflictos'):
            installer.plan(self.root)
        self.assertFalse((self.root / 'services/new.py').exists())

    def test_missing_file_and_added_collision(self):
        (self.root / 'services/sample.py').unlink()
        self.write('services/new.py', b'personal = 9\n')
        with self.assertRaises(ValueError) as error:
            installer.plan(self.root)
        self.assertIn('Falta el archivo local', str(error.exception))
        self.assertIn('Ya existe con otro contenido', str(error.exception))

    def test_symlinks_and_changed_after_preflight(self):
        planned = installer.plan(self.root)
        self.write('services/sample.py', b'changed = True\n')
        with self.assertRaisesRegex(ValueError, 'cambió'):
            installer.install(self.root, planned, self.backups)
        (self.root / 'services/sample.py').unlink()
        (self.root / 'services/sample.py').symlink_to(self.root / 'app/ui2/index.html')
        with self.assertRaisesRegex(ValueError, 'simbólicos'):
            installer.plan(self.root)

    def test_write_failure_restores_files(self):
        planned = installer.plan(self.root)
        real = installer.atomic_write
        calls = 0
        def fail_second(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('simulated disk failure')
            return real(*args)
        with patch.object(installer, 'atomic_write', fail_second):
            with self.assertRaises(OSError):
                installer.install(self.root, planned, self.backups)
        self.assertEqual((self.root / 'services/sample.py').read_bytes(), b'a = 1\nb = 1\nc = 1\n')
        self.assertFalse((self.root / 'services/new.py').exists())

    def test_reviewed_hash_only_accepts_exact_snapshot(self):
        known = b'a = 7\nb = 1\nc = 1\n'
        self.write('services/sample.py', known)
        with patch.object(installer, 'REVIEWED_LOCAL_SHA256', {
            'services/sample.py': hashlib.sha256(known).hexdigest()
        }):
            self.assertEqual(installer.plan(self.root)['services/sample.py']['after'], b'a = 2\nb = 1\nc = 1\n')
            self.write('services/sample.py', b'a = 8\nb = 1\nc = 1\n')
            with self.assertRaises(ValueError):
                installer.plan(self.root)


if __name__ == '__main__':
    unittest.main()

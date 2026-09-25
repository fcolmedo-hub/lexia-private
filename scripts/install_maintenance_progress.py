#!/usr/bin/env python3
"""Apply the reviewed Maintenance update to this checkout, with a local backup."""
import datetime
from pathlib import Path
import subprocess
import sys
import tarfile

BASE = '0c79d67ad058cc61e0ac38d3984d4f1e29ff379c'
FILES = [
    'app/ui2/assets/maintenance.css',
    'app/ui2/assets/maintenance.js',
    'app/ui2/assets/windows_maintenance_status_detail.js',
    'app/ui2/navigator_3_3_4a.js',
    'core/document_detector.py',
    'services/autosync_service.py',
    'services/library_snapshot_service.py',
]


def git(*args, data=None):
    return subprocess.run(['git', *args], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main():
    root = git('rev-parse', '--show-toplevel')
    if root.returncode:
        raise SystemExit('Abrí la terminal dentro de la carpeta LexIA_2.3_DEV.')
    import os
    os.chdir(root.stdout.decode().strip())
    target = git('rev-parse', '--verify', sys.argv[1] if len(sys.argv) > 1 else 'FETCH_HEAD')
    if target.returncode:
        raise SystemExit('Primero ejecutá git fetch origin fix/autosync-progress.')
    revision = target.stdout.decode().strip()
    marker = git('show', revision + ':docs/maintenance-review-2026-09.md')
    if marker.returncode:
        raise SystemExit('La revisión descargada no corresponde a esta actualización.')
    diff = git('diff', '--binary', BASE, revision, '--', *FILES)
    if diff.returncode or not diff.stdout:
        raise SystemExit('No se pudo preparar el parche. No se modificó ningún archivo.')
    patch = diff.stdout
    reverse = git('apply', '--reverse', '--check', '-', data=patch)
    if not reverse.returncode:
        print('La actualización ya está instalada. Cerrá LexIA por completo y volvé a abrirla.')
        return
    check = git('apply', '--check', '-', data=patch)
    if check.returncode:
        print(check.stderr.decode(errors='replace'))
        raise SystemExit('Hay diferencias locales. No se modificó ningún archivo. Enviá este resultado para adaptar la actualización.')
    desktop = Path.home() / 'Desktop'
    parent = desktop if desktop.is_dir() else Path.home()
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = parent / ('lexia-mantenimiento-' + stamp)
    backup.mkdir()
    (backup / 'actualizacion.patch').write_bytes(patch)
    with tarfile.open(backup / 'archivos-anteriores.tar.gz', 'w:gz') as archive:
        for name in FILES:
            if Path(name).is_file():
                archive.add(name, arcname=name)
    applied = git('apply', '-', data=patch)
    if applied.returncode:
        print(applied.stderr.decode(errors='replace'))
        raise SystemExit('No se pudo aplicar la actualización. Respaldo: ' + str(backup))
    (backup / 'revision.txt').write_text(revision + '\n', encoding='utf-8')
    print('Actualización instalada. Respaldo: ' + str(backup))
    print('Cerrá LexIA por completo y volvé a abrirla para reiniciar también AutoSync.')


if __name__ == '__main__':
    main()

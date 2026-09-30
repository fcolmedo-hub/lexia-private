#!/usr/bin/env python3
"""Permite preparar selecciones OCR mientras se elimina otra tanda."""
import argparse
from datetime import datetime
import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

FILE = 'app/ui2/assets/maintenance.js'
TARGET_SHA256 = '99674108df21cb2442a6a39aa7f0f9ad417c88a87726b4b18631a2df28f10bf7'
KNOWN = {
    'f5d6bdc5b5acc2ab7c887cf5541ca834f3f78a18120e6e9d51a66afdb89218c6',
    '0504ef6edd5299159bf22670d9e2a094bf0e6800698adb741698213ce7388b98',
    'cebb05b5741e2b95732f732e23092c0c82e69a38c7de6c149443be03899d97b1',
}


def git(*args):
    result = subprocess.run(['git', *args], capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace').strip())
    return result.stdout


def normal(data):
    return data.decode('utf-8-sig').replace('\r\n', '\n')


def sha(data):
    return hashlib.sha256(normal(data).encode('utf-8')).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--source', default='FETCH_HEAD')
    args = parser.parse_args()
    root = Path(git('rev-parse', '--show-toplevel').decode().strip()).resolve()
    path = root
    for part in Path(FILE).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('La ruta contiene un enlace simbólico. No se modificó LexIA.')
    current = path.read_bytes()
    target = git('show', f'{args.source}:{FILE}')
    if sha(target) != TARGET_SHA256:
        raise ValueError('La revisión descargada no coincide con este instalador. No se modificó LexIA.')
    if sha(current) == TARGET_SHA256:
        print('La selección durante la eliminación ya está instalada.')
        return
    if sha(current) not in KNOWN:
        raise ValueError('maintenance.js tiene otros cambios locales. Enviá ese archivo para adaptar la actualización. No se modificó LexIA.')
    print('Comprobación correcta: 1 archivo por actualizar. Catálogo e index.html se conservan.')
    if args.check:
        return
    text = normal(target)
    if current.count(b'\r\n') > current.count(b'\n') - current.count(b'\r\n'):
        text = text.replace('\n', '\r\n')
    data = (('\ufeff' if current.startswith(b'\xef\xbb\xbf') else '') + text).encode('utf-8')
    desktop = Path.home() / 'Desktop'
    backup_root = desktop if desktop.is_dir() else Path.home()
    backup = backup_root / ('lexia-ocr-respaldo-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir()
    shutil.copy2(path, backup / 'maintenance.js')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.lexia-ocr-', delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        temporary.chmod(stat.S_IMODE(path.stat().st_mode))
        if path.read_bytes() != current:
            raise ValueError('El archivo cambió durante la instalación. No se reemplazó.')
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f'Instalación terminada. Respaldo: {backup}')
    print('Cerrá LexIA completamente y volvé a abrirla.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from error

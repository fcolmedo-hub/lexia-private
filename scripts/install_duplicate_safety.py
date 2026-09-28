#!/usr/bin/env python3
"""Instala la protección de duplicados y reparación de ubicaciones; no modifica datos."""
import argparse
import ast
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
TARGET = 'FETCH_HEAD'
FILES = {'core/pipeline.py': {'target': '6aefd58a4d51dc4819ddeb856d3c1e93dccc462c71c2c30c8c6469fba96b6e02',
                      'known': ['5c26368ec9667bab1392c066fe47d64b65506fa6cd94aea5647bdc914551e922']},
 'storage/catalog.py': {'target': '1dd4391bfe575c04d72e61f5acd4d138c59298ff3b301af931fc2cb3e9130eb5',
                        'known': ['526243f11c9d9f0a4ab1c1f29de54a2e492186bab82dda6e9d533316b6b3e030']},
 'services/secure_document_deletion.py': {'target': '8c371d8fcd0adcfbcf55ed507985482ea98ec1edf48cff3c4cb64dbc282d8753',
                                          'known': ['3abae644f8121a0c68360473f0dc53b151c51325dfaa181ca019cf049f47a5ff',
                                                    'ec6e6c3ff9b74be7f22049a2bfa6c70698e9927a360cf1355a9afb513a561048']},
 'services/windows_research_manual_sources.py': {'target': '13c4986e0d09ed1c258c24096bb1fa29b240e6aa7eb7586237e62d93c0136bc2',
                                                 'known': ['b5476c16a2ebacd6e4b1f9e32a42f28b301e3b8acece2032d3e442a7938cefe4',
                                                           'faeb6d015641078151dfb9de04c78467cae545ae67540e8f2fd951e1480780dd']},
 'app/ui2/assets/windows_maintenance_duplicates.js': {'target': '75fe1fde158e04da456a08207050a188748e36b7ce2244c7910e490d1e640560',
                                                      'known': ['4bc7b56bd7a0cc40f8168a483298e799a20ba06b86441ad63f972396b43f6a3f',
                                                                '86bb838204965dc9540812036bfcf429a5cde1e43c6805c07cc56cc1f187a342',
                                                                'bf8e8f46b503edad24457ba21755cd116ca8b3ea86df62493dd1aebdb4a2f7bc']},
 'services/duplicate_file_safety.py': {'target': '782afc5f495b59cf75af29c7e8c79f79b409dd70eb935da6f50777410cfc11ca',
                                       'known': []},
 'services/moved_duplicate_reconciliation.py': {'target': '089f23a9963e55e6e937d87d9a8c6989e8ac83608d83bc163c39147a70755ae2',
                                                'known': []}}

def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Falló git {' '.join(args)} (código {result.returncode}). {detail}".strip())
    return result.stdout

def decode(data: bytes) -> tuple[str, bool, bool]:
    bom = data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8-sig" if bom else "utf-8")
    crlf = text.count("\r\n") > text.count("\n") - text.count("\r\n")
    return text.replace("\r\n", "\n"), bom, crlf

def encode(text: str, bom: bool, crlf: bool) -> bytes:
    return (("\ufeff" if bom else "") + (text.replace("\n", "\r\n") if crlf else text)).encode("utf-8")

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def safe_path(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or relative.parts[0] not in {
        'app', 'core', 'docs', 'prompt', 'scripts', 'services', 'standards',
        'storage', 'tests', 'tools', 'requirements.txt',
    } or name == 'app/ui2/index.html':
        raise ValueError(f'Ruta no permitida: {name}')
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f'No se modifican enlaces simbólicos: {name}')
    if current.exists() and not current.is_file():
        raise ValueError(f'La ruta no es un archivo: {name}')
    return current

def atomic_write(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.lexia-update-', delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

def verify_unchanged(root: Path, planned: dict) -> None:
    for name, item in planned.items():
        path = safe_path(root, name)
        current = path.read_bytes() if path.exists() else None
        if current != item['before']:
            raise ValueError(f'{name} cambió durante la comprobación. Volvé a ejecutar el instalador.')

def install(root: Path, planned: dict, backup_parent: Path | None = None) -> Path:
    verify_unchanged(root, planned)
    if backup_parent is None:
        desktop = Path.home() / 'Desktop'
        backup_parent = desktop if desktop.is_dir() else Path.home()
    backup = backup_parent / ('lexia-duplicados-respaldo-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True)
    manifest = {'target': TARGET, 'files': {}}
    for name, item in planned.items():
        if item['before'] is not None:
            destination = backup / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(item['before'])
            destination.chmod(item['mode'])
        manifest['files'][name] = {
            'new': item['before'] is None, 'mode': item['mode'],
            'before_sha256': digest(item['before']) if item['before'] is not None else None,
            'after_sha256': digest(item['after']),
        }
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    verify_unchanged(root, planned)
    written = []
    try:
        for name, item in planned.items():
            atomic_write(safe_path(root, name), item['after'], item['mode'])
            written.append(name)
    except BaseException:
        errors = []
        for name in reversed(written):
            try:
                item = planned[name]
                if item['before'] is None:
                    (root / name).unlink(missing_ok=True)
                else:
                    atomic_write(root / name, item['before'], item['mode'])
            except OSError as error:
                errors.append(f'{name}: {error}')
        if errors:
            raise RuntimeError(f'Restauración incompleta. Respaldo: {backup}\n' + '\n'.join(errors))
        raise
    return backup

def plan(root: Path) -> dict:
    planned, errors = {}, []
    for name, specification in FILES.items():
        try:
            path = safe_path(root, name)
            target = git(root, 'show', f'{TARGET}:{name}')
            target_text, _, _ = decode(target)
            if digest(target_text.encode('utf-8')) != specification['target']:
                raise ValueError('La versión de origen no coincide con este instalador')
            before = path.read_bytes() if path.exists() else None
            mode = stat.S_IMODE(path.stat().st_mode) if before is not None else 0o644
            if before is not None:
                local_text, bom, crlf = decode(before)
                current_hash = digest(local_text.encode('utf-8'))
                if current_hash == specification['target']:
                    continue
                if current_hash not in specification['known']:
                    raise ValueError('Hay cambios locales no reconocidos; se conservaron')
                after = encode(target_text, bom, crlf)
            else:
                if specification['known']:
                    raise ValueError('Falta un archivo necesario de la instalación')
                after = target
            if name.endswith('.py'):
                ast.parse(decode(after)[0], filename=name)
            planned[name] = {'before': before, 'after': after, 'mode': mode}
        except (OSError, ValueError, RuntimeError, SyntaxError) as error:
            errors.append(f'- {name}: {error}')
    if errors:
        raise ValueError('Conflictos detectados:\n' + '\n'.join(errors))
    return planned

def main() -> int:
    global TARGET
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='FETCH_HEAD')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        root = Path(git(Path.cwd(), 'rev-parse', '--show-toplevel').decode().strip())
        TARGET = git(root, 'rev-parse', '--verify', args.source + '^{commit}').decode().strip()
        planned = plan(root)
    except (OSError, ValueError, RuntimeError) as error:
        print(f'{error}\nNo se modificó LexIA.', file=sys.stderr)
        return 1
    print(f'Comprobación correcta: {len(planned)} archivo(s) por instalar. No se modifica el catálogo ni runtime.')
    if args.check or not planned:
        return 0
    try:
        backup = install(root, planned)
    except (OSError, ValueError, RuntimeError) as error:
        print(f'No se completó la instalación: {error}', file=sys.stderr)
        return 1
    print(f'Instalación terminada. Respaldo: {backup}')
    print('Cerrá LexIA completamente y volvé a abrirla. No hace falta reconstruir la aplicación.')
    print('En Duplicados, usá Corregir ubicación para reparar un archivo trasladado. No lo elimines.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

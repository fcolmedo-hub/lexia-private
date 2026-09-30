#!/usr/bin/env python3
"""Evita recorridos completos de Inicio en Windows; conserva otros cambios."""
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
FILES = {'app/ui2/assets/app_runtime.js': {'target': '963f413a353d8bbfc2b318334dfff3d75720c115d785d304a593208b05fd7cb2',
                                   'old': '  function '
                                          'removeLiveSearchBadge(){\n'
                                          '    const '
                                          "normalize=value=>String(value||'').replace(/\\s+/g,' "
                                          "').trim().toLowerCase();\n"
                                          '    const '
                                          "nodes=[...document.querySelectorAll('div,aside,section')];\n"
                                          '    for(const node of nodes){\n'
                                          '      const '
                                          'text=normalize(node.textContent);\n'
                                          '      '
                                          "if(!text.includes('live')||!text.includes('búsqueda "
                                          "real'))continue;\n"
                                          '      if(text.length>240)continue;\n'
                                          '\n'
                                          '      let candidate=node;\n'
                                          '      for(let '
                                          'depth=0;depth<5&&candidate&&candidate!==document.body;depth+=1){\n'
                                          '        const '
                                          'style=window.getComputedStyle(candidate);\n'
                                          '        '
                                          "if(style.position==='fixed'||style.position==='sticky'){\n"
                                          '          candidate.remove();\n'
                                          '          return true;\n'
                                          '        }\n'
                                          '        '
                                          'candidate=candidate.parentElement;\n'
                                          '      }\n'
                                          '\n'
                                          '      node.remove();\n'
                                          '      return true;\n'
                                          '    }\n'
                                          '    return false;\n'
                                          '  }\n'
                                          '\n'
                                          '  function '
                                          'installLiveSearchBadgeRemoval(){\n'
                                          '    removeLiveSearchBadge();\n'
                                          '    '
                                          'if(window.__lexiaAppLiveBadgeObserverInstalled)return;\n'
                                          '    '
                                          'window.__lexiaAppLiveBadgeObserverInstalled=true;\n'
                                          '    const observer=new '
                                          'MutationObserver(()=>removeLiveSearchBadge());\n'
                                          '    '
                                          'observer.observe(document.body,{childList:true,subtree:true});\n'
                                          '  }\n'
                                          '\n',
                                   'new': '  function '
                                          'removeLiveSearchBadge(){\n'
                                          '    const '
                                          "badge=document.getElementById('liveBadge');\n"
                                          '    if(!badge)return false;\n'
                                          '    badge.remove();\n'
                                          '    return true;\n'
                                          '  }\n'
                                          '\n'
                                          '  function '
                                          'installLiveSearchBadgeRemoval(){\n'
                                          '    '
                                          'if(window.__lexiaAppLiveBadgeObserverInstalled)return;\n'
                                          '    '
                                          'window.__lexiaAppLiveBadgeObserverInstalled=true;\n'
                                          '    // The badge is already in the '
                                          'static HTML before this script '
                                          'loads. A\n'
                                          '    // document-wide observer '
                                          'repeatedly scanned every node on '
                                          'large screens.\n'
                                          '    removeLiveSearchBadge();\n'
                                          '  }\n'
                                          '\n'},
 'app/ui2/assets/windows_live_badge_cleanup.js': {'target': '933ebf3afe115c09e3f619304e0354a0d729e05b0639ecc085c32cafc33a9caa',
                                                  'known': ['c660756d4d28797ca81d0db4e399afdf4d21c335d542b31ac93c3e4c79aa5a0c']},
 'app/ui2/windows_desktop.py': {'target': '5fd753f2f079fab67f11219bf93cc2d7dbd9bc576f84943e4dd7fe569e1634d2',
                                'old': '    if '
                                       '"assets/windows_live_badge_cleanup.js" '
                                       'not in patched:\n'
                                       '        tag = (\n'
                                       "            '<script "
                                       'src="assets/windows_live_badge_cleanup.js\'\n'
                                       '            '
                                       '\'?v=windows-live-cleanup-1"></script>\\n\'\n'
                                       '        )\n'
                                       '        patched = '
                                       'patched.replace("</body>", tag + '
                                       '"</body>", 1) if "</body>" in patched '
                                       'else patched + "\\n" + tag\n'
                                       '        changed = True\n'
                                       '\n',
                                'new': '    patched, asset_changed = '
                                       '_upsert_asset_script(\n'
                                       '        patched, live_badge_cleanup, '
                                       '"windows-live-cleanup"\n'
                                       '    )\n'
                                       '    changed = changed or '
                                       'asset_changed\n'
                                       '\n'}}

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
    backup = backup_parent / ('lexia-inicio-respaldo-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
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
            if before is None:
                raise ValueError('Falta un archivo necesario de la instalación')
            local_text, bom, crlf = decode(before)
            current_hash = digest(local_text.encode('utf-8'))
            if current_hash == specification['target']:
                continue
            if 'old' in specification:
                previous = specification['old']
                replacement = specification['new']
                if local_text.count(replacement) == 1 and previous not in local_text:
                    continue
                if local_text.count(previous) != 1:
                    raise ValueError('No se encontró exactamente una vez la rutina antigua; se conservaron los cambios locales')
                after = encode(local_text.replace(previous, replacement, 1), bom, crlf)
            else:
                if current_hash not in specification['known']:
                    raise ValueError('Hay cambios locales no reconocidos; se conservaron')
                after = encode(target_text, bom, crlf)
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
    print('La portada ya no recorre todo el documento al actualizarse. Reiniciá LexIA.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

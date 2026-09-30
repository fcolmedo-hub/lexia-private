#!/usr/bin/env python3
"""Actualización Mac al código PR24, sin cambiar rama, catálogo ni index.html."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime
from difflib import SequenceMatcher
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

BASE = "b4c3c00b0bf2d54f2c62e9d4bc2fd02ecb5f9efe"
TARGET = "41b8b70a8acd81f59b42dd5a98241bcee1a0e06f"
FILES = (('app/ui2/assets/app_runtime.js', 'modified', 'f765475376d64feff023391a4923678495b75aca'),
 ('app/ui2/assets/maintenance.css', 'modified', '3a143e0caada4f684ca1a9c6ecbd4bfeded5f46f'),
 ('app/ui2/assets/maintenance.js', 'modified', 'c49ac85734899fc122068baf59f07c02962635fb'),
 ('app/ui2/assets/shared_ui_consistency.css', 'modified', '70537982a948fa1eae19ebb9997e71a0487ec6cd'),
 ('app/ui2/assets/standards_nav_fix.js', 'modified', '8fbb0d9148db2e29da7daee598959d07485d3b2f'),
 ('app/ui2/assets/standards_ui.js', 'modified', '34471867d8ddcfd9e874ad44a2c160e37eff8e25'),
 ('app/ui2/assets/windows_maintenance_duplicates.js', 'modified', 'ee49a37ccde5c538d7d620626b9c25035bff6126'),
 ('app/ui2/assets/windows_maintenance_status_detail.js',
  'modified',
  '4b1ddb37c5ca286bb59efb84524649450b468f13'),
 ('app/ui2/assets/windows_search_results_polish.js', 'modified', '122350f720135e985db9bf83de482f2051f0fc56'),
 ('app/ui2/navigator_3_3_4a.js', 'modified', '369f8dfe8edf8c10147a9ec2abdbd64abf492b19'),
 ('app/ui2/standards_api.py', 'modified', 'f185821c87c2bec0332bdeaa437b9bcce868c31b'),
 ('core/document_detector.py', 'modified', 'fddc54c4ca066bfdda451f483f59ab5586813b19'),
 ('docs/maintenance-review-2026-09.md', 'added', '66cb74d30ff72f341f5514421cd2fbba183a1d5b'),
 ('prompt/standards_extraction_v5.txt', 'added', 'cc8b230603515bf156d2b60a9be97365150bc9a5'),
 ('requirements.txt', 'modified', 'd9d9da75562c0741c1df4b2dcc6ccac635350d18'),
 ('scripts/install_maintenance_progress.py', 'added', 'af8fff4c104669d274d7d00cab13d1e66ec23a7a'),
 ('scripts/install_maintenance_windows.py', 'added', 'bb2647e8108b35cd7904681637de90a2e723474d'),
 ('scripts/install_pr24_windows.py', 'added', '276b687cb779bfcfe0b267e4e98732aaf435494a'),
 ('scripts/install_standards_refresh.py', 'added', '09cd1ff5c430fb9b2b759571c85d6c718be02f8b'),
 ('services/autosync_service.py', 'modified', 'b88a5de24655308bf984742e9ee684a7548c4d81'),
 ('services/library_snapshot_service.py', 'modified', '0aaf42e617554eb97b5962232307359fde5addea'),
 ('services/ocr_queue_service.py', 'modified', '0611f5aa02db512cf9f110c29d5eaff52d8f8d1c'),
 ('services/secure_document_deletion.py', 'modified', '397d5af01862a0f719abb5c5420358e3c7c1937a'),
 ('services/standards_batch_ui.py', 'added', 'fb63e224189305e1ce14f4442af20fe74bd5d4b9'),
 ('services/standards_pipeline.py', 'added', '3db96aa8b3ae08a75777f2bf62b298a4b69b7799'),
 ('services/standards_service.py', 'modified', '156f645b1fe6867c0f749fb3c4a3ac33c1de7e6a'),
 ('services/ui2_delete_bridge.py', 'modified', '5038dd851a8d4fef53365112ef733e5705b98d64'),
 ('services/windows_research_manual_sources.py', 'modified', 'afc547e1775b6fdd34b1031e123973c1d2023708'),
 ('standards/ENGINE.md', 'modified', '124ed1144a3c70b968db04fcec7d44a059addd30'),
 ('storage/ocr_queue_repository.py', 'modified', '7158554280259e827f9a1820590abebee625065f'),
 ('tests/maintenance_ui/layout.cjs', 'added', 'f14832e6f97ba71caa3ac7ed58918f5b367af7ee'),
 ('tests/maintenance_ui/maintenance.test.cjs', 'added', 'e0cb4d34960cfc0add39eba924d233d39616eacc'),
 ('tests/maintenance_ui/package.json', 'added', '77ce163c79fcdb0933e884baa69ff3fc40bb7313'),
 ('tests/test_autosync_progress.py', 'added', 'c879d73abec82f95f0d25145ef412fd7131ab7b2'),
 ('tests/test_duplicate_bulk_job.py', 'added', 'aafb05376d7e414a74c0fc07e1e5ae106476c239'),
 ('tests/test_install_pr24_windows.py', 'added', '157f65c50bad7ff6e5b2bd4dd247d5cd1bbb6b0c'),
 ('tests/test_maintenance_layout_ocr_3_3_5.py', 'modified', 'b2daafae1d9767e2b57f9a1f0434091be10a5edd'),
 ('tests/test_maintenance_ocr_selection.py', 'added', '511cec4fb736ed747234886fc2cbb66d068f2c7e'),
 ('tests/test_maintenance_windows_installer.py', 'added', 'ba7eda646c8dd6c88d4fa1b7eeba70f0a0c045ba'),
 ('tests/test_standards_batch_ui.py', 'added', 'f2689948a53c7a79817da10589b50a4d2f0aaf21'),
 ('tests/test_standards_candidate_selection.py', 'added', '04a083b29becadf1484dc7238c44db878e8b8a0b'),
 ('tests/test_standards_document_metadata.py', 'added', '86db2820431bae2c8dc4d149b40c7c4dd8ec0804'),
 ('tests/test_standards_import_incremental.py', 'added', 'dbe1fe2d7dcc10444d6609d2fdfa91985683cfbd'),
 ('tests/test_standards_pipeline.py', 'added', '88f430772f1a81f490f944fe04d5a6b2488b6271'),
 ('tests/test_standards_refresh_installer.py', 'added', '2469fb4627aa0aaa28c7d7f27337b7f4ab96d2c7'),
 ('tests/test_standards_relation_preparation_bounds.py', 'added', 'fb34fed76c95712559dce519006b1e1846da95db'),
 ('tests/test_standards_service.py', 'modified', '80c1444dcbb5a5b397461d4d078bf07ec5f7a68b'),
 ('tests/test_standards_ui_pagination.py', 'modified', '2a3dc8f098af4daad1f56433ddc4cf54bfeff7a3'),
 ('tests/test_windows_maintenance_and_manual_source_polish.py',
  'modified',
  '08884459b13940f35ed44bb23aab29efdae95c70'),
 ('tools/actualizar_diccionario_estandares.py', 'added', '8915482d5b730bcdba0d4520537230626f49fae0'),
 ('tools/aplicar_relaciones_estandares.py', 'added', '53820b7b0330613512478faad1d9ee439a46faa0'),
 ('tools/exportar_estandares_piloto.py', 'added', '13bbc35b86d9064994f650ea8692be5bf571188a'),
 ('tools/importar_estandares_sqlite.py', 'modified', '775ddd1a8a24f4e2d998ed1a83cf87f7dc42b5bf'),
 ('tools/preparar_canonicalizacion_estandares.py', 'added', '71fae824ef7a34f7b37918d7ce04516f6ef05bf4'),
 ('tools/preparar_estandares_v2.py', 'added', '6908f857ac1cb665974a835747e8d349f7cb0288'),
 ('tools/preparar_estandares_v5.py', 'added', '86efdef50dbe5113f5ddc32d5e8e55ca64725f59'),
 ('tools/preseleccionar_fallos_estandares.py', 'added', '3c3c6ad3fbe113eeb7c5a4faef1ea25bf1cd457c'),
 ('tools/procesar_canonicalizacion_batch.py', 'added', '1f553088c072d97d120e4d3a386927ea85647071'),
 ('tools/procesar_estandares_batch_v5.py', 'added', '8ae42a8a977be49210609cb296651c2004561d4f'),
 ('tools/tribunales_estandares.py', 'added', '9ef7749e093d13156eb9b0bfca2370e490b1e7e1'),
 ('tools/validar_estandares_v2.py', 'added', '4d76bb80391d826ff542da6af7ae604e139ac9ee'),
 ('tools/validar_estandares_v5.py', 'added', 'dc81f5a0103de1bfeacdf9a9a1928eabb0d26eb5'))
REVIEWED_LOCAL_SHA256 = {'app/ui2/assets/maintenance.js': 'cebb05b5741e2b95732f732e23092c0c82e69a38c7de6c149443be03899d97b1',
 'app/ui2/assets/windows_maintenance_duplicates.js': '4bc7b56bd7a0cc40f8168a483298e799a20ba06b86441ad63f972396b43f6a3f'}

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


def merge(current: bytes, before: bytes, after: bytes) -> bytes:
    local, bom, crlf = decode(current)
    old = decode(before)[0]
    new = decode(after)[0]
    if local == new:
        return current
    if local == old:
        return encode(new, bom, crlf)
    with tempfile.TemporaryDirectory(prefix="lexia-merge-") as temporary:
        paths = [Path(temporary) / name for name in ("local", "base", "new")]
        for path, value in zip(paths, (local, old, new)):
            path.write_text(value, encoding="utf-8", newline="\n")
        result = subprocess.run(["git", "merge-file", "-p", *(str(path) for path in paths)], capture_output=True)
    if result.returncode == 0:
        return encode(result.stdout.decode("utf-8"), bom, crlf)
    # git merge-file returns the number of conflicts (capped at 127), so 2+
    # is also a merge conflict, not an unexplained process failure.
    if result.returncode < 0 or result.returncode >= 128:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Falló git merge-file (código {result.returncode}). {detail}")
    # Git groups adjacent edits into a conflict even when they touch distinct
    # lines. Retry only when every edit occupies a disjoint base-line range.
    base_lines = old.splitlines(keepends=True)

    def edits(variant: str):
        lines = variant.splitlines(keepends=True)
        matcher = SequenceMatcher(None, base_lines, lines, autojunk=False)
        return [(start, end, lines[left:right]) for tag, start, end, left, right in matcher.get_opcodes() if tag != "equal"]

    local_edits = edits(local)
    target_edits = edits(new)
    for start, end, replacement in target_edits:
        for other_start, other_end, other_replacement in local_edits:
            same = (start, end, replacement) == (other_start, other_end, other_replacement)
            overlaps = max(start, other_start) < min(end, other_end)
            touches_insertion = (start == end and other_start <= start <= other_end) or (other_start == other_end and start <= other_start <= end)
            if (overlaps or touches_insertion) and not same:
                raise ValueError("Los cambios locales se cruzan con esta actualización; no se escribió ningún archivo.")
    all_edits = list(local_edits)
    for edit in target_edits:
        if edit not in all_edits:
            all_edits.append(edit)
    merged = []
    position = 0
    for start, end, replacement in sorted(all_edits, key=lambda item: (item[0], item[1])):
        merged.extend(base_lines[position:start])
        merged.extend(replacement)
        position = end
    merged.extend(base_lines[position:])
    return encode("".join(merged), bom, crlf)


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


def plan(root: Path) -> dict:
    git(root, 'rev-parse', '--verify', f'{BASE}^{{commit}}')
    git(root, 'rev-parse', '--verify', f'{TARGET}^{{commit}}')
    planned = {}
    conflicts = []
    for name, status, expected_blob in FILES:
        try:
            path = safe_path(root, name)
            target = git(root, 'show', f'{TARGET}:{name}')
            blob = hashlib.sha1(b'blob ' + str(len(target)).encode() + b'\0' + target).hexdigest()
            if blob != expected_blob:
                raise ValueError('El contenido descargado no coincide con la revisión fijada')
            current = path.read_bytes() if path.exists() else None
            if current is not None and decode(current)[0] == decode(target)[0]:
                continue
            if current is None:
                if status != 'added':
                    raise ValueError('Falta el archivo local; no se restaura automáticamente')
                result = target
            elif digest(current) == REVIEWED_LOCAL_SHA256.get(name):
                # These two exact files were reviewed against the uploaded Mac
                # snapshot. Every difference is an intended PR24 update.
                _, bom, crlf = decode(current)
                result = encode(decode(target)[0], bom, crlf)
            elif status == 'added':
                raise ValueError('Ya existe con otro contenido')
            else:
                result = merge(current, git(root, 'show', f'{BASE}:{name}'), target)
            if result == current:
                continue
            if name.endswith('.py'):
                ast.parse(decode(result)[0], filename=name)
            if any(line.startswith((b'<<<<<<< ', b'>>>>>>> ')) for line in result.splitlines()):
                raise ValueError('Se encontraron marcadores de conflicto')
            planned[name] = {
                'before': current, 'after': result,
                'mode': stat.S_IMODE(path.stat().st_mode) if current is not None else 0o644,
            }
        except (RuntimeError, ValueError, OSError, SyntaxError, UnicodeError) as error:
            conflicts.append(f'{name}: {error}')
    if conflicts:
        raise ValueError('No se modificó LexIA. Conflictos:\n- ' + '\n- '.join(conflicts))
    return planned


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
    backup = backup_parent / ('lexia-mac-pr24-respaldo-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Comprobar sin modificar archivos')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        raise SystemExit('Este instalador es para macOS.')
    try:
        root = Path(git(Path.cwd(), 'rev-parse', '--show-toplevel').decode().strip()).resolve()
        planned = plan(root)
        print(f'Comprobación correcta: {len(planned)} archivo(s) por actualizar a {TARGET[:7]}.')
        print('Se conservan index.html, catálogo, runtime, configuración y cambios locales compatibles.')
        if args.check or not planned:
            return
        backup = install(root, planned)
        print(f'Instalación terminada. Respaldo: {backup}')
        print('Abrí LexIA de nuevo. Esta actualización no requiere reconstruir LexIA.app.')
    except (RuntimeError, ValueError, OSError) as error:
        raise SystemExit(str(error)) from error


if __name__ == '__main__':
    main()

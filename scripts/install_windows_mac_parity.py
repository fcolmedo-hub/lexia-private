#!/usr/bin/env python3
"""Actualiza Windows con las mejoras compartidas de Mac y conserva el arranque."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime
from functools import lru_cache
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

BASE = "400a1013e493438d6c898a9a55bb6861e97fd691"
STUDY_BASE = "d97696724af0a61af3dbaa3a523ba7ec44820e08"
STUDY_PREVIOUS = "142d2daf34f661c271f2c8402684c7b0df2444ff"
THEMATIC_PREVIOUS = "7c95bf1787ce018bac8d09ec07220866aa9dcd85"
STUDY = "98a155fee8ecfe23e6f03b1f6ef489b804483406"
SEARCH = "bb3d877aa2e258ae617101b0f027ef7b0d58c063"
DATES = "b39fc15040ac756e6eedd3104e2765f5a1fc6ccb"
MESSAGES = "ad40ad07d74e4db17fb9fd5078c93a6af511d876"
REFS = {
    STUDY: "fix/study-judgment-200k", SEARCH: "fix/legislation-keyword-priority",
    DATES: "fix/navigator-file-creation-date", MESSAGES: "fix/core-service-errors",
}
SERVER = "app/ui2/server.py"
INDEX = "app/ui2/index.html"
RUNTIME = "app/ui2/assets/app_runtime.js"
FRONTEND = "app/ui2/windows_parity_frontend.py"
CONFIRMATION = "app/ui2/assets/windows_study_confirmation.js"
STUDY_FILES = ("config/settings.py", "ai/knowledge_context_builder.py", "ai/thematic_document_study.py", "services/ui2_delete_bridge.py")
COPIES = {
    "app/ui2/legal_citations.py": SEARCH,
    "app/ui2/legislation_intent.py": SEARCH,
    "app/ui2/assets/legal_article_preview.js": SEARCH,
    "services/file_dates.py": DATES,
}
FRONTEND_BLOCK = '''        if path in {"/", "/index.html"}:
            try:
                from windows_parity_frontend import render_index
                rendered = render_index((HERE / "index.html").read_text(encoding="utf-8-sig")).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(rendered)))
                self.end_headers()
                self.wfile.write(rendered)
                return
            except (OSError, ValueError) as exc:
                return self._json({"ok": False, "error": str(exc)}, 503)

'''
LOADER = '''
;/* LexIA: exact legislation article preview (compatible installation). */
(function(){
  'use strict';
  if(document.querySelector('script[data-lexia-legal-article-preview]'))return;
  const locator=document.createElement('script');
  locator.src='assets/legal_article_preview.js?v=1';
  locator.async=false;
  locator.dataset.lexiaLegalArticlePreview='1';
  (document.body||document.documentElement).appendChild(locator);
})();
'''


def git(root, *args, check=True):
    result = subprocess.run(["git", *args], cwd=root, capture_output=True)
    if check and result.returncode:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip())
    return result


@lru_cache(maxsize=80)
def source_text(root: Path, revision: str, name: str) -> str:
    return git(root, "show", f"{revision}:{name}").stdout.decode("utf-8-sig").replace("\r\n", "\n")


def ensure_sources(root):
    missing = [branch for sha, branch in REFS.items() if git(root, "cat-file", "-e", sha + "^{commit}", check=False).returncode]
    if missing:
        print("Descargando las revisiones verificadas…", flush=True)
        git(root, "fetch", "origin", *missing)
    for sha in REFS:
        git(root, "cat-file", "-e", sha + "^{commit}")


def support(root, revision, name):
    namespace = {"__name__": "lexia_installer_support", "__file__": str(root / name)}
    code = source_text(root, revision, name)
    exec(compile(code, name, "exec"), namespace)
    return namespace


def merge_text(current, before, after, name):
    if before == after or current == after:
        return current
    with tempfile.TemporaryDirectory(prefix="lexia-combinar-") as folder:
        paths = [Path(folder) / value for value in ("local", "base", "target")]
        for path, text in zip(paths, (current, before, after)):
            path.write_text(text, encoding="utf-8", newline="\n")
        result = subprocess.run(["git", "merge-file", "-p", *map(str, paths)], capture_output=True)
        if result.returncode or b"\x00" in result.stdout:
            raise ValueError(f"{name}: hay cambios locales que se cruzan con la actualización.")
        return result.stdout.decode("utf-8")


def frontend_server(current):
    if FRONTEND_BLOCK in current:
        return current
    anchor = "    def do_GET(self):\n        path = urlparse(self.path).path\n\n"
    if current.count(anchor) != 1 or "from windows_parity_frontend import render_index" in current:
        raise ValueError("El servidor tiene un controlador de interfaz diferente.")
    return current.replace(anchor, anchor + FRONTEND_BLOCK, 1)


def prepare(root: Path, source: str):
    root = root.resolve()
    actual = Path(git(root, "rev-parse", "--show-toplevel").stdout.decode().strip()).resolve()
    if root != actual or git(root, "ls-files", "-u").stdout:
        raise ValueError("Ejecutá desde la raíz de LexIA, sin conflictos de Git pendientes.")
    ensure_sources(root)
    source = git(root, "rev-parse", "--verify", "--end-of-options", source + "^{commit}").stdout.decode().strip()
    names = (*STUDY_FILES, SERVER, "app/ui2/navigator_3_3_4a.js", *COPIES, FRONTEND, CONFIRMATION, RUNTIME)
    originals, texts = {}, {}
    for name in (*names, INDEX):
        path = root / name
        if path.is_symlink() or any((root / parent).is_symlink() for parent in Path(name).parents):
            raise ValueError(f"No se modificará una ruta enlazada: {name}")
        if path.exists() and not path.is_file():
            raise ValueError(f"No es un archivo regular: {name}")
        original = path.read_bytes() if path.exists() else None
        if original is None and name not in {*COPIES, FRONTEND, CONFIRMATION}:
            raise ValueError(f"Falta {name}.")
        originals[name] = original
        texts[name] = original.decode("utf-8-sig").replace("\r\n", "\n") if original is not None else ""
    for name in STUDY_FILES:
        before = STUDY_BASE
        if name == "services/ui2_delete_bridge.py" and '"phase": "awaiting_confirmation"' in texts[name]:
            before = STUDY_PREVIOUS
        elif name == "ai/thematic_document_study.py" and '"study_selection": {' in texts[name]:
            before = THEMATIC_PREVIOUS
        texts[name] = merge_text(texts[name], source_text(root, before, name), source_text(root, STUDY, name), name)
    texts[SERVER] = merge_text(texts[SERVER], source_text(root, BASE, SERVER), source_text(root, SEARCH, SERVER), SERVER)
    dates = support(root, DATES, "scripts/install_navigator_file_dates.py")
    for name in (SERVER, "app/ui2/navigator_3_3_4a.js"):
        texts[name] = dates["patched_text"](name, texts[name], source_text(root, BASE, name), source_text(root, DATES, name), source_text(root, dates["PREVIOUS"], name))
    messages = support(root, MESSAGES, "scripts/install_core_service_messages.py")
    texts[SERVER] = messages["prepare"](texts[SERVER].encode()).decode()
    texts[SERVER] = frontend_server(texts[SERVER])
    for name, revision in {**COPIES, FRONTEND: source, CONFIRMATION: source}.items():
        target = source_text(root, revision, name)
        if texts[name] and texts[name] != target:
            raise ValueError(f"{name}: existe una versión local diferente.")
        texts[name] = target
    if not ("data-lexia-legal-article-preview" in texts[RUNTIME] and "assets/legal_article_preview.js" in texts[RUNTIME]):
        texts[RUNTIME] += LOADER
    for name in names:
        if name.endswith(".py"):
            ast.parse(texts[name], filename=name)
    # Verify the rendered UI before any write, using only a temporary mirror.
    with tempfile.TemporaryDirectory(prefix="lexia-interfaz-") as folder:
        mirror = Path(folder)
        for name in (FRONTEND, CONFIRMATION):
            path = mirror / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(texts[name], encoding="utf-8", newline="\n")
        scope = {"__name__": "lexia_frontend_preflight", "__file__": str(mirror / FRONTEND)}
        exec(compile(texts[FRONTEND], FRONTEND, "exec"), scope)
        rendered = scope["render_index"](texts[INDEX])
        if not all(marker in rendered for marker in ("Cancelar sin costo", "Enviar análisis parcial", "window.lexiaSearch320Clear=clearSearch;")):
            raise ValueError("No se pudo preparar el aviso y la limpieza de búsqueda.")
    changes = []
    for name in names:
        original = originals[name]
        decoded = original.decode("utf-8-sig") if original else ""
        newline = "\r\n" if decoded.count("\r\n") > decoded.count("\n") / 2 else "\n"
        bom = "\ufeff" if original and original.startswith(b"\xef\xbb\xbf") else ""
        updated = (bom + texts[name].replace("\n", newline)).encode("utf-8")
        if updated != original:
            changes.append((root / name, original, updated))
    return changes, (root / INDEX, originals[INDEX])


def atomic_write(path, data, mode=0o644):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="lexia-actualizar-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def apply_plan(root, changes, read_guard):
    for path, original in [(path, original) for path, original, _ in changes] + [read_guard]:
        if (path.read_bytes() if path.exists() else None) != original:
            raise ValueError(f"El archivo cambió durante la comprobación: {path.name}")
    if not changes:
        return None
    parent = Path.home() / "Desktop"
    if not parent.is_dir():
        parent = Path.home()
    backup = parent / ("lexia-windows-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    backup.mkdir()
    modes, manifest = {}, {}
    for path, original, _ in changes:
        name = str(path.relative_to(root))
        modes[path] = stat.S_IMODE(path.stat().st_mode) if original is not None else 0o644
        manifest[name] = {"existed": original is not None}
        if original is not None:
            saved = backup / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    written = []
    try:
        for path, original, updated in changes:
            atomic_write(path, updated, modes[path])
            written.append((path, original))
    except OSError:
        for path, original in reversed(written):
            if original is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, original, modes[path])
        raise
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if os.name != "nt":
        raise ValueError("Este instalador es para Windows.")
    root = Path.cwd().resolve()
    changes, guard = prepare(root, args.source)
    if not changes:
        print("Las mejoras ya están instaladas.")
    elif args.check:
        print(f"Comprobación correcta: {len(changes)} archivos por actualizar. No se modificó LexIA.")
        for path, _, _ in changes:
            print("-", path.relative_to(root))
    else:
        backup = apply_plan(root, changes, guard)
        print(f"Actualización terminada. Respaldo: {backup}")
        print("Abrí LexIA desde el acceso directo habitual.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, UnicodeError, SyntaxError) as exc:
        print(f"No se pudo instalar: {exc}", file=sys.stderr)
        raise SystemExit(1)

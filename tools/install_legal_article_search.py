#!/usr/bin/env python3
"""Install the reviewed article-search fix without replacing a customized runtime.

Run from the LexIA checkout after fetching fix/legal-article-search. Git's index,
the current branch, and index.html are left untouched. Uses only the stdlib.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


FIX = "abc5200389f8bdf32a89e93f8ee0146683247b80"
BASE = "400a1013e493438d6c898a9a55bb6861e97fd691"
FILES = (
    "app/ui2/assets/legal_article_preview.js",
    "app/ui2/legal_citations.py",
    "app/ui2/server.py",
    "tests/test_content_search_legislation_priority.py",
    "tests/test_legal_article_preview.js",
)
RUNTIME = "app/ui2/assets/app_runtime.js"
LOADER = b"""
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
"""


def git(root, *args, data=None, check=True):
    result = subprocess.run(
        ["git", "-C", str(root), *args], input=data, capture_output=True
    )
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return result


def atomic_write(path, content, mode):
    fd, name = tempfile.mkstemp(prefix=".lexia-install-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def install(root, backup_parent=None):
    root = Path(root).resolve()
    actual_root = Path(git(root, "rev-parse", "--show-toplevel").stdout.decode().strip()).resolve()
    if actual_root != root:
        raise RuntimeError("Ejecutá el instalador desde la carpeta principal de LexIA.")
    if git(root, "ls-files", "-u").stdout:
        raise RuntimeError("Hay conflictos de Git pendientes. No se modificó ningún archivo.")
    git(root, "cat-file", "-e", FIX + "^{commit}")
    snapshots = {}
    for name in (*FILES, RUNTIME):
        path = root / name
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
            raise RuntimeError("No se reemplazará un enlace simbólico: " + name)
        snapshots[name] = (path.read_bytes(), path.stat().st_mode) if path.exists() else None
    if snapshots[RUNTIME] is None:
        raise RuntimeError("No se encontró " + RUNTIME)

    patches = []
    changed = []
    for name in FILES:
        patch = git(root, "diff", "--no-ext-diff", "--no-textconv", "--binary", BASE, FIX, "--", name).stdout
        if not patch:
            raise RuntimeError("No se encontró la corrección esperada para " + name)
        forward = git(root, "apply", "--check", "-", data=patch, check=False)
        if forward.returncode == 0:
            patches.append(patch)
            changed.append(name)
        elif git(root, "apply", "--reverse", "--check", "-", data=patch, check=False).returncode != 0:
            raise RuntimeError("No se modificó ningún archivo. Necesita revisión: " + name + "\n" + forward.stderr.decode("utf-8", "replace"))

    runtime, mode = snapshots[RUNTIME]
    has_loader = b"data-lexia-legal-article-preview" in runtime and b"assets/legal_article_preview.js" in runtime
    new_runtime = runtime
    if not has_loader:
        loader = LOADER.replace(b"\n", b"\r\n") if b"\r\n" in runtime else LOADER
        new_runtime += loader
        changed.append(RUNTIME)
    combined = b"".join(patches)
    if combined:
        git(root, "apply", "--check", "-", data=combined)
    if not changed:
        print("La corrección de búsqueda de artículos ya está instalada.")
        return None

    if backup_parent is None:
        desktop = Path.home() / "Desktop"
        backup_parent = desktop if desktop.is_dir() else Path.home()
    backup = Path(tempfile.mkdtemp(prefix="lexia-respaldo-articulos-", dir=backup_parent))
    for name, snapshot in snapshots.items():
        if snapshot is not None:
            destination = backup / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, destination)
    (backup / "archivos-nuevos.txt").write_text("\n".join(name for name in changed if snapshots[name] is None), encoding="utf-8")
    for name, snapshot in snapshots.items():
        path = root / name
        current = path.read_bytes() if path.exists() else None
        if current != (snapshot[0] if snapshot else None):
            raise RuntimeError("Un archivo cambió durante la comprobación. Cerrá LexIA y repetí: " + name)

    try:
        if combined:
            git(root, "apply", "-", data=combined)
        if not has_loader:
            atomic_write(root / RUNTIME, new_runtime, mode)
    except Exception:
        for name in changed:
            snapshot = snapshots[name]
            path = root / name
            if snapshot is None:
                if path.exists():
                    path.unlink()
            else:
                atomic_write(path, snapshot[0], snapshot[1])
        raise RuntimeError("La instalación no pudo completarse; se restauraron los archivos. Respaldo: " + str(backup))
    print("Corrección de búsqueda de artículos instalada.")
    print("Se conservaron los ajustes existentes de app_runtime.js y la rama actual.")
    print("Respaldo: " + str(backup))
    return backup


if __name__ == "__main__":
    try:
        install(Path.cwd())
    except (OSError, RuntimeError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        sys.exit(1)

import json
import os
from pathlib import Path
import subprocess

import pytest

from scripts import install_navigator_file_dates as installer


ROOT = Path(__file__).resolve().parents[1]


def sources():
    names = (installer.SERVER, installer.NAVIGATOR, installer.DATES)
    before = {name: subprocess.check_output(["git", "show", f"{installer.BASE}:{name}"], cwd=ROOT).decode() if name != installer.DATES else "" for name in names}
    after = {name: (ROOT / name).read_text() for name in names}
    return before, after


def setup_installation(monkeypatch, tmp_path):
    before, after = sources()
    root = tmp_path / "checkout"
    for name in (installer.SERVER, installer.NAVIGATOR):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        note = "\n# Keep local server configuration\n" if name.endswith(".py") else "\n// Keep local navigator selection fixes\n"
        path.write_bytes(("\ufeff" + (before[name] + note).replace("\n", "\r\n")).encode())
    (root / "services").mkdir()
    monkeypatch.setattr(installer, "git_text", lambda _root, revision, name: before[name] if revision == installer.BASE else after[name])
    monkeypatch.setattr(installer.Path, "home", lambda: tmp_path)
    return root


def test_install_preserves_customizations_and_has_no_data_migrations(monkeypatch, tmp_path):
    root = setup_installation(monkeypatch, tmp_path)
    originals = {name: (root / name).read_bytes() for name in (installer.SERVER, installer.NAVIGATOR)}
    plan = installer.prepare(root, "new-revision")
    assert len(plan) == 3
    assert not (root / installer.DATES).exists()
    for name, content in originals.items():
        assert (root / name).read_bytes() == content
    backup = installer.apply_plan(root, plan)
    for name, content in originals.items():
        assert (backup / name).read_bytes() == content
        updated = (root / name).read_bytes()
        assert updated.startswith(b"\xef\xbb\xbf")
        assert b"\r\n" in updated
        assert b"Keep local" in updated
    assert (root / installer.DATES).is_file()
    assert installer.prepare(root, "new-revision") == []
    manifest = json.loads((backup / "manifest.json").read_text())
    assert not manifest[installer.DATES]["existed"]


def test_conflicting_date_logic_blocks_whole_install(monkeypatch, tmp_path):
    root = setup_installation(monkeypatch, tmp_path)
    path = root / installer.NAVIGATOR
    original = path.read_bytes().replace(b"Sin fecha", b"Fecha personalizada")
    path.write_bytes(original)
    with pytest.raises(ValueError, match="cambios locales"):
        installer.prepare(root, "new-revision")
    assert path.read_bytes() == original
    assert not (root / installer.DATES).exists()
    assert not list(tmp_path.glob("lexia-fechas-*"))


def test_partial_install_failure_restores_original_files(monkeypatch, tmp_path):
    root = setup_installation(monkeypatch, tmp_path)
    original = (root / installer.SERVER).read_bytes()
    plan = installer.prepare(root, "new-revision")
    write = installer.atomic_write
    calls = []
    def fail_second_write(path, data, mode):
        calls.append(path)
        if len(calls) == 2:
            raise OSError("Simulated replace failure")
        write(path, data, mode)
    monkeypatch.setattr(installer, "atomic_write", fail_second_write)
    with pytest.raises(OSError):
        installer.apply_plan(root, plan)
    assert (root / installer.SERVER).read_bytes() == original
    assert not (root / installer.DATES).exists()


def test_navigator_displays_local_creation_date_and_unknown_date():
    script = r'''
const fs=require('fs');
const text=fs.readFileSync(process.argv[1],'utf8');
const dateBlock=text.slice(text.indexOf('  const date=value=>{'),text.indexOf('  const post=async'));
const card=text.slice(text.indexOf('  function fileCard('),text.indexOf('  function closeFileMenus('));
const state={offset:0,selectedFiles:new Set()};
const esc=value=>String(value??'').replace(/[&<>"']/g, char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const size=value=>'1 KB',number=value=>String(value);
const render=new Function('state','esc','size','number',dateBlock+card+'return fileCard;')(state,esc,size,number);
const row={document_path:'/file.pdf',document_name:'File.pdf',size:1000,total_pages:6,updated_at:'2099-12-31',file_created_at:'2026-10-01T01:30:00+00:00'};
const known=render(row,0),unknown=render({...row,file_created_at:''},1);
if(!known.includes('Creado: 30/9/2026')||known.includes('2099'))throw new Error(known);
if(!unknown.includes('Creación no disponible')||unknown.includes('2099'))throw new Error(unknown);
'''
    subprocess.run(["node", "-e", script, str(ROOT / installer.NAVIGATOR)], env={**os.environ, "TZ": "America/Cordoba"}, check=True, capture_output=True, text=True)

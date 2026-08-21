from __future__ import annotations
import argparse, json, shutil, sqlite3, sys, time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from config.settings import SETTINGS

PROTECTED_ROOTS = {"Jurisprudencia", "Escritos", "Doctrina"}
DEFAULT_DISABLED = {"Downloads", "PRUEBA 101051"}
TARGET_CATEGORY = "Jurisprudencia"

@dataclass(slots=True)
class MoveRule:
    source_name: str
    destination_category: str = TARGET_CATEGORY
    enabled: bool = True

@dataclass(slots=True)
class MigrationPlan:
    created_at: str
    library_path: str
    rules: list[MoveRule]
    def to_json(self):
        return {
            "created_at": self.created_at,
            "library_path": self.library_path,
            "rules": [asdict(r) for r in self.rules],
        }

def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()

def library_path():
    return resolve_path(Path(SETTINGS.library_path))

def runtime_path():
    return resolve_path(Path(SETTINGS.runtime_path))

def catalog_path():
    return resolve_path(Path(SETTINGS.catalog_path))

def knowledge_path():
    return resolve_path(Path(getattr(SETTINGS, "knowledge_path", "runtime/knowledge.sqlite3")))

def ocr_path():
    return resolve_path(Path(getattr(SETTINGS, "ocr_queue_path", "runtime/ocr_queue.sqlite3")))

def snapshot_path():
    return runtime_path() / "library_snapshot.json"

def autosync_state_path():
    value = getattr(SETTINGS, "autosync_state_path", runtime_path() / "autosync_state.json")
    return resolve_path(Path(value))

def plan_path():
    return runtime_path() / "library_migration_plan.json"

def journal_path():
    return runtime_path() / "library_migration_journal.json"

def report_path():
    return runtime_path() / "library_migration_report.json"

def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False

def build_plan():
    root = library_path()
    if not root.exists():
        raise RuntimeError(f"No existe la biblioteca: {root}")
    rules = []
    for child in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name.casefold()):
        if child.name in PROTECTED_ROOTS:
            continue
        rules.append(MoveRule(child.name, enabled=child.name not in DEFAULT_DISABLED))
    return MigrationPlan(datetime.now().isoformat(timespec="seconds"), str(root), rules)

def save_plan(plan):
    path = plan_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path

def load_plan(path=None):
    source = path or plan_path()
    data = json.loads(source.read_text(encoding="utf-8"))
    return MigrationPlan(
        str(data.get("created_at", "")),
        str(data["library_path"]),
        [MoveRule(**item) for item in data.get("rules", [])],
    )

def count_files(folder):
    return sum(1 for p in folder.rglob("*") if p.is_file())

def print_plan(plan):
    root = Path(plan.library_path)
    print("\nLexIA Library Migration Manager 1.0")
    print("=" * 68)
    print(f"Biblioteca: {root}")
    print(f"Destino:    {root / TARGET_CATEGORY}\n")
    enabled = files = 0
    for rule in plan.rules:
        source = root / rule.source_name
        count = count_files(source) if source.exists() else 0
        status = "MOVER" if rule.enabled else "NO MOVER"
        print(f"  [{status:8}] {rule.source_name} ({count} archivos)")
        if rule.enabled:
            enabled += 1
            files += count
    print(f"\nCarpetas habilitadas: {enabled}")
    print(f"Archivos físicos aproximados: {files}")
    print("\nJurisprudencia, Escritos y Doctrina están protegidas.")
    print("Downloads y PRUEBA 101051 quedan deshabilitadas por defecto.")
    print("LexIA debe estar CERRADO durante --apply y --rollback.")

def backup_file(src, backup_dir):
    if not src.exists():
        return None
    dst = backup_dir / src.name
    shutil.copy2(src, dst)
    return str(dst)

def create_backup():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = resolve_path(Path(getattr(SETTINGS, "backups_path", ROOT / "backups")))
    backup_dir = base / "library_migration_1_0" / stamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"created_at": datetime.now().isoformat(timespec="seconds"), "files": {}}
    for name, path in {
        "catalog": catalog_path(), "knowledge": knowledge_path(), "ocr": ocr_path(),
        "snapshot": snapshot_path(), "autosync": autosync_state_path()
    }.items():
        manifest["files"][name] = {"source": str(path), "backup": backup_file(path, backup_dir)}
    (backup_dir / "backup_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return backup_dir

def build_path_map(plan):
    root = Path(plan.library_path).resolve()
    destination_root = (root / TARGET_CATEGORY).resolve()
    enabled = [(root / r.source_name).resolve() for r in plan.rules if r.enabled]
    with sqlite3.connect(catalog_path()) as con:
        rows = con.execute("SELECT path FROM documents WHERE is_deleted = 0").fetchall()
    mapping = {}
    for (raw,) in rows:
        old = Path(raw).resolve()
        for source in enabled:
            if is_relative_to(old, source):
                mapping[str(old)] = str((destination_root / source.name / old.relative_to(source)).resolve())
                break
    return mapping

def validate_plan(plan, mapping):
    root = Path(plan.library_path).resolve()
    if root != library_path().resolve():
        raise RuntimeError("El plan pertenece a otra biblioteca.")
    (root / TARGET_CATEGORY).mkdir(parents=True, exist_ok=True)
    for rule in plan.rules:
        if not rule.enabled:
            continue
        if rule.source_name in PROTECTED_ROOTS:
            raise RuntimeError(f"Carpeta protegida: {rule.source_name}")
        source = root / rule.source_name
        dest = root / TARGET_CATEGORY / rule.source_name
        if not source.exists():
            raise RuntimeError(f"No existe el origen: {source}")
        if dest.exists():
            raise RuntimeError(f"Ya existe el destino y no se hará merge: {dest}")
    if len(mapping.values()) != len({v.casefold() for v in mapping.values()}):
        raise RuntimeError("El plan produciría rutas duplicadas.")
    if not mapping:
        raise RuntimeError("No hay documentos del catálogo para migrar.")

def rewrite_metadata(raw, category):
    try:
        meta = json.loads(raw or "{}")
    except json.JSONDecodeError:
        meta = {}
    cls = meta.get("classification")
    if not isinstance(cls, dict):
        cls = {}
    cls.update({
        "document_type": category,
        "confidence": 1.0,
        "reasons": ["Categoría autoritativa determinada por carpeta física"],
        "source": "physical_folder",
    })
    meta["classification"] = cls
    meta["physical_category"] = category
    return json.dumps(meta, ensure_ascii=False)

def migrate_catalog(mapping, category):
    original_meta = {}
    with sqlite3.connect(catalog_path()) as con:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = OFF")
        con.execute("BEGIN IMMEDIATE")
        try:
            for old, new in mapping.items():
                row = con.execute(
                    "SELECT name, category, metadata_json FROM documents WHERE path = ?", (old,)
                ).fetchone()
                if not row:
                    continue
                original_meta[old] = dict(row)
                meta = rewrite_metadata(row["metadata_json"], category)
                con.execute(
                    "UPDATE documents SET path=?, category=?, metadata_json=?, updated_at=CURRENT_TIMESTAMP WHERE path=?",
                    (new, category, meta, old),
                )
                con.execute("UPDATE fragments SET document_path=?, category=? WHERE document_path=?",
                            (new, category, old))
                con.execute("UPDATE document_locations SET path=?, is_current=1, last_seen_at=CURRENT_TIMESTAMP WHERE path=?",
                            (new, old))
                con.execute("UPDATE documents SET duplicate_of=? WHERE duplicate_of=?", (new, old))
                con.execute("UPDATE vector_relocations SET old_path=? WHERE old_path=?", (new, old))
                con.execute("UPDATE vector_relocations SET new_path=? WHERE new_path=?", (new, old))
            con.execute("DELETE FROM fragments_fts")
            con.execute("""
                INSERT INTO fragments_fts(document_path,fragment_index,category,document_name,text_content)
                SELECT f.document_path,f.fragment_index,f.category,d.name,f.text_content
                FROM fragments f JOIN documents d ON d.path=f.document_path
                WHERE d.is_deleted=0
            """)
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.execute("PRAGMA foreign_keys = ON")
    return original_meta

def migrate_knowledge(mapping, category):
    db = knowledge_path()
    if not db.exists():
        return 0
    changed = 0
    with sqlite3.connect(db) as con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for old, new in mapping.items():
            if "knowledge_documents" in tables:
                changed += con.execute(
                    "UPDATE knowledge_documents SET document_path=?, category=? WHERE document_path=?",
                    (new, category, old),
                ).rowcount
            for table in ("document_concepts", "document_citations"):
                if table in tables:
                    con.execute(f"UPDATE {table} SET document_path=? WHERE document_path=?", (new, old))
        con.commit()
    return changed

def tables_with_column(con, column):
    result = []
    for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        if table.startswith("sqlite_"):
            continue
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if column in cols:
            result.append(table)
    return result

def migrate_ocr_paths(mapping):
    db = ocr_path()
    if not db.exists():
        return 0
    changed = 0
    with sqlite3.connect(db) as con:
        for table in tables_with_column(con, "document_path"):
            for old, new in mapping.items():
                changed += con.execute(
                    f"UPDATE {table} SET document_path=? WHERE document_path=?", (new, old)
                ).rowcount
        con.commit()
    return changed

def reconcile_ocr_orphans():
    with sqlite3.connect(catalog_path()) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT d.path,d.name,d.total_pages,d.metadata_json,d.extraction_method,
              (SELECT COUNT(*) FROM fragments f WHERE f.document_path=d.path) fragment_count
            FROM documents d
            WHERE d.is_deleted=0 AND (
              d.extraction_method='ocr_pending' OR d.metadata_json LIKE '%"ocr_pending": true%'
            )
        """).fetchall()
    db = ocr_path()
    if not db.exists():
        return {"detected": len(rows), "requeued": 0, "unresolved": len(rows), "reason": "No existe cola OCR"}
    with sqlite3.connect(db) as con:
        candidate = None
        columns = set()
        for table in tables_with_column(con, "document_path"):
            cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
            if {"document_path", "document_name", "status"} <= cols:
                candidate, columns = table, cols
                break
        if candidate is None:
            return {"detected": len(rows), "requeued": 0, "unresolved": len(rows),
                    "reason": "Esquema OCR no reconocido de forma segura"}
        existing = {r[0] for r in con.execute(f"SELECT document_path FROM {candidate}")}
        requeued = unresolved = 0
        info = con.execute(f"PRAGMA table_info({candidate})").fetchall()
        required = {r[1] for r in info if int(r[3] or 0)==1 and r[4] is None and int(r[5] or 0)==0}
        for row in rows:
            if int(row["fragment_count"] or 0) > 0 or row["path"] in existing:
                continue
            values = {"document_path":row["path"], "document_name":row["name"], "status":"pending"}
            if "total_pages" in columns: values["total_pages"] = row["total_pages"]
            if "selected" in columns: values["selected"] = 1
            if "progress_page" in columns: values["progress_page"] = 0
            if "error" in columns: values["error"] = None
            if not required <= set(values):
                unresolved += 1
                continue
            keys = [k for k in values if k in columns]
            con.execute(
                f"INSERT INTO {candidate} ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",
                [values[k] for k in keys],
            )
            existing.add(row["path"])
            requeued += 1
        con.commit()
    return {"detected": len(rows), "requeued": requeued, "unresolved": unresolved, "table": candidate}

def migrate_qdrant(mapping, category, original_meta):
    from qdrant_client import QdrantClient, models
    client = QdrantClient(
        url=str(getattr(SETTINGS, "qdrant_url", "http://127.0.0.1:6333")),
        timeout=int(getattr(SETTINGS, "qdrant_timeout_seconds", 10)),
    )
    collection = str(getattr(SETTINGS, "collection_name", ""))
    docs = points = 0
    for i, (old, new) in enumerate(mapping.items(), 1):
        ids, offset = [], None
        while True:
            records, offset = client.scroll(
                collection_name=collection,
                scroll_filter=models.Filter(must=[
                    models.FieldCondition(key="document_path", match=models.MatchValue(value=old))
                ]),
                limit=256, offset=offset, with_payload=False, with_vectors=False,
            )
            ids.extend(r.id for r in records)
            if offset is None:
                break
        if ids:
            raw = original_meta.get(old, {}).get("metadata_json", "{}")
            meta = json.loads(rewrite_metadata(raw, category))
            client.set_payload(
                collection_name=collection,
                payload={"document_path":new, "category":category, "metadata":meta},
                points=ids, wait=True,
            )
            docs += 1
            points += len(ids)
        if i % 250 == 0:
            print(f"Qdrant: {i}/{len(mapping)} documentos revisados; {points} puntos actualizados")
    return {"updated_documents":docs, "updated_points":points}

def move_folders(plan):
    root = Path(plan.library_path).resolve()
    dest_root = root / TARGET_CATEGORY
    dest_root.mkdir(parents=True, exist_ok=True)
    moved = []
    for rule in plan.rules:
        if rule.enabled:
            source, dest = root / rule.source_name, dest_root / rule.source_name
            source.rename(dest)
            moved.append({"source":str(source.resolve()), "destination":str(dest.resolve())})
            print(f"Movida: {source.name}")
    return moved

def verify(mapping=None):
    mapping = mapping or {}
    with sqlite3.connect(catalog_path()) as con:
        active = con.execute("SELECT COUNT(*) FROM documents WHERE is_deleted=0").fetchone()[0]
        juris = con.execute("SELECT COUNT(*) FROM documents WHERE is_deleted=0 AND category='Jurisprudencia'").fetchone()[0]
        paths = [r[0] for r in con.execute("SELECT path FROM documents WHERE is_deleted=0")]
        old = sum(con.execute("SELECT COUNT(*) FROM documents WHERE path=? AND is_deleted=0",(p,)).fetchone()[0]
                  for p in mapping)
    missing = [p for p in paths if not Path(p).exists()]
    return {"documents_active":active, "jurisprudencia":juris, "missing_on_disk":len(missing),
            "missing_examples":missing[:20], "old_paths_remaining":old}

def apply(plan):
    mapping = build_path_map(plan)
    validate_plan(plan, mapping)
    print_plan(plan)
    print(f"\nDocumentos del catálogo a relocalizar: {len(mapping)}")
    backup_dir = create_backup()
    print(f"Backup: {backup_dir}")
    journal = {"version":"1.0","started_at":datetime.now().isoformat(timespec="seconds"),
               "backup_dir":str(backup_dir),"mapping":mapping,"moves":[],"status":"running"}
    journal_path().write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding="utf-8")
    started = time.monotonic()
    try:
        print("\n1/6 Moviendo carpetas...")
        journal["moves"] = move_folders(plan)
        journal_path().write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding="utf-8")
        print("2/6 Actualizando catálogo y FTS...")
        original_meta = migrate_catalog(mapping, TARGET_CATEGORY)
        print("3/6 Actualizando Knowledge...")
        kc = migrate_knowledge(mapping, TARGET_CATEGORY)
        print("4/6 Actualizando y reconciliando OCR...")
        oc = migrate_ocr_paths(mapping)
        orc = reconcile_ocr_orphans()
        print("5/6 Actualizando Qdrant sin embeddings...")
        qd = migrate_qdrant(mapping, TARGET_CATEGORY, original_meta)
        print("6/6 Invalidando snapshot...")
        if snapshot_path().exists():
            snapshot_path().unlink()
        result = verify(mapping)
        report = {
            "status":"completed","elapsed_seconds":round(time.monotonic()-started,3),
            "documents_relocated":len(mapping),"folders_moved":len(journal["moves"]),
            "knowledge_rows_changed":kc,"ocr_paths_changed":oc,
            "ocr_reconciliation":orc,"qdrant":qd,"verification":result,
            "backup_dir":str(backup_dir)
        }
        report_path().write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        journal["status"]="completed"
        journal_path().write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding="utf-8")
        print("\nMIGRACIÓN COMPLETADA")
        print(json.dumps(report,ensure_ascii=False,indent=2))
    except Exception as exc:
        journal["status"]="failed"; journal["error"]=str(exc)
        journal_path().write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding="utf-8")
        print("\nERROR. NO INICIES LEXIA.")
        print(r"Ejecutá: .\.venv\Scripts\python.exe tools\lexia_library_migrate.py --rollback")
        raise

def rollback():
    jp = journal_path()
    if not jp.exists():
        raise RuntimeError("No existe journal de migración.")
    journal = json.loads(jp.read_text(encoding="utf-8"))
    backup_dir = Path(journal["backup_dir"])
    manifest = json.loads((backup_dir/"backup_manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"].values():
        if item.get("backup") and Path(item["backup"]).exists():
            shutil.copy2(item["backup"], item["source"])
    for move in reversed(journal.get("moves", [])):
        src, dst = Path(move["source"]), Path(move["destination"])
        if dst.exists() and not src.exists():
            dst.rename(src)
    journal["status"]="rolled_back"
    journal["rolled_back_at"]=datetime.now().isoformat(timespec="seconds")
    jp.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Rollback físico + SQLite completado.")
    print("Si Qdrant ya había sido actualizado antes del error, ejecutá --verify y no inicies LexIA hasta revisar el reporte.")

def main():
    p = argparse.ArgumentParser(description="Migración controlada de biblioteca LexIA")
    p.add_argument("--prepare-plan",action="store_true")
    p.add_argument("--show-plan",action="store_true")
    p.add_argument("--apply",action="store_true")
    p.add_argument("--verify",action="store_true")
    p.add_argument("--rollback",action="store_true")
    p.add_argument("--plan",type=Path)
    a=p.parse_args()
    if a.prepare_plan:
        plan=build_plan(); path=save_plan(plan); print_plan(plan); print(f"\nPlan: {path}"); return 0
    if a.show_plan:
        print_plan(load_plan(a.plan)); return 0
    if a.verify:
        print(json.dumps(verify(),ensure_ascii=False,indent=2)); return 0
    if a.rollback:
        rollback(); return 0
    if a.apply:
        apply(load_plan(a.plan)); return 0
    p.print_help(); return 0

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3, sys
from collections import Counter
from pathlib import Path

def resolve_under_root(root, value):
    p = Path(value)
    return p if p.is_absolute() else (root / p).resolve()

def ro_connect(path):
    con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=r"D:\LexIA_2.3_DEV")
    ap.add_argument("--archivo")
    ap.add_argument("--muestra", type=int, default=30)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    sys.path.insert(0, str(root))
    from config.settings import SETTINGS
    from services.library_classification_tree import LibraryClassificationTree

    library_root = resolve_under_root(root, SETTINGS.library_path)
    catalog_path = resolve_under_root(root, SETTINGS.catalog_path)

    aliases = None
    config_path = root / "config" / "library_tree.json"
    if config_path.exists():
        aliases = json.loads(config_path.read_text(encoding="utf-8")).get("category_aliases")

    tree = LibraryClassificationTree(library_root, aliases)

    print("# LEXIA — LIBRARY CLASSIFICATION TREE 1.0 / FASE A")
    print("MODO: SOLO LECTURA")
    print("library_root:", library_root)
    print("catalogo:", catalog_path)
    print()

    if args.archivo:
        print(json.dumps(tree.classify(args.archivo).as_dict(), indent=2, ensure_ascii=False))
        print("\nVERIFICACION: no se modifico nada.")
        return

    con = ro_connect(catalog_path)
    try:
        rows = con.execute("""
            SELECT path,name,category
            FROM documents
            WHERE COALESCE(is_deleted,0)=0
            ORDER BY path
        """).fetchall()
    finally:
        con.close()

    mismatches = []
    projected = Counter()
    depths = Counter()
    invalid = 0

    for row in rows:
        c = tree.classify(row["path"])
        if not c.valid:
            invalid += 1
            continue
        projected[c.category] += 1
        depths[len(c.levels)] += 1
        current = str(row["category"] or "Sin categoría")
        if current != c.category:
            mismatches.append({
                "name": row["name"],
                "actual": current,
                "proyectada": c.category,
                "levels": list(c.levels),
                "relative_path": c.relative_path,
            })

    print("DOCUMENTOS ACTIVOS:", len(rows))
    print("RUTAS NO CLASIFICABLES:", invalid)
    print("DIFERENCIAS CATEGORIA ACTUAL / CARPETA:", len(mismatches))
    print("\nCATEGORIAS PROYECTADAS")
    for k,v in sorted(projected.items()):
        print(f"  {k}: {v}")

    print("\nPROFUNDIDAD")
    for k,v in sorted(depths.items()):
        print(f"  {k} subnivel(es): {v}")

    print(f"\nMUESTRA DIFERENCIAS (max {args.muestra})")
    for item in mismatches[:max(0,args.muestra)]:
        print(f"- {item['name']}")
        print(f"  actual: {item['actual']}")
        print(f"  proyectada: {item['proyectada']}")
        print(f"  niveles: {' / '.join(item['levels']) or '[ninguno]'}")
        print(f"  relativa: {item['relative_path']}")

    print("\nVERIFICACION")
    print("Catalogo modificado: NO")
    print("Qdrant modificado: NO")
    print("Knowledge modificado: NO")
    print("FTS modificado: NO")
    print("Archivos movidos: NO")

if __name__ == "__main__":
    main()

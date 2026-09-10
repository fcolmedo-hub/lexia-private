from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.standards_service import StandardsService


def main() -> int:
    parser = argparse.ArgumentParser(description="Consulta el diccionario de estándares jurídicos de LexIA.")
    parser.add_argument("texto", nargs="?", default="")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--tribunal", default="")
    parser.add_argument("--desde", default="")
    parser.add_argument("--hasta", default="")
    parser.add_argument("--speaker", default="")
    parser.add_argument("--treatment", default="")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--uid", default="", help="Muestra la vista completa de un estándar.")
    parser.add_argument("--grafo", default="", help="Muestra el grafo desde un standard_uid.")
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--investigacion", action="store_true", help="Devuelve fuentes estructuradas para Investigación.")
    args = parser.parse_args()

    service = StandardsService(args.db)
    if args.uid:
        result = service.get_standard(args.uid)
    elif args.grafo:
        result = service.graph(args.grafo, depth=args.depth)
    elif args.investigacion:
        result = service.investigation_sources(args.texto, limit=args.limit)
    else:
        result = service.search(
            text=args.texto,
            tags=args.tag,
            court=args.tribunal,
            date_from=args.desde,
            date_to=args.hasta,
            speaker=args.speaker,
            treatment=args.treatment,
            limit=args.limit,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

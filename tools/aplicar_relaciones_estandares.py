from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.standards_relation_engine import apply_relation_decisions, load_jsonl


DEFAULT_DB = REPO_ROOT / "runtime" / "standards" / "standards.sqlite3"
DEFAULT_CLASSIFICATIONS = (
    REPO_ROOT / "runtime" / "standards" / "canonicalization_batch" / "results" / "classifications.jsonl"
)
DEFAULT_AUDITS = [
    REPO_ROOT / "runtime" / "standards" / "canonicalization_audit_priority.jsonl",
    REPO_ROOT / "runtime" / "standards" / "canonicalization_audit_supports.jsonl",
    REPO_ROOT / "runtime" / "standards" / "canonicalization_audit_related.jsonl",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Registra decisiones de canonicalización y mantiene las relaciones del diccionario. "
            "Sin --apply sólo informa el plan."
        )
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--classifications", type=Path, default=DEFAULT_CLASSIFICATIONS)
    parser.add_argument(
        "--audit",
        type=Path,
        action="append",
        default=None,
        help="JSONL de revisión; puede repetirse. Si se omite, detecta las auditorías históricas.",
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not args.db.exists():
        parser.error(f"No existe SQLite: {args.db}")
    if not args.classifications.exists():
        parser.error(f"No existe classifications.jsonl: {args.classifications}")

    result = apply_relation_decisions(
        args.db,
        load_jsonl(args.classifications),
        audit_paths=args.audit if args.audit is not None else DEFAULT_AUDITS,
        classifier_model=args.model,
        source_file=str(args.classifications.resolve()),
        apply=args.apply,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["missing_standard"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

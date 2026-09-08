from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config.settings import SETTINGS
from services.standards_pipeline import StandardsPipeline


DEFAULT_DB = Path(SETTINGS.runtime_path) / "standards" / "standards.sqlite3"
DEFAULT_RUNS = Path(SETTINGS.runtime_path) / "standards" / "runs"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Motor incremental del Diccionario de Estándares Jurídicos de LexIA."
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--run-id", default=None)
    common.add_argument("--db", type=Path, default=DEFAULT_DB)
    common.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS)
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser(
        "prepare", parents=[common], help="Prepara fallos y lote V5 sin llamar a la API."
    )
    prepare.add_argument("--paths-file", type=Path, required=True)
    prepare.add_argument("--catalog", type=Path, default=Path(SETTINGS.catalog_path))
    prepare.add_argument("--model", default="gpt-5.6-luna")
    prepare.add_argument("--reasoning-effort", default="medium")
    prepare.add_argument("--max-output-tokens", type=int, default=4000)

    sub.add_parser("submit-extraction", parents=[common], help="Envía el lote V5; esta acción consume API.")
    sub.add_parser("collect-extraction", parents=[common], help="Recoge, valida, importa y prepara relaciones nuevas.")
    sub.add_parser("submit-relations", parents=[common], help="Envía relaciones nuevas; esta acción consume API.")
    sub.add_parser("collect-relations", parents=[common], help="Recoge y aplica relaciones como proposed.")
    sub.add_parser("status", parents=[common], help="Muestra el estado durable de la ejecución y la base.")
    sub.add_parser("batch-status", parents=[common], help="Consulta a la API el estado del lote activo.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command != "prepare" and not args.run_id:
        parser.error("--run-id es obligatorio para continuar una ejecución")
    pipeline = StandardsPipeline(
        repo_root=REPO_ROOT,
        db_path=args.db,
        runs_root=args.runs_root,
        run_id=args.run_id,
    )
    try:
        if args.command == "prepare":
            result = pipeline.prepare(
                catalog_path=args.catalog,
                paths_file=args.paths_file,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                max_output_tokens=args.max_output_tokens,
            )
        elif args.command == "submit-extraction":
            result = pipeline.submit_extraction()
        elif args.command == "collect-extraction":
            result = pipeline.collect_extraction()
        elif args.command == "submit-relations":
            result = pipeline.submit_relations()
        elif args.command == "collect-relations":
            result = pipeline.collect_relations()
        elif args.command == "batch-status":
            result = pipeline.batch_status()
        else:
            result = pipeline.summary()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

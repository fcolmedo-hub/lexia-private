from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_PROMPTS = REPO_ROOT / "runtime" / "standards_pilot" / "export_50" / "prompts.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "runtime" / "standards_pilot" / "api_test_5"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"JSON inválido en {path}, línea {lineno}: {exc}") from exc
            if not isinstance(row, dict):
                raise RuntimeError(f"Registro no-objeto en {path}, línea {lineno}")
            rows.append(row)
    return rows


def _extract_usage(response: Any) -> dict[str, int | None]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"input_tokens": None, "output_tokens": None, "total_tokens": None}
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def _validate_json_array(text: str) -> tuple[bool, Any, str | None]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return False, None, str(exc)
    if not isinstance(value, list):
        return False, value, "La respuesta JSON no es un array en la raíz"
    return True, value, None


def _existing_result_is_success(path: Path) -> tuple[bool, dict[str, Any] | None]:
    """Sólo considera reutilizable un resultado que haya completado una respuesta API."""
    if not path.exists():
        return False, None
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False, None
    if not isinstance(existing, dict):
        return False, None
    # Los resultados de error tienen error_type/error y no response_id.
    success = bool(existing.get("response_id")) and "error_type" not in existing
    return success, existing


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Envía los primeros fallos del piloto de estándares a OpenAI y guarda cada respuesta."
    )
    parser.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument(
        "--reasoning-effort",
        default="high",
        choices=("none", "low", "medium", "high", "xhigh", "max"),
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=12000,
        help="Tope de salida por fallo; evita respuestas accidentalmente desmesuradas.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Repite también resultados ya completados correctamente.",
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit debe ser mayor que cero")
    if not args.prompts.exists():
        parser.error(f"No existe el archivo de prompts: {args.prompts}")
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: falta la variable de entorno OPENAI_API_KEY.")
        print("En PowerShell, para esta sesión:  $env:OPENAI_API_KEY='su_clave_api'")
        return 2

    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: no está instalado el SDK oficial de OpenAI para Python.")
        print("Instálelo con:  python -m pip install --upgrade openai")
        return 2

    prompts = _load_jsonl(args.prompts)
    selected = prompts[: args.limit]
    if len(selected) < args.limit:
        print(f"AVISO: sólo hay {len(selected)} registros disponibles; se procesarán esos.")

    args.output.mkdir(parents=True, exist_ok=True)
    client = OpenAI()

    summary: dict[str, Any] = {
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "requested": len(selected),
        "completed": 0,
        "valid_json": 0,
        "failed": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "results": [],
    }

    for position, row in enumerate(selected, start=1):
        pilot_id = int(row.get("pilot_id", position))
        name = str(row.get("document_name", f"fallo_{pilot_id}"))
        prompt = str(row.get("prompt", ""))
        if not prompt.strip():
            print(f"[{position}/{len(selected)}] OMITIDO: prompt vacío ({name})")
            summary["failed"] += 1
            continue

        result_path = args.output / f"{pilot_id:03d}_resultado.json"
        raw_path = args.output / f"{pilot_id:03d}_respuesta.txt"

        existing_success, existing = _existing_result_is_success(result_path)
        if existing_success and not args.overwrite:
            print(f"[{position}/{len(selected)}] YA COMPLETADO: {name}")
            summary["completed"] += 1
            summary["valid_json"] += int(bool(existing.get("valid_json_array")))
            usage = existing.get("usage") if isinstance(existing.get("usage"), dict) else {}
            if isinstance(usage.get("input_tokens"), int):
                summary["input_tokens"] += usage["input_tokens"]
            if isinstance(usage.get("output_tokens"), int):
                summary["output_tokens"] += usage["output_tokens"]
            summary["results"].append(existing)
            continue
        if result_path.exists() and not existing_success:
            print(f"[{position}/{len(selected)}] Reintentando resultado previo fallido: {name}")

        print(f"[{position}/{len(selected)}] Enviando: {name}")
        started = time.perf_counter()
        try:
            response = client.responses.create(
                model=args.model,
                input=prompt,
                reasoning={"effort": args.reasoning_effort},
                max_output_tokens=args.max_output_tokens,
            )
            elapsed = round(time.perf_counter() - started, 2)
            text = (getattr(response, "output_text", "") or "").strip()
            usage = _extract_usage(response)
            valid_json, parsed, validation_error = _validate_json_array(text)

            raw_path.write_text(text + ("\n" if text else ""), encoding="utf-8")
            result = {
                "pilot_id": pilot_id,
                "document_name": name,
                "document_path": row.get("document_path"),
                "model": args.model,
                "reasoning_effort": args.reasoning_effort,
                "response_id": getattr(response, "id", None),
                "elapsed_seconds": elapsed,
                "usage": usage,
                "valid_json_array": valid_json,
                "validation_error": validation_error,
                "standards_count": len(parsed) if valid_json else None,
                "response_file": raw_path.name,
            }
            result_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            summary["completed"] += 1
            summary["valid_json"] += int(valid_json)
            if isinstance(usage.get("input_tokens"), int):
                summary["input_tokens"] += usage["input_tokens"]
            if isinstance(usage.get("output_tokens"), int):
                summary["output_tokens"] += usage["output_tokens"]
            summary["results"].append(result)

            status = "JSON OK" if valid_json else f"JSON INVÁLIDO: {validation_error}"
            count_text = f", estándares={len(parsed)}" if valid_json else ""
            print(
                f"    {status}{count_text}, entrada={usage.get('input_tokens')}, "
                f"salida={usage.get('output_tokens')}, {elapsed}s"
            )
        except Exception as exc:
            elapsed = round(time.perf_counter() - started, 2)
            summary["failed"] += 1
            error_result = {
                "pilot_id": pilot_id,
                "document_name": name,
                "document_path": row.get("document_path"),
                "model": args.model,
                "elapsed_seconds": elapsed,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            result_path.write_text(
                json.dumps(error_result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            summary["results"].append(error_result)
            print(f"    ERROR {type(exc).__name__}: {exc}")

            # Si no hay saldo, insistir con el resto no sirve y sólo ensucia la salida.
            error_text = str(exc).lower()
            if "credit_balance_exhausted" in error_text or "insufficient_quota" in error_text or "no credits remaining" in error_text:
                print("    Sin créditos API: se detiene la prueba.")
                break

    summary_path = args.output / "resumen.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nPrueba terminada.")
    print(json.dumps({
        "completed": summary["completed"],
        "valid_json": summary["valid_json"],
        "failed": summary["failed"],
        "input_tokens": summary["input_tokens"],
        "output_tokens": summary["output_tokens"],
        "output_dir": str(args.output.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

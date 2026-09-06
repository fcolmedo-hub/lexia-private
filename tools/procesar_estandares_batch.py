from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROMPTS = REPO_ROOT / "runtime" / "standards_pilot" / "export_50_v2" / "prompts.jsonl"
DEFAULT_WORKDIR = REPO_ROOT / "runtime" / "standards_pilot" / "batch_luna_v2"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"JSON inválido en {path}, línea {lineno}: {exc}") from exc
            if not isinstance(value, dict):
                raise RuntimeError(f"Registro no-objeto en {path}, línea {lineno}")
            rows.append(value)
    return rows


def output_text_from_response_body(body: dict[str, Any]) -> str:
    parts: list[str] = []
    output = body.get("output")
    if not isinstance(output, list):
        return ""
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "output_text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
    return "".join(parts).strip()


def require_sdk():
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Falta OPENAI_API_KEY en el entorno")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Falta el SDK oficial: python -m pip install --upgrade openai") from exc
    return OpenAI()


def cmd_prepare(args: argparse.Namespace) -> int:
    rows = load_jsonl(args.prompts)
    if args.limit is not None:
        if args.limit < 1:
            raise RuntimeError("--limit debe ser >= 1")
        rows = rows[: args.limit]
    if not rows:
        raise RuntimeError("No hay prompts para preparar")

    args.workdir.mkdir(parents=True, exist_ok=True)
    request_path = args.workdir / "batch_input.jsonl"
    manifest_path = args.workdir / "manifest.json"

    requests: list[str] = []
    manifest_rows: list[dict[str, Any]] = []
    for position, row in enumerate(rows, start=1):
        pilot_id = int(row.get("pilot_id", position))
        custom_id = f"pilot-{pilot_id:03d}"
        prompt = str(row.get("prompt") or "")
        if not prompt.strip():
            raise RuntimeError(f"Prompt vacío para pilot_id={pilot_id}")
        request = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/responses",
            "body": {
                "model": args.model,
                "input": prompt,
                "reasoning": {"effort": args.reasoning_effort},
                "max_output_tokens": args.max_output_tokens,
            },
        }
        requests.append(json.dumps(request, ensure_ascii=False, separators=(",", ":")))
        manifest_rows.append({
            "custom_id": custom_id,
            "pilot_id": pilot_id,
            "document_name": row.get("document_name"),
            "document_path": row.get("document_path"),
        })

    request_path.write_text("\n".join(requests) + "\n", encoding="utf-8")
    manifest = {
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "max_output_tokens": args.max_output_tokens,
        "requests": len(manifest_rows),
        "prompts_file": str(args.prompts.resolve()),
        "batch_input_file": request_path.name,
        "rows": manifest_rows,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "prepared": len(manifest_rows),
        "batch_input": str(request_path.resolve()),
        "workdir": str(args.workdir.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    client = require_sdk()
    request_path = args.workdir / "batch_input.jsonl"
    if not request_path.exists():
        raise RuntimeError(f"No existe {request_path}; ejecute primero prepare")
    with request_path.open("rb") as fh:
        uploaded = client.files.create(file=fh, purpose="batch")
    batch = client.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/responses",
        completion_window="24h",
        metadata={"purpose": "lexia-standards-v2"},
    )
    state = {
        "batch_id": batch.id,
        "input_file_id": uploaded.id,
        "status": batch.status,
        "endpoint": batch.endpoint,
        "completion_window": batch.completion_window,
    }
    args.workdir.mkdir(parents=True, exist_ok=True)
    (args.workdir / "batch_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def load_state(workdir: Path) -> dict[str, Any]:
    path = workdir / "batch_state.json"
    if not path.exists():
        raise RuntimeError(f"No existe {path}; ejecute primero submit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not value.get("batch_id"):
        raise RuntimeError("batch_state.json inválido")
    return value


def cmd_status(args: argparse.Namespace) -> int:
    client = require_sdk()
    state = load_state(args.workdir)
    batch = client.batches.retrieve(str(state["batch_id"]))
    result = {
        "batch_id": batch.id,
        "status": batch.status,
        "input_file_id": batch.input_file_id,
        "output_file_id": getattr(batch, "output_file_id", None),
        "error_file_id": getattr(batch, "error_file_id", None),
        "request_counts": (
            batch.request_counts.model_dump() if getattr(batch, "request_counts", None) is not None else None
        ),
    }
    state.update(result)
    (args.workdir / "batch_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    client = require_sdk()
    state = load_state(args.workdir)
    batch = client.batches.retrieve(str(state["batch_id"]))
    if batch.status != "completed":
        print(json.dumps({"batch_id": batch.id, "status": batch.status}, ensure_ascii=False, indent=2))
        return 2
    output_file_id = getattr(batch, "output_file_id", None)
    if not output_file_id:
        raise RuntimeError("Batch completado sin output_file_id")

    manifest = json.loads((args.workdir / "manifest.json").read_text(encoding="utf-8"))
    by_custom = {row["custom_id"]: row for row in manifest.get("rows", [])}

    raw_content = client.files.content(output_file_id).read()
    if isinstance(raw_content, bytes):
        raw_text = raw_content.decode("utf-8")
    else:
        raw_text = str(raw_content)
    (args.workdir / "batch_output.jsonl").write_text(raw_text, encoding="utf-8")

    results_dir = args.workdir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "completed": 0,
        "valid_json": 0,
        "failed": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "results": [],
    }

    for lineno, raw in enumerate(raw_text.splitlines(), start=1):
        if not raw.strip():
            continue
        record = json.loads(raw)
        custom_id = str(record.get("custom_id") or "")
        meta = by_custom.get(custom_id)
        if meta is None:
            summary["failed"] += 1
            summary["results"].append({"custom_id": custom_id, "error": "custom_id desconocido"})
            continue
        pilot_id = int(meta["pilot_id"])
        response_info = record.get("response") if isinstance(record.get("response"), dict) else {}
        status_code = response_info.get("status_code")
        body = response_info.get("body") if isinstance(response_info.get("body"), dict) else {}
        error = record.get("error")
        if status_code != 200 or error:
            summary["failed"] += 1
            item = {
                "pilot_id": pilot_id,
                "document_name": meta.get("document_name"),
                "status_code": status_code,
                "error": error or body,
            }
            (results_dir / f"{pilot_id:03d}_resultado.json").write_text(
                json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            summary["results"].append(item)
            continue

        text = output_text_from_response_body(body)
        valid = False
        parsed: Any = None
        validation_error: str | None = None
        try:
            parsed = json.loads(text)
            valid = isinstance(parsed, list)
            if not valid:
                validation_error = "La respuesta JSON no es un array en la raíz"
        except json.JSONDecodeError as exc:
            validation_error = str(exc)

        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if isinstance(input_tokens, int):
            summary["input_tokens"] += input_tokens
        if isinstance(output_tokens, int):
            summary["output_tokens"] += output_tokens

        (results_dir / f"{pilot_id:03d}_respuesta.txt").write_text(
            text + ("\n" if text else ""), encoding="utf-8"
        )
        item = {
            "pilot_id": pilot_id,
            "document_name": meta.get("document_name"),
            "document_path": meta.get("document_path"),
            "model": body.get("model") or manifest.get("model"),
            "reasoning_effort": manifest.get("reasoning_effort"),
            "response_id": body.get("id"),
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": usage.get("total_tokens"),
            },
            "valid_json_array": valid,
            "validation_error": validation_error,
            "standards_count": len(parsed) if valid else None,
            "response_file": f"{pilot_id:03d}_respuesta.txt",
        }
        (results_dir / f"{pilot_id:03d}_resultado.json").write_text(
            json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        summary["completed"] += 1
        summary["valid_json"] += int(valid)
        summary["results"].append(item)

    (results_dir / "resumen.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "completed": summary["completed"],
        "valid_json": summary["valid_json"],
        "failed": summary["failed"],
        "input_tokens": summary["input_tokens"],
        "output_tokens": summary["output_tokens"],
        "results_dir": str(results_dir.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepara, envía y recoge lotes Batch de extracción de estándares v2."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    prepare.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR)
    prepare.add_argument("--limit", type=int, default=None)
    prepare.add_argument("--model", default="gpt-5.6-luna")
    prepare.add_argument("--reasoning-effort", default="medium", choices=("none", "low", "medium", "high", "xhigh", "max"))
    prepare.add_argument("--max-output-tokens", type=int, default=4000)
    prepare.set_defaults(func=cmd_prepare)

    for name, func in (("submit", cmd_submit), ("status", cmd_status), ("collect", cmd_collect)):
        p = sub.add_parser(name)
        p.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR)
        p.set_defaults(func=func)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"ERROR {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

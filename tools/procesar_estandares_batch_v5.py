from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROMPTS = REPO_ROOT / "runtime" / "standards_pilot" / "export_50_v5" / "prompts.jsonl"
DEFAULT_WORKDIR = REPO_ROOT / "runtime" / "standards_pilot" / "batch_luna_v5"

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "standards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string"},
                    "speaker": {"type": "string", "enum": ["mayoria", "disidencia", "procurador", "tribunal_anterior"]},
                    "source_speaker": {"type": "string", "enum": ["mayoria", "disidencia", "procurador", "tribunal_anterior"]},
                    "treatment": {"type": "string", "enum": ["adopta", "propone", "cita", "rechaza"]},
                    "conditions": {"type": "array", "items": {"type": "string"}},
                    "consequence": {"type": ["string", "null"]},
                    "exceptions": {"type": "array", "items": {"type": "string"}},
                    "evidence": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "unit_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                            },
                            "required": ["unit_ids"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["statement", "speaker", "source_speaker", "treatment", "conditions", "consequence", "exceptions", "evidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["standards"],
    "additionalProperties": False,
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise RuntimeError(f"Registro no-objeto en {path}, línea {lineno}")
            rows.append(value)
    return rows


def require_sdk():
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Falta OPENAI_API_KEY en el entorno")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Falta el SDK oficial: python -m pip install --upgrade openai") from exc
    return OpenAI()


def output_text_from_body(body: dict[str, Any]) -> str:
    parts: list[str] = []
    output = body.get("output") if isinstance(body.get("output"), list) else []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content") if isinstance(item.get("content"), list) else []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "output_text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
    return "".join(parts).strip()


def parse_pilot_ids(value: str | None) -> list[int] | None:
    if not value:
        return None
    result: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        pid = int(part)
        if pid < 1:
            raise RuntimeError("--pilot-ids debe contener IDs >= 1")
        if pid not in result:
            result.append(pid)
    return result or None


def select_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    pilot_ids = parse_pilot_ids(args.pilot_ids)
    if pilot_ids is not None:
        if args.skip != 0 or args.limit is not None:
            raise RuntimeError("Use --pilot-ids o --skip/--limit, no ambos")
        by_id = {int(row.get("pilot_id")): row for row in rows if row.get("pilot_id") is not None}
        missing = [pid for pid in pilot_ids if pid not in by_id]
        if missing:
            raise RuntimeError(f"pilot_id inexistentes: {missing}")
        return [by_id[pid] for pid in pilot_ids]
    if args.skip < 0:
        raise RuntimeError("--skip debe ser >= 0")
    selected = rows[args.skip:]
    if args.limit is not None:
        if args.limit < 1:
            raise RuntimeError("--limit debe ser >= 1")
        selected = selected[:args.limit]
    return selected


def cmd_prepare(args: argparse.Namespace) -> int:
    rows = select_rows(load_jsonl(args.prompts), args)
    if not rows:
        raise RuntimeError("No hay prompts para preparar")
    args.workdir.mkdir(parents=True, exist_ok=True)
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
                "text": {"format": {"type": "json_schema", "name": "lexia_standards_v5", "strict": True, "schema": SCHEMA}},
            },
        }
        requests.append(json.dumps(request, ensure_ascii=False, separators=(",", ":")))
        manifest_rows.append({
            "custom_id": custom_id,
            "pilot_id": pilot_id,
            "document_name": row.get("document_name"),
            "document_path": row.get("document_path"),
        })
    (args.workdir / "batch_input.jsonl").write_text("\n".join(requests) + "\n", encoding="utf-8")
    manifest = {
        "version": 5,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "max_output_tokens": args.max_output_tokens,
        "structured_outputs": True,
        "evidence_mode": "deterministic_unit_ids",
        "requests": len(manifest_rows),
        "prompts_file": str(args.prompts.resolve()),
        "rows": manifest_rows,
    }
    (args.workdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "prepared": len(manifest_rows),
        "pilot_ids": [x["pilot_id"] for x in manifest_rows],
        "structured_outputs": True,
        "evidence_mode": "deterministic_unit_ids",
        "workdir": str(args.workdir.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


def load_state(workdir: Path) -> dict[str, Any]:
    path = workdir / "batch_state.json"
    if not path.exists():
        raise RuntimeError(f"No existe {path}; ejecute primero submit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not value.get("batch_id"):
        raise RuntimeError("batch_state.json inválido")
    return value


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
        metadata={"purpose": "lexia-standards-v5"},
    )
    state = {
        "batch_id": batch.id,
        "input_file_id": uploaded.id,
        "status": batch.status,
        "endpoint": batch.endpoint,
        "completion_window": batch.completion_window,
    }
    (args.workdir / "batch_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


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
        "request_counts": batch.request_counts.model_dump() if getattr(batch, "request_counts", None) is not None else None,
    }
    state.update(result)
    (args.workdir / "batch_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
    raw_text = raw_content.decode("utf-8") if isinstance(raw_content, bytes) else str(raw_content)
    (args.workdir / "batch_output.jsonl").write_text(raw_text, encoding="utf-8")
    results_dir = args.workdir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    summary = {"completed": 0, "valid_json": 0, "failed": 0, "input_tokens": 0, "output_tokens": 0, "results": []}
    for raw in raw_text.splitlines():
        if not raw.strip():
            continue
        record = json.loads(raw)
        custom_id = str(record.get("custom_id") or "")
        meta = by_custom.get(custom_id)
        if meta is None:
            summary["failed"] += 1
            continue
        pilot_id = int(meta["pilot_id"])
        response_info = record.get("response") if isinstance(record.get("response"), dict) else {}
        status_code = response_info.get("status_code")
        body = response_info.get("body") if isinstance(response_info.get("body"), dict) else {}
        error = record.get("error")
        if status_code != 200 or error:
            summary["failed"] += 1
            item = {"pilot_id": pilot_id, "document_name": meta.get("document_name"), "status_code": status_code, "error": error or body}
            (results_dir / f"{pilot_id:03d}_resultado.json").write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            summary["results"].append(item)
            continue
        text = output_text_from_body(body)
        valid = False
        standards_count: int | None = None
        validation_error: str | None = None
        try:
            parsed = json.loads(text)
            valid = isinstance(parsed, dict) and isinstance(parsed.get("standards"), list)
            if valid:
                standards_count = len(parsed["standards"])
            else:
                validation_error = "La respuesta v5 no tiene standards=array"
        except json.JSONDecodeError as exc:
            validation_error = str(exc)
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        if isinstance(usage.get("input_tokens"), int):
            summary["input_tokens"] += usage["input_tokens"]
        if isinstance(usage.get("output_tokens"), int):
            summary["output_tokens"] += usage["output_tokens"]
        (results_dir / f"{pilot_id:03d}_respuesta.txt").write_text(text + ("\n" if text else ""), encoding="utf-8")
        item = {
            "pilot_id": pilot_id,
            "document_name": meta.get("document_name"),
            "document_path": meta.get("document_path"),
            "model": body.get("model") or manifest.get("model"),
            "reasoning_effort": manifest.get("reasoning_effort"),
            "response_id": body.get("id"),
            "usage": {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "total_tokens": usage.get("total_tokens")},
            "valid_json_array": valid,
            "validation_error": validation_error,
            "standards_count": standards_count,
            "response_file": f"{pilot_id:03d}_respuesta.txt",
        }
        (results_dir / f"{pilot_id:03d}_resultado.json").write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary["completed"] += 1
        summary["valid_json"] += int(valid)
        summary["results"].append(item)
    (results_dir / "resumen.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
    parser = argparse.ArgumentParser(description="Batch v5: Structured Outputs + evidencia por IDs deterministas de unidades.")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    prepare.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR)
    prepare.add_argument("--skip", type=int, default=0)
    prepare.add_argument("--limit", type=int, default=None)
    prepare.add_argument("--pilot-ids", default=None, help="Lista separada por comas, ej. 9,16,38,46,50")
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
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"ERROR {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATES = REPO_ROOT / "runtime" / "standards" / "canonicalization_candidates.jsonl"
DEFAULT_WORKDIR = REPO_ROOT / "runtime" / "standards" / "canonicalization_batch"

RELATIONS = ["none", "duplicate_of", "specializes", "generalizes", "exception_to", "related_to", "supports", "contradicts"]
DIRECTIONS = ["a_to_b", "b_to_a", "symmetric", "not_applicable"]
CONFIDENCE = ["high", "medium", "low"]

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "relation": {"type": "string", "enum": RELATIONS},
        "direction": {"type": "string", "enum": DIRECTIONS},
        "confidence": {"type": "string", "enum": CONFIDENCE},
        "rationale": {"type": "string"},
    },
    "required": ["relation", "direction", "confidence", "rationale"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """Clasifica la relación jurídica entre DOS estándares extraídos de jurisprudencia.
No determines si los estándares son correctos en abstracto: compara exclusivamente las dos proposiciones y sus citas.
Sé conservador. Si no existe una relación jurídica suficientemente concreta, devuelve relation=none.
No uses similitud temática como sinónimo de relación.

Relaciones:
- duplicate_of: sustancialmente la misma regla jurídica, aunque cambie la redacción.
- specializes: el estándar de origen es una formulación más específica o estrecha del estándar de destino.
- generalizes: el estándar de origen es una formulación más general o amplia del estándar de destino.
- exception_to: el estándar de origen establece una excepción o límite operativo al estándar de destino.
- related_to: existe conexión jurídica directa, pero ninguna de las relaciones anteriores describe correctamente el vínculo.
- supports: el estándar de origen proporciona una premisa jurídica que apoya la aplicación o conclusión del estándar de destino.
- contradicts: ambos estándares son incompatibles en su contenido normativo para un mismo supuesto relevante.
- none: no hay relación jurídica concreta suficiente.

Dirección:
- a_to_b: A es duplicate_of/specializes/generalizes/exception_to/supports respecto de B.
- b_to_a: B lo es respecto de A.
- symmetric: para duplicate_of, related_to o contradicts cuando la relación no requiere dirección.
- not_applicable: úsalo con none.

Reglas de decisión:
1. Prefiere none antes que inventar vínculos.
2. No marques duplicate_of porque compartan ley, instituto, hechos o vocabulario.
3. Dos reglas autónomas del mismo fallo normalmente no son duplicate_of.
4. Para specializes/generalizes debe existir verdadera inclusión normativa entre ámbitos de aplicación.
5. Para exception_to debe poder formularse: 'rige B, salvo en el supuesto A'.
6. Para supports debe existir una relación inferencial jurídica clara, no mera proximidad temática.
7. Usa las citas sólo como apoyo para entender el alcance; no reconstruyas texto ausente.
8. Rationale breve, máximo dos oraciones.
"""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
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
    for item in body.get("output", []) if isinstance(body.get("output"), list) else []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for block in item.get("content", []) if isinstance(item.get("content"), list) else []:
            if isinstance(block, dict) and block.get("type") == "output_text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
    return "".join(parts).strip()


def candidate_prompt(row: dict[str, Any]) -> str:
    a = row.get("a") if isinstance(row.get("a"), dict) else {}
    b = row.get("b") if isinstance(row.get("b"), dict) else {}
    payload = {
        "candidate_id": row.get("candidate_id"),
        "same_document": row.get("same_document"),
        "A": {
            "standard_uid": a.get("standard_uid"),
            "statement": a.get("statement"),
            "speaker": a.get("speaker"),
            "source_speaker": a.get("source_speaker"),
            "treatment": a.get("treatment"),
            "document_name": a.get("document_name"),
            "court": a.get("court"),
            "judgment_date": a.get("judgment_date"),
            "evidence_excerpt": a.get("evidence_excerpt"),
        },
        "B": {
            "standard_uid": b.get("standard_uid"),
            "statement": b.get("statement"),
            "speaker": b.get("speaker"),
            "source_speaker": b.get("source_speaker"),
            "treatment": b.get("treatment"),
            "document_name": b.get("document_name"),
            "court": b.get("court"),
            "judgment_date": b.get("judgment_date"),
            "evidence_excerpt": b.get("evidence_excerpt"),
        },
    }
    return SYSTEM_PROMPT + "\nPAR A CLASIFICAR:\n" + json.dumps(payload, ensure_ascii=False, indent=2)


def load_state(workdir: Path) -> dict[str, Any]:
    path = workdir / "batch_state.json"
    if not path.exists():
        raise RuntimeError(f"No existe {path}; ejecute primero submit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not value.get("batch_id"):
        raise RuntimeError("batch_state.json inválido")
    return value


def cmd_prepare(args: argparse.Namespace) -> int:
    rows = load_jsonl(args.candidates)
    if args.limit is not None:
        rows = rows[: args.limit]
    if not rows:
        raise RuntimeError("No hay candidatos para preparar")
    args.workdir.mkdir(parents=True, exist_ok=True)
    requests: list[str] = []
    manifest_rows: list[dict[str, Any]] = []
    for pos, row in enumerate(rows, 1):
        candidate_id = str(row.get("candidate_id") or f"candidate-{pos:04d}")
        custom_id = candidate_id
        body = {
            "model": args.model,
            "input": candidate_prompt(row),
            "reasoning": {"effort": args.reasoning_effort},
            "max_output_tokens": args.max_output_tokens,
            "text": {"format": {"type": "json_schema", "name": "lexia_relation_classifier", "strict": True, "schema": SCHEMA}},
        }
        requests.append(json.dumps({"custom_id": custom_id, "method": "POST", "url": "/v1/responses", "body": body}, ensure_ascii=False, separators=(",", ":")))
        manifest_rows.append({
            "custom_id": custom_id,
            "candidate_id": candidate_id,
            "a_uid": row.get("a", {}).get("standard_uid") if isinstance(row.get("a"), dict) else None,
            "b_uid": row.get("b", {}).get("standard_uid") if isinstance(row.get("b"), dict) else None,
            "same_document": row.get("same_document"),
            "score": row.get("score"),
        })
    (args.workdir / "batch_input.jsonl").write_text("\n".join(requests) + "\n", encoding="utf-8")
    manifest = {
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "requests": len(manifest_rows),
        "candidates_file": str(args.candidates.resolve()),
        "rows": manifest_rows,
    }
    (args.workdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"prepared": len(manifest_rows), "workdir": str(args.workdir.resolve())}, ensure_ascii=False, indent=2))
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    client = require_sdk()
    request_path = args.workdir / "batch_input.jsonl"
    if not request_path.exists():
        raise RuntimeError(f"No existe {request_path}; ejecute primero prepare")
    with request_path.open("rb") as fh:
        uploaded = client.files.create(file=fh, purpose="batch")
    batch = client.batches.create(input_file_id=uploaded.id, endpoint="/v1/responses", completion_window="24h", metadata={"purpose": "lexia-standards-canonicalization"})
    state = {"batch_id": batch.id, "input_file_id": uploaded.id, "status": batch.status}
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
    results: list[dict[str, Any]] = []
    summary = {"completed": 0, "valid_json": 0, "failed": 0, "input_tokens": 0, "output_tokens": 0, "relations": {name: 0 for name in RELATIONS}}
    for raw in raw_text.splitlines():
        if not raw.strip():
            continue
        record = json.loads(raw)
        custom_id = str(record.get("custom_id") or "")
        meta = by_custom.get(custom_id)
        response_info = record.get("response") if isinstance(record.get("response"), dict) else {}
        body = response_info.get("body") if isinstance(response_info.get("body"), dict) else {}
        if meta is None or response_info.get("status_code") != 200 or record.get("error"):
            summary["failed"] += 1
            continue
        text = output_text_from_body(body)
        try:
            parsed = json.loads(text)
            valid = isinstance(parsed, dict) and parsed.get("relation") in RELATIONS and parsed.get("direction") in DIRECTIONS and parsed.get("confidence") in CONFIDENCE
        except json.JSONDecodeError:
            parsed = {}
            valid = False
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        summary["input_tokens"] += int(usage.get("input_tokens") or 0)
        summary["output_tokens"] += int(usage.get("output_tokens") or 0)
        item = dict(meta)
        item.update({
            "valid": valid,
            "relation": parsed.get("relation"),
            "direction": parsed.get("direction"),
            "confidence": parsed.get("confidence"),
            "rationale": parsed.get("rationale"),
            "response_id": body.get("id"),
        })
        results.append(item)
        summary["completed"] += 1
        if valid:
            summary["valid_json"] += 1
            summary["relations"][str(parsed["relation"])] += 1
    results_dir = args.workdir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "classifications.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in results) + ("\n" if results else ""), encoding="utf-8")
    (results_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 and summary["valid_json"] == summary["completed"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clasifica candidatos de canonicalización mediante Batch + Structured Outputs.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    p.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--model", default="gpt-5.6-luna")
    p.add_argument("--reasoning-effort", default="medium")
    p.add_argument("--max-output-tokens", type=int, default=700)
    p.set_defaults(func=cmd_prepare)
    for name, func in (("submit", cmd_submit), ("status", cmd_status), ("collect", cmd_collect)):
        q = sub.add_parser(name)
        q.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR)
        q.set_defaults(func=func)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

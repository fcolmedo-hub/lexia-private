from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "runtime" / "standards" / "standards.sqlite3"
DEFAULT_CLASSIFICATIONS = REPO_ROOT / "runtime" / "standards" / "canonicalization_batch" / "results" / "classifications.jsonl"
DEFAULT_AUDITS = [
    REPO_ROOT / "runtime" / "standards" / "canonicalization_audit_priority.jsonl",
    REPO_ROOT / "runtime" / "standards" / "canonicalization_audit_supports.jsonl",
    REPO_ROOT / "runtime" / "standards" / "canonicalization_audit_related.jsonl",
]

RELATIONS = {
    "duplicate_of",
    "specializes",
    "generalizes",
    "exception_to",
    "related_to",
    "supports",
    "contradicts",
}
DIRECTIONS = {"a_to_b", "b_to_a", "symmetric", "not_applicable"}


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


def load_audit_overrides(paths: list[Path]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    overrides: dict[str, dict[str, Any]] = {}
    used_files: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        used_files.append(str(path.resolve()))
        for row in load_jsonl(path):
            if row.get("audit_status") != "reviewed":
                continue
            candidate_id = str(row.get("candidate_id") or "").strip()
            if not candidate_id:
                continue
            relation = row.get("audited_relation")
            direction = row.get("audited_direction")
            if relation is None or direction is None:
                raise RuntimeError(f"Auditoría revisada incompleta para {candidate_id} en {path}")
            overrides[candidate_id] = {
                "relation": str(relation),
                "direction": str(direction),
                "comment": row.get("audit_comment"),
                "source": str(path.resolve()),
            }
    return overrides, used_files


def resolve_endpoints(a_uid: str, b_uid: str, relation: str, direction: str) -> tuple[str, str]:
    if direction == "a_to_b":
        return a_uid, b_uid
    if direction == "b_to_a":
        return b_uid, a_uid
    if direction == "symmetric":
        return tuple(sorted((a_uid, b_uid)))  # type: ignore[return-value]
    raise RuntimeError(f"Dirección {direction!r} inválida para relación {relation!r}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Cierra el piloto de canonicalización: aplica auditorías ya revisadas, "
            "descarta relation=none y persiste las demás relaciones como proposed."
        )
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--classifications", type=Path, default=DEFAULT_CLASSIFICATIONS)
    parser.add_argument("--audit", type=Path, action="append", default=None,
                        help="JSONL de auditoría; puede repetirse. Por defecto usa priority/supports/related si existen.")
    parser.add_argument("--apply", action="store_true", help="Escribe en SQLite. Sin esta opción sólo informa el plan.")
    args = parser.parse_args()

    if not args.classifications.exists():
        parser.error(f"No existe classifications.jsonl: {args.classifications}")
    if not args.db.exists():
        parser.error(f"No existe SQLite: {args.db}")

    audit_paths = list(args.audit) if args.audit else list(DEFAULT_AUDITS)
    overrides, audit_files = load_audit_overrides(audit_paths)
    classifications = load_jsonl(args.classifications)

    planned: list[dict[str, Any]] = []
    skipped_none = 0
    skipped_invalid = 0
    overridden = 0

    for row in classifications:
        candidate_id = str(row.get("candidate_id") or row.get("custom_id") or "").strip()
        a_uid = str(row.get("a_uid") or "").strip()
        b_uid = str(row.get("b_uid") or "").strip()
        relation = str(row.get("relation") or "").strip()
        direction = str(row.get("direction") or "").strip()
        rationale = str(row.get("rationale") or "").strip()

        override = overrides.get(candidate_id)
        if override is not None:
            relation = override["relation"]
            direction = override["direction"]
            if override.get("comment"):
                rationale = str(override["comment"])
            overridden += 1

        if relation == "none":
            skipped_none += 1
            continue
        if relation not in RELATIONS or direction not in DIRECTIONS or direction == "not_applicable":
            skipped_invalid += 1
            continue
        if not a_uid or not b_uid or a_uid == b_uid:
            skipped_invalid += 1
            continue

        from_uid, to_uid = resolve_endpoints(a_uid, b_uid, relation, direction)
        planned.append({
            "candidate_id": candidate_id,
            "from_standard_uid": from_uid,
            "to_standard_uid": to_uid,
            "relation_type": relation,
            "rationale": rationale,
            "audited": override is not None,
        })

    # Evita duplicados exactos producidos por pares simétricos o re-clasificaciones.
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in planned:
        key = (item["from_standard_uid"], item["to_standard_uid"], item["relation_type"])
        current = deduped.get(key)
        if current is None or (item["audited"] and not current["audited"]):
            deduped[key] = item
    planned = list(deduped.values())

    conn = sqlite3.connect(args.db)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        standard_uids = {str(row[0]) for row in conn.execute("SELECT standard_uid FROM standards")}
        ready: list[dict[str, Any]] = []
        missing_standard: list[dict[str, Any]] = []
        for item in planned:
            if item["from_standard_uid"] not in standard_uids or item["to_standard_uid"] not in standard_uids:
                missing_standard.append(item)
            else:
                ready.append(item)

        result = {
            "mode": "apply" if args.apply else "dry_run",
            "classifications": len(classifications),
            "audit_overrides_loaded": len(overrides),
            "audit_files_used": audit_files,
            "overrides_applied": overridden,
            "skipped_none": skipped_none,
            "skipped_invalid": skipped_invalid,
            "planned_relations": len(planned),
            "ready_for_sqlite": len(ready),
            "missing_standard": len(missing_standard),
            "relation_counts": {},
        }
        counts: dict[str, int] = {}
        for item in ready:
            counts[item["relation_type"]] = counts.get(item["relation_type"], 0) + 1
        result["relation_counts"] = dict(sorted(counts.items()))

        if missing_standard:
            result["missing_examples"] = [
                {
                    "candidate_id": x["candidate_id"],
                    "from": x["from_standard_uid"],
                    "to": x["to_standard_uid"],
                    "relation": x["relation_type"],
                }
                for x in missing_standard[:10]
            ]

        if args.apply:
            inserted_or_updated = 0
            preserved_terminal = 0
            with conn:
                for item in ready:
                    existing = conn.execute(
                        """
                        SELECT relation_id, status FROM relations
                        WHERE from_standard_uid=? AND to_standard_uid=? AND relation_type=?
                        """,
                        (item["from_standard_uid"], item["to_standard_uid"], item["relation_type"]),
                    ).fetchone()
                    if existing is not None and str(existing[1]) in {"confirmed", "rejected"}:
                        preserved_terminal += 1
                        continue
                    conn.execute(
                        """
                        INSERT INTO relations(
                            from_standard_uid, to_standard_uid, relation_type, status, rationale
                        ) VALUES(?,?,?,?,?)
                        ON CONFLICT(from_standard_uid, to_standard_uid, relation_type)
                        DO UPDATE SET
                            rationale=excluded.rationale,
                            status=CASE
                                WHEN relations.status IN ('confirmed','rejected') THEN relations.status
                                ELSE 'proposed'
                            END
                        """,
                        (
                            item["from_standard_uid"],
                            item["to_standard_uid"],
                            item["relation_type"],
                            "proposed",
                            item["rationale"],
                        ),
                    )
                    inserted_or_updated += 1
            result["sqlite_inserted_or_updated"] = inserted_or_updated
            result["sqlite_preserved_confirmed_or_rejected"] = preserved_terminal
            result["sqlite_relations_total"] = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
            result["sqlite_relations_proposed"] = conn.execute(
                "SELECT COUNT(*) FROM relations WHERE status='proposed'"
            ).fetchone()[0]

        print(json.dumps(result, ensure_ascii=False, indent=2))
        if missing_standard:
            return 2
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

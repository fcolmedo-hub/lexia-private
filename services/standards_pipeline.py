from __future__ import annotations

import json
import sqlite3
import uuid
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.standards_relation_engine import apply_relation_decisions, load_jsonl
from tools.exportar_estandares_piloto import (
    _load_requested_paths,
    export_documents,
)
from tools.importar_estandares_sqlite import import_validated_run
from tools.preparar_canonicalizacion_estandares import build_candidates
from tools.preparar_estandares_v2 import dump_jsonl
from tools.preparar_estandares_v5 import prepare_document_v5
from tools.procesar_canonicalizacion_batch import (
    cmd_collect as collect_relation_batch,
    cmd_prepare as prepare_relation_batch,
    cmd_status as status_relation_batch,
    cmd_submit as submit_relation_batch,
)
from tools.procesar_estandares_batch_v5 import (
    cmd_collect as collect_extraction_batch,
    cmd_prepare as prepare_extraction_batch,
    cmd_status as status_extraction_batch,
    cmd_submit as submit_extraction_batch,
)
from tools.validar_estandares_v5 import validate_result


class StandardsPipeline:
    """Flujo incremental y reanudable para alimentar el diccionario.

    Las llamadas que generan costo (submit) son siempre explícitas. Las demás
    etapas son locales, idempotentes y dejan un estado durable por ejecución.
    """

    def __init__(
        self,
        *,
        repo_root: Path,
        db_path: Path,
        runs_root: Path,
        run_id: str | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.db_path = db_path.resolve()
        self.runs_root = runs_root.resolve()
        self.run_id = run_id or self._new_run_id()
        self.run_dir = self.runs_root / self.run_id
        self.state_path = self.run_dir / "state.json"

    @staticmethod
    def _new_run_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"standards-{timestamp}-{uuid.uuid4().hex[:6]}"

    def load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            raise RuntimeError(f"No existe la ejecución {self.run_id}")
        value = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise RuntimeError(f"Estado inválido: {self.state_path}")
        return value

    def _save_state(self, state: dict[str, Any]) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        state["run_id"] = self.run_id
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        temporary = self.state_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.state_path)

    def _transition(self, stage: str, **updates: Any) -> dict[str, Any]:
        state = self.load_state()
        state.update(updates)
        state["stage"] = stage
        self._save_state(state)
        return state

    def prepare(
        self,
        *,
        catalog_path: Path,
        paths_file: Path,
        model: str,
        reasoning_effort: str,
        max_output_tokens: int = 4000,
    ) -> dict[str, Any]:
        if self.state_path.exists():
            raise RuntimeError(f"La ejecución ya existe: {self.run_id}")
        if not catalog_path.exists():
            raise FileNotFoundError(f"No existe el catálogo: {catalog_path}")
        if not paths_file.exists():
            raise FileNotFoundError(f"No existe la selección: {paths_file}")

        # Una base nacida antes del motor incremental puede tener relaciones
        # positivas pero no las decisiones `none`. Continuar así volvería a
        # clasificar y cobrar pares ya resueltos; se bloquea hasta registrar
        # una vez las clasificaciones históricas con el migrador genérico.
        if self.db_path.exists():
            conn = sqlite3.connect(self.db_path)
            try:
                has_relations = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='relations'"
                ).fetchone()
                relation_count = int(conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]) if has_relations else 0
                has_decisions = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='relation_decisions'"
                ).fetchone()
                decision_count = int(conn.execute("SELECT COUNT(*) FROM relation_decisions").fetchone()[0]) if has_decisions else 0
            finally:
                conn.close()
            if relation_count and not decision_count:
                raise RuntimeError(
                    "La base contiene relaciones históricas sin relation_decisions. "
                    "Ejecutá una sola vez tools/aplicar_relaciones_estandares.py --apply "
                    "antes de iniciar nuevos lotes."
                )

        requested_paths, encoding = _load_requested_paths(paths_file)
        if not requested_paths:
            raise RuntimeError("La selección de fallos está vacía")
        documents, missing = export_documents(catalog_path, requested_paths)
        if missing:
            preview = "\n".join(f"- {path}" for path in missing[:20])
            raise RuntimeError(
                "Hay fallos no indexados como Jurisprudencia o sin fragmentos:\n" + preview
            )

        source_dir = self.run_dir / "source"
        prepared_dir = self.run_dir / "prepared_v5"
        extraction_dir = self.run_dir / "extraction_batch"
        source_dir.mkdir(parents=True, exist_ok=True)
        prepared_dir.mkdir(parents=True, exist_ok=True)

        source_rows: list[dict[str, Any]] = []
        for pilot_id, document in enumerate(documents, start=1):
            source_rows.append({
                "pilot_id": pilot_id,
                "document_path": document.path,
                "document_name": document.name,
                "total_pages": document.total_pages,
                "metadata": document.metadata,
                "fragments": document.fragments,
            })
        dump_jsonl(source_dir / "fallos.jsonl", source_rows)

        prompt_template = (
            self.repo_root / "prompt" / "standards_extraction_v5.txt"
        ).read_text(encoding="utf-8").rstrip()
        prepared_rows: list[dict[str, Any]] = []
        prompt_rows: list[dict[str, Any]] = []
        units = 0
        for row in source_rows:
            prepared, document_text = prepare_document_v5(row)
            prepared_rows.append(prepared)
            units += sum(
                len(fragment.get("units", []))
                for fragment in prepared.get("fragments", [])
            )
            prompt_rows.append({
                "pilot_id": prepared["pilot_id"],
                "document_path": prepared["document_path"],
                "document_name": prepared["document_name"],
                "prompt": prompt_template + "\n\n" + document_text,
            })
        dump_jsonl(prepared_dir / "fallos.jsonl", prepared_rows)
        dump_jsonl(prepared_dir / "prompts.jsonl", prompt_rows)

        self.run_dir.mkdir(parents=True, exist_ok=True)
        initial = {
            "stage": "preparing",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "catalog_path": str(catalog_path.resolve()),
            "paths_file": str(paths_file.resolve()),
            "selection_encoding": encoding,
            "model": model,
            "reasoning_effort": reasoning_effort,
            "documents": len(prepared_rows),
            "fragments": sum(len(row.get("fragments", [])) for row in prepared_rows),
            "units": units,
        }
        self._save_state(initial)

        code = prepare_extraction_batch(Namespace(
            prompts=prepared_dir / "prompts.jsonl",
            workdir=extraction_dir,
            skip=0,
            limit=None,
            pilot_ids=None,
            model=model,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
        ))
        if code != 0:
            raise RuntimeError("No se pudo preparar el lote de extracción")
        return self._transition("extraction_ready_to_submit")

    def submit_extraction(self) -> dict[str, Any]:
        state = self.load_state()
        if state.get("stage") != "extraction_ready_to_submit":
            raise RuntimeError("La extracción no está lista para enviar")
        code = submit_extraction_batch(Namespace(workdir=self.run_dir / "extraction_batch"))
        if code != 0:
            raise RuntimeError("No se pudo enviar el lote de extracción")
        return self._transition("extraction_submitted")

    def batch_status(self) -> dict[str, Any]:
        state = self.load_state()
        stage = str(state.get("stage") or "")
        if stage.startswith("extraction_"):
            code = status_extraction_batch(Namespace(workdir=self.run_dir / "extraction_batch"))
        elif stage.startswith("relations_"):
            code = status_relation_batch(Namespace(workdir=self.run_dir / "relations_batch"))
        else:
            return state
        if code != 0:
            raise RuntimeError("No se pudo consultar el estado del lote")
        return self.load_state()

    def collect_extraction(self) -> dict[str, Any]:
        state = self.load_state()
        if state.get("stage") != "extraction_submitted":
            raise RuntimeError("No hay una extracción enviada pendiente de recoger")
        extraction_dir = self.run_dir / "extraction_batch"
        code = collect_extraction_batch(Namespace(workdir=extraction_dir))
        if code == 2:
            raise RuntimeError("El lote de extracción todavía no terminó")
        if code != 0:
            raise RuntimeError("El lote de extracción contiene respuestas fallidas o inválidas")
        self._transition("extraction_collected")
        return self._validate_import_and_prepare_relations()

    def _validate_import_and_prepare_relations(self) -> dict[str, Any]:
        prepared_path = self.run_dir / "prepared_v5" / "fallos.jsonl"
        documents = load_jsonl(prepared_path)
        by_id = {int(row["pilot_id"]): row for row in documents}
        responses_dir = self.run_dir / "extraction_batch" / "results"
        validated_dir = self.run_dir / "validated_v5"
        validated_dir.mkdir(parents=True, exist_ok=True)
        validation = {
            "documents": 0,
            "standards": 0,
            "evidence_total": 0,
            "evidence_resolved": 0,
            "invalid_evidence": 0,
            "needs_review": 0,
            "format_errors": 0,
        }
        for response_path in sorted(responses_dir.glob("*_respuesta.txt")):
            pilot_id = int(response_path.name.split("_", 1)[0])
            try:
                result = validate_result(
                    by_id[pilot_id], response_path.read_text(encoding="utf-8")
                )
            except Exception:
                validation["format_errors"] += 1
                continue
            (validated_dir / f"{pilot_id:03d}_validado.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            values = result["validation"]
            validation["documents"] += 1
            validation["standards"] += int(values["standards_count"])
            validation["evidence_total"] += int(values["evidence_total"])
            validation["evidence_resolved"] += int(values["evidence_resolved"])
            validation["invalid_evidence"] += int(values["invalid_evidence"])
            validation["needs_review"] += int(bool(values["needs_review"]))
        if validation["format_errors"]:
            raise RuntimeError(
                f"Hay {validation['format_errors']} respuestas con formato inválido; no se importó el lote"
            )

        state = self.load_state()
        imported = import_validated_run(
            validated_dir=validated_dir,
            fallos_path=prepared_path,
            db_path=self.db_path,
            schema_path=self.repo_root / "standards" / "schema.sql",
            run_id=self.run_id,
            model=str(state.get("model") or "gpt-5.6-luna"),
            reasoning_effort=str(state.get("reasoning_effort") or "medium"),
        )
        self._transition("standards_imported", validation=validation, import_result=imported)
        return self.prepare_relations()

    def prepare_relations(self) -> dict[str, Any]:
        state = self.load_state()
        if state.get("stage") not in {"standards_imported", "relations_ready_to_submit"}:
            raise RuntimeError("Primero debe completarse la importación de estándares")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            decisions_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='relation_decisions'"
            ).fetchone()
            excluded = (
                {str(row[0]) for row in conn.execute("SELECT candidate_id FROM relation_decisions")}
                if decisions_table else set()
            )
            candidates = build_candidates(conn, 0.08, 1, 24, excluded)
        finally:
            conn.close()

        candidates_path = self.run_dir / "relation_candidates.jsonl"
        dump_jsonl(candidates_path, candidates)
        if not candidates:
            return self._transition(
                "completed",
                relation_candidates=0,
                message="No hay pares nuevos para clasificar",
            )

        state = self.load_state()
        code = prepare_relation_batch(Namespace(
            candidates=candidates_path,
            workdir=self.run_dir / "relations_batch",
            limit=None,
            model=state.get("model") or "gpt-5.6-luna",
            reasoning_effort=state.get("reasoning_effort") or "medium",
            max_output_tokens=700,
        ))
        if code != 0:
            raise RuntimeError("No se pudo preparar el lote de relaciones")
        return self._transition(
            "relations_ready_to_submit", relation_candidates=len(candidates)
        )

    def submit_relations(self) -> dict[str, Any]:
        state = self.load_state()
        if state.get("stage") != "relations_ready_to_submit":
            raise RuntimeError("Las relaciones no están listas para enviar")
        code = submit_relation_batch(Namespace(workdir=self.run_dir / "relations_batch"))
        if code != 0:
            raise RuntimeError("No se pudo enviar el lote de relaciones")
        return self._transition("relations_submitted")

    def collect_relations(self) -> dict[str, Any]:
        state = self.load_state()
        if state.get("stage") != "relations_submitted":
            raise RuntimeError("No hay un lote de relaciones pendiente de recoger")
        workdir = self.run_dir / "relations_batch"
        code = collect_relation_batch(Namespace(workdir=workdir))
        if code == 2:
            raise RuntimeError("El lote de relaciones todavía no terminó")
        if code != 0:
            raise RuntimeError("El lote de relaciones contiene respuestas fallidas o inválidas")
        classifications = workdir / "results" / "classifications.jsonl"
        result = apply_relation_decisions(
            self.db_path,
            load_jsonl(classifications),
            classifier_model=str(state.get("model") or ""),
            source_file=str(classifications.resolve()),
            apply=True,
        )
        if result["missing_standard"] or result["invalid"]:
            raise RuntimeError("Las decisiones de relaciones no superaron la validación final")
        return self._transition("completed", relation_result=result)

    def summary(self) -> dict[str, Any]:
        state = self.load_state()
        database: dict[str, int] = {}
        if self.db_path.exists():
            conn = sqlite3.connect(self.db_path)
            try:
                for table in ("documents", "standards", "quotes", "relations", "relation_decisions"):
                    exists = conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                    ).fetchone()
                    database[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) if exists else 0
            finally:
                conn.close()
        return {"state": state, "database": database, "run_dir": str(self.run_dir)}

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock, Thread
from time import monotonic
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ContextBuildJobResult:
    job_id: str
    package: Any
    saved_paths: Any
    elapsed_seconds: float


class ContextBuildService:
    """
    Ejecuta una única investigación del Context Builder en segundo plano.

    No depende de Streamlit. El objeto vive dentro de LexIAApplication, que
    Streamlit conserva mediante cache_resource, por lo que la tarea continúa
    aunque el usuario navegue a otra sección.
    """

    RUNNING_PHASES = {
        "queued",
        "saving_history",
        "searching",
        "saving",
    }

    def __init__(self, builder, history_repository):
        self.builder = builder
        self.history_repository = history_repository
        self._lock = Lock()
        self._thread: Thread | None = None
        self._result: ContextBuildJobResult | None = None
        self._state: dict[str, Any] = {
            "job_id": None,
            "phase": "idle",
            "status": "Sin investigación en curso",
            "percentage": 0,
            "query": "",
            "started_at": None,
            "finished_at": None,
            "elapsed_seconds": 0.0,
            "error": None,
        }

    def state(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def running(self) -> bool:
        with self._lock:
            return self._state["phase"] in self.RUNNING_PHASES

    def result(self) -> ContextBuildJobResult | None:
        with self._lock:
            return self._result

    def clear_result(self) -> None:
        """
        Limpia el resultado anterior. Se usa únicamente al iniciar una nueva
        investigación o si en el futuro se agrega una acción explícita de limpiar.
        """
        with self._lock:
            if self._state["phase"] in self.RUNNING_PHASES:
                return
            self._result = None
            if self._state["phase"] in {"completed", "error"}:
                self._state.update(
                    {
                        "phase": "idle",
                        "status": "Sin investigación en curso",
                        "percentage": 0,
                        "error": None,
                    }
                )

    def start_job(
        self,
        *,
        query: str,
        facts: str,
        objective: str,
        additional_instruction: str,
        max_sources: int,
    ) -> str:
        query = str(query or "").strip()
        if not query:
            raise ValueError("Ingresá una consulta.")

        with self._lock:
            if self._state["phase"] in self.RUNNING_PHASES:
                raise RuntimeError(
                    "Ya hay una investigación del Context Builder en curso."
                )

            job_id = uuid4().hex
            self._result = None
            self._state = {
                "job_id": job_id,
                "phase": "queued",
                "status": "Preparando investigación...",
                "percentage": 5,
                "query": query,
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "finished_at": None,
                "elapsed_seconds": 0.0,
                "error": None,
            }

            self._thread = Thread(
                target=self._run_job,
                kwargs={
                    "job_id": job_id,
                    "query": query,
                    "facts": str(facts or ""),
                    "objective": str(objective or ""),
                    "additional_instruction": str(
                        additional_instruction or ""
                    ),
                    "max_sources": int(max_sources),
                },
                name=f"lexia-context-{job_id[:8]}",
                daemon=True,
            )
            self._thread.start()
            return job_id

    def _update(self, **values: Any) -> None:
        with self._lock:
            self._state.update(values)

    def _run_job(
        self,
        *,
        job_id: str,
        query: str,
        facts: str,
        objective: str,
        additional_instruction: str,
        max_sources: int,
    ) -> None:
        started = monotonic()

        try:
            self._update(
                phase="saving_history",
                status="Guardando la consulta...",
                percentage=10,
            )

            self.history_repository.save(
                query=query,
                facts=facts,
                objective=objective,
                additional_instruction=additional_instruction,
                max_sources=max_sources,
            )

            self._update(
                phase="searching",
                status="Buscando y seleccionando fuentes...",
                percentage=35,
            )

            package = self.builder.build_research_package(
                query=query,
                facts=facts,
                objective=objective,
                additional_instruction=additional_instruction,
                max_sources=max_sources,
            )

            self._update(
                phase="saving",
                status="Organizando y guardando el contexto...",
                percentage=85,
            )

            paths = self.builder.save(package)
            elapsed = monotonic() - started

            result = ContextBuildJobResult(
                job_id=job_id,
                package=package,
                saved_paths=paths,
                elapsed_seconds=elapsed,
            )

            with self._lock:
                self._result = result
                self._state.update(
                    {
                        "phase": "completed",
                        "status": "Contexto listo para ChatGPT",
                        "percentage": 100,
                        "finished_at": datetime.now().isoformat(
                            timespec="seconds"
                        ),
                        "elapsed_seconds": round(elapsed, 3),
                        "error": None,
                    }
                )

        except Exception as error:
            elapsed = monotonic() - started
            self._update(
                phase="error",
                status="La investigación produjo un error",
                percentage=100,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                elapsed_seconds=round(elapsed, 3),
                error=str(error),
            )

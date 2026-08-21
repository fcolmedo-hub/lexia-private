from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter
from typing import Callable


@dataclass(slots=True)
class MonitorEvent:
    stage: str
    message: str
    progress: int
    detail: str = ""
    metrics: dict[str, object] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


@dataclass(slots=True)
class MonitorSnapshot:
    query: str
    mode: str
    status: str = "Preparando"
    progress: int = 0
    started_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )
    elapsed_seconds: float = 0.0
    events: list[MonitorEvent] = field(default_factory=list)
    metrics: dict[str, object] = field(default_factory=dict)


ProgressCallback = Callable[[MonitorEvent], None]


class IntelligenceMonitor:
    """Publica progreso real por etapas del motor de inteligencia."""

    def __init__(
        self,
        query: str,
        mode: str,
        callback: ProgressCallback | None = None,
    ):
        self.snapshot = MonitorSnapshot(query=query, mode=mode)
        self.callback = callback
        self._started = perf_counter()
        self._stage_started = self._started

    def step(
        self,
        stage: str,
        message: str,
        progress: int,
        detail: str = "",
        **metrics: object,
    ) -> None:
        now = perf_counter()
        progress = max(self.snapshot.progress, min(100, int(progress)))
        self.snapshot.progress = progress
        self.snapshot.status = message
        self.snapshot.elapsed_seconds = round(now - self._started, 2)
        self.snapshot.metrics.update(metrics)
        event = MonitorEvent(
            stage=stage,
            message=message,
            progress=progress,
            detail=detail,
            metrics=dict(metrics),
            elapsed_seconds=self.snapshot.elapsed_seconds,
        )
        self.snapshot.events.append(event)
        self._stage_started = now
        if self.callback:
            self.callback(event)

    def finish(self, **metrics: object) -> MonitorSnapshot:
        self.step(
            "finalizado",
            "Investigación finalizada",
            100,
            **metrics,
        )
        return self.snapshot

    def fail(self, error: Exception) -> MonitorSnapshot:
        self.step(
            "error",
            "La investigación se interrumpió",
            self.snapshot.progress,
            detail=str(error),
            error=str(error),
        )
        return self.snapshot

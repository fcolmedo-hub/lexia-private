from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any

from config.settings import SETTINGS


@dataclass(slots=True)
class CheckpointState:
    checkpoint_id: str
    task: str
    phase: str
    started_at: str
    updated_at: str
    completed: bool = False
    interrupted: bool = False
    processed: int = 0
    total: int = 0
    current_file: str = ""
    percentage: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class CheckpointService:
    def __init__(self, root_path: str | Path | None = None):
        configured = getattr(SETTINGS, "checkpoint_path", None)
        self.root_path = Path(
            root_path
            or configured
            or (SETTINGS.runtime_path / "checkpoints")
        ).resolve()
        self.current_path = self.root_path / "current_checkpoint.json"
        self.history_path = self.root_path / "history"
        self._lock = RLock()
        self._last_saved_at = 0.0
        self._last_saved_processed = -1

    def begin(
        self,
        task: str,
        phase: str,
        *,
        total: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> CheckpointState:
        now = datetime.now().isoformat(timespec="seconds")
        state = CheckpointState(
            checkpoint_id=uuid.uuid4().hex,
            task=task,
            phase=phase,
            started_at=now,
            updated_at=now,
            total=max(0, int(total)),
            payload=dict(payload or {}),
        )
        self._write(state)
        return state

    def load(self) -> CheckpointState | None:
        if not self.current_path.exists():
            return None
        try:
            data = json.loads(
                self.current_path.read_text(encoding="utf-8")
            )
            return CheckpointState(**data)
        except Exception:
            return None

    def pending(self) -> CheckpointState | None:
        state = self.load()
        if state is None or state.completed:
            return None
        return state

    def update(
        self,
        *,
        phase: str | None = None,
        processed: int | None = None,
        total: int | None = None,
        current_file: str | None = None,
        percentage: int | None = None,
        payload_update: dict[str, Any] | None = None,
        force: bool = False,
    ) -> CheckpointState | None:
        with self._lock:
            state = self.load()
            if state is None or state.completed:
                return state

            phase_changed = phase is not None and phase != state.phase
            if phase is not None:
                state.phase = phase
            if processed is not None:
                state.processed = max(0, int(processed))
            if total is not None:
                state.total = max(0, int(total))
            if current_file is not None:
                state.current_file = str(current_file)
            if percentage is not None:
                state.percentage = max(0, min(100, int(percentage)))
            elif state.total > 0:
                state.percentage = max(
                    0,
                    min(100, int(state.processed / state.total * 100)),
                )
            if payload_update:
                state.payload.update(payload_update)

            now_mono = time.monotonic()
            elapsed = now_mono - self._last_saved_at
            units = state.processed - self._last_saved_processed
            should_write = (
                force
                or phase_changed
                or elapsed >= 5.0
                or units >= 100
                or state.processed >= state.total > 0
            )

            if should_write:
                state.updated_at = datetime.now().isoformat(
                    timespec="seconds"
                )
                self._write(state)
            return state

    def complete(
        self,
        *,
        payload_update: dict[str, Any] | None = None,
    ) -> CheckpointState | None:
        with self._lock:
            state = self.load()
            if state is None:
                return None
            if payload_update:
                state.payload.update(payload_update)
            state.completed = True
            state.interrupted = False
            state.error = None
            state.percentage = 100
            state.updated_at = datetime.now().isoformat(
                timespec="seconds"
            )
            self._write(state)
            self._archive(state)
            try:
                self.current_path.unlink()
            except FileNotFoundError:
                pass
            return state

    def fail(self, error: str) -> CheckpointState | None:
        with self._lock:
            state = self.load()
            if state is None:
                return None
            state.interrupted = True
            state.error = str(error)
            state.updated_at = datetime.now().isoformat(
                timespec="seconds"
            )
            self._write(state)
            return state

    def cancel(self) -> None:
        with self._lock:
            state = self.load()
            if state is not None:
                state.completed = True
                state.interrupted = False
                state.error = "Cancelado por el usuario"
                state.updated_at = datetime.now().isoformat(
                    timespec="seconds"
                )
                self._archive(state)
            try:
                self.current_path.unlink()
            except FileNotFoundError:
                pass

    def status(self) -> dict[str, Any]:
        state = self.load()
        return {
            "active": bool(state and not state.completed),
            "checkpoint": asdict(state) if state is not None else None,
            "current_path": str(self.current_path),
            "history_path": str(self.history_path),
        }

    def _write(self, state: CheckpointState) -> None:
        self.root_path.mkdir(parents=True, exist_ok=True)
        temporary = self.current_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(
                asdict(state),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, self.current_path)
        self._last_saved_at = time.monotonic()
        self._last_saved_processed = state.processed

    def _archive(self, state: CheckpointState) -> None:
        self.history_path.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = self.history_path / (
            f"{stamp}_{state.task}_{state.checkpoint_id[:8]}.json"
        )
        destination.write_text(
            json.dumps(
                asdict(state),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

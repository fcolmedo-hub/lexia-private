import atexit
import json
import os
import socket
from datetime import datetime
from pathlib import Path

import psutil

from config.settings import SETTINGS


class RuntimeGuard:
    def __init__(self, state_path: str | Path = SETTINGS.app_state_path):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.acquired = False

    def acquire(self) -> None:
        previous = self.read_state()

        if previous and self._is_active(previous):
            current_pid = os.getpid()

            if previous.get("pid") != current_pid:
                raise RuntimeError(
                    "LexIA ya está abierta en otra instancia. "
                    f"Proceso activo: PID {previous.get('pid')}."
                )

        payload = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }

        self.state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.acquired = True
        atexit.register(self.release)

    def release(self) -> None:
        if not self.acquired:
            return

        state = self.read_state()

        if state and state.get("pid") == os.getpid():
            self.state_path.unlink(missing_ok=True)

        self.acquired = False

    def read_state(self) -> dict | None:
        if not self.state_path.exists():
            return None

        try:
            return json.loads(
                self.state_path.read_text(encoding="utf-8")
            )
        except Exception:
            return None

    def clear_stale(self) -> bool:
        state = self.read_state()

        if state and not self._is_active(state):
            self.state_path.unlink(missing_ok=True)
            return True

        return False

    def _is_active(self, state: dict) -> bool:
        pid = state.get("pid")

        if not isinstance(pid, int):
            return False

        return psutil.pid_exists(pid)

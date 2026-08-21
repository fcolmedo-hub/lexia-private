from services.logging_service import configure_logging
from services.runtime_guard import RuntimeGuard


def main() -> None:
    configure_logging()

    guard = RuntimeGuard()
    guard.clear_stale()

    state = guard.read_state()

    if state:
        raise RuntimeError(
            "Cerrá la interfaz de LexIA antes de indexar. "
            f"Instancia activa: PID {state.get('pid')}."
        )

    from main import command_ingest

    command_ingest()


if __name__ == "__main__":
    main()

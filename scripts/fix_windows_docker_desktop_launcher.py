from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "ui2" / "windows_desktop.py"
BACKUP = TARGET.with_suffix(".py.bak-docker-desktop-launcher-20260830")
MARKER = "Docker Desktop: ejecutable principal"

NEW_DOCKER_DESKTOP = '''def docker_desktop() -> Path | None:
    # Preferir el ejecutable principal de Docker Desktop. Algunas instalaciones
    # incluyen otro Docker Desktop.exe dentro de resources; ese auxiliar no debe
    # usarse como lanzador principal.
    registry = _docker_desktop_from_registry()
    if registry is not None and registry.parent.name.lower() != "resources":
        return registry

    candidates: list[Path] = []
    for key in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        base = os.environ.get(key)
        if base:
            root = Path(base)
            candidates.extend([
                root / "Docker" / "Docker" / "Docker Desktop.exe",
                root / "Docker" / "Docker Desktop.exe",
                root / "DockerDesktop" / "Docker Desktop.exe",
            ])

    lad = local_appdata()
    candidates.extend([
        lad / "Docker" / "Docker Desktop.exe",
        lad / "Programs" / "Docker" / "Docker" / "Docker Desktop.exe",
        lad / "Programs" / "Docker" / "Docker Desktop.exe",
        lad / "Programs" / "DockerDesktop" / "Docker Desktop.exe",
    ])

    cli = docker_cli()
    if cli is not None:
        current = cli.parent
        while current.parent != current:
            if current.name.lower() == "resources":
                install_root = current.parent
                candidates.insert(0, install_root / "Docker Desktop.exe")
                break
            current = current.parent

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists() and candidate.parent.name.lower() != "resources":
            return candidate

    return None
'''

NEW_LAUNCH = '''def launch_docker_desktop() -> None:
    desktop = docker_desktop()
    if desktop is None:
        binary = docker_cli()
        hint = f" docker.exe={binary}" if binary else " docker.exe=no encontrado"
        raise RuntimeError("No se encontró el ejecutable principal de Docker Desktop en Windows." + hint)

    log_startup(f"Docker Desktop: ejecutable principal {desktop}")
    try:
        process = subprocess.Popen(
            [str(desktop)],
            cwd=str(desktop.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
        log_startup(f"Docker Desktop: proceso lanzado pid={process.pid}")
        return
    except Exception as exc:
        log_startup(f"Docker Desktop: Popen falló: {exc}")

    try:
        os.startfile(str(desktop))
        log_startup("Docker Desktop: lanzado mediante os.startfile")
        return
    except Exception as exc:
        log_startup(f"Docker Desktop: os.startfile falló: {exc}")
        raise RuntimeError(f"No se pudo iniciar Docker Desktop: {desktop}") from exc
'''


def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"ABORTADO: no existe {TARGET}")

    text = TARGET.read_text(encoding="utf-8", errors="strict")
    if MARKER in text:
        print("OK: windows_desktop.py ya contiene el launcher corregido")
        return

    desktop_pattern = re.compile(
        r"def docker_desktop\(\) -> Path \| None:\n.*?(?=\ndef docker_ready\(\) -> bool:)",
        re.S,
    )
    launch_pattern = re.compile(
        r"def launch_docker_desktop\(\) -> None:\n.*?(?=\ndef ensure_docker\(\) -> None:)",
        re.S,
    )

    patched, n1 = desktop_pattern.subn(NEW_DOCKER_DESKTOP.rstrip() + "\n", text, count=1)
    patched, n2 = launch_pattern.subn(NEW_LAUNCH.rstrip() + "\n", patched, count=1)

    if n1 != 1 or n2 != 1:
        raise SystemExit(
            f"ABORTADO: esperaba reemplazar 1 docker_desktop y 1 launch_docker_desktop; obtuve {n1} y {n2}. No modifiqué nada."
        )

    # Validar la sintaxis completa de windows_desktop.py antes de escribir.
    compile(patched, str(TARGET), "exec")

    if not BACKUP.exists():
        BACKUP.write_text(text, encoding="utf-8")
    TARGET.write_text(patched, encoding="utf-8")

    print("OK: windows_desktop.py corregido y validado")
    print("- prioriza Docker Desktop.exe fuera de resources")
    print("- contempla AppData\\Local\\Programs\\DockerDesktop")
    print("- registra ruta exacta y PID del proceso lanzado")


if __name__ == "__main__":
    main()

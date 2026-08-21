\
import ast
import importlib.util
from pathlib import Path

from services.platform_info_service import (
    PlatformInfoService,
)


ROOT = Path(__file__).resolve().parent

REQUIRED_FILES = (
    "app/ui.py",
    "ai/context_package_builder.py",
    "ai/knowledge_context_builder.py",
    "config/settings.py",
    "core/document_extractor.py",
    "core/pipeline.py",
    "prompt/compiler.py",
    "prompt/launcher.py",
    "search/interpreted_search.py",
    "search/professional_search.py",
    "services/application.py",
    "services/autosync_service.py",
    "services/performance_profiler.py",
    "services/prompt_launcher_service.py",
    "services/platform_info_service.py",
)


def main():
    errors = []

    for relative in REQUIRED_FILES:
        path = ROOT / relative

        if not path.exists():
            errors.append(
                f"Falta el archivo: {relative}"
            )
            continue

        if path.suffix == ".py":
            try:
                ast.parse(
                    path.read_text(
                        encoding="utf-8"
                    ),
                    filename=str(path),
                )
            except SyntaxError as error:
                errors.append(
                    f"Error de sintaxis en "
                    f"{relative}: {error}"
                )

    info = PlatformInfoService().status()

    for name, component in info[
        "components"
    ].items():
        if not component["available"]:
            errors.append(
                f"Componente no disponible: {name}"
            )

    if errors:
        print(
            "\nLEXIA PLATFORM 2.1 DEV — "
            "CONTROL FALLIDO\n"
        )
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print(
        "\nLEXIA PLATFORM 2.1 DEV — "
        "CONTROL CORRECTO\n"
    )
    print(
        f"Versión: {info['version']}"
    )
    print(
        f"Build: {info['build']}"
    )
    print(
        "Todos los componentes esenciales "
        "están disponibles."
    )
    print(
        "No se modificaron data, runtime ni Qdrant."
    )


if __name__ == "__main__":
    main()

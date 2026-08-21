import importlib
import sys

from services.health_service import HealthService
from version import __version__


REQUIRED_MODULES = (
    "streamlit",
    "qdrant_client",
    "fastembed",
    "fitz",
    "rapidocr_onnxruntime",
    "docx",
    "pypdf",
    "psutil",
)


def main() -> None:
    errors = []

    for module_name in REQUIRED_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as error:
            errors.append(f"{module_name}: {error}")

    print(f"LexIA Professional {__version__}")

    if errors:
        print("\nDependencias con problemas:")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)

    report = HealthService().report()

    print("\nVerificación:")
    for key, value in report.items():
        print(f"- {key}: {value}")

    if not report["healthy"]:
        sys.exit(2)

    print("\nInstalación verificada correctamente.")


if __name__ == "__main__":
    main()

import pytest


pytestmark = pytest.mark.skip(
    reason=(
        "La importación sigue embebida en app/ui.py y no expone una operación "
        "invocable sin Streamlit. Este control estático se reemplazará cuando "
        "la importación se extraiga a un servicio testeable."
    )
)


def test_library_importer_requires_a_service_boundary():
    """Marcador temporal: no simular os.replace como si fuera una prueba LexIA."""

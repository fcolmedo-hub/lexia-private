import pytest


pytestmark = pytest.mark.skip(
    reason=(
        "La prueba protegía menús y claves de la UI clásica ya reemplazados por "
        "UI2. La navegación actual se cubrirá con pruebas específicas de UI2."
    )
)


def test_unified_workspaces_legacy_ui_contract_retired():
    """Marcador temporal hasta incorporar pruebas de navegación UI2."""

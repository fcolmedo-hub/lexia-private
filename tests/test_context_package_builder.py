from pathlib import Path

from ai.context_package_builder import (
    ContextPackage,
    ContextPackageBuilder,
)


def test_package_contains_mandatory_task():
    package = ContextPackage(
        title="prueba",
        content=(
            "TAREA OBLIGATORIA\n"
            "Respondé directamente la consulta.\n"
            "No preguntes qué debe hacerse."
        ),
        sources=[],
        created_at="2026-01-01T00:00:00",
        character_count=100,
        objective="Investigación jurídica",
        query="Consulta",
        facts="",
        interpretation={},
        document_count=0,
        selected_count=0,
    )

    assert "TAREA OBLIGATORIA" in package.content
    assert "No preguntes" in package.content


def test_safe_title():
    builder = ContextPackageBuilder.__new__(
        ContextPackageBuilder
    )
    title = builder._safe_title(
        "¿Responsabilidad del Estado?"
    )

    assert "?" not in title
    assert title

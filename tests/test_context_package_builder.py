from pathlib import Path

from ai.context_package_builder import (
    ContextPackage,
    ContextPackageBuilder,
)
from models.search_result import SearchResult


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


def _result(path, index, text, page):
    return SearchResult(
        document_name=Path(path).name,
        document_path=Path(path),
        category="Jurisprudencia",
        fragment_index=index,
        text=text,
        score=1.0,
        page_start=page,
        page_end=page,
    )


def test_render_groups_fragments_from_same_document_as_one_source():
    builder = ContextPackageBuilder.__new__(ContextPackageBuilder)
    rendered = builder._render_sources(
        [
            _result("fallo-a.pdf", 1, "primer fundamento", 4),
            _result("fallo-a.pdf", 8, "segundo fundamento", 19),
            _result("fallo-b.pdf", 2, "otro precedente", 7),
        ]
    )

    assert rendered.count("[FUENTE 1]") == 1
    assert rendered.count("[FUENTE 2]") == 1
    assert "[FUENTE 3]" not in rendered
    assert "Fragmentos seleccionados: 2" in rendered
    assert "Página 4" in rendered
    assert "Página 19" in rendered
    assert rendered.count("Documento: fallo-a.pdf") == 1


def test_curation_regroups_only_selected_fragments():
    builder = ContextPackageBuilder.__new__(ContextPackageBuilder)
    sources = [
        _result("fallo-a.pdf", 1, "primer fundamento", 4),
        _result("fallo-a.pdf", 8, "segundo fundamento", 19),
        _result("fallo-b.pdf", 2, "otro precedente", 7),
    ]
    package = ContextPackage(
        title="prueba",
        content=(
            "ENCABEZADO\n\nFUENTES\n\n"
            + builder._render_sources(sources)
            + "\n\nESTRUCTURA DE LA RESPUESTA\n\nFIN"
        ),
        sources=sources,
        created_at="2026-01-01T00:00:00",
        character_count=1,
        objective="Investigación jurídica",
        query="Consulta",
        facts="",
        interpretation={},
        document_count=3,
        selected_count=2,
    )

    curated = builder.curate_package(package, [0, 1])

    assert curated.selected_count == 1
    assert curated.content.count("[FUENTE 1]") == 1
    assert "[FUENTE 2]" not in curated.content
    assert "Fragmentos seleccionados: 2" in curated.content

from pathlib import Path

from storage.legal_matrix_repository import (
    LegalMatrixRepository,
)


def test_matrix_persists_row(tmp_path: Path) -> None:
    repository = LegalMatrixRepository(
        tmp_path / "matrix.sqlite3"
    )

    row_id = repository.add(
        fact="La Administración demoró.",
        evidence="Expediente administrativo.",
        legal_rule="Falta de servicio.",
    )

    rows = repository.list_rows()

    assert row_id > 0
    assert rows[0]["fact"] == "La Administración demoró."

from pathlib import Path

from legal.query_interpreter import LegalQueryInterpreter
from storage.query_interpretation_repository import (
    QueryInterpretationRepository,
)


def test_repository_saves_interpretation(tmp_path: Path) -> None:
    repository = QueryInterpretationRepository(
        tmp_path / "interpretations.sqlite3"
    )

    interpretation = LegalQueryInterpreter().interpret(
        "plazo razonable en proceso penal"
    )

    record_id = repository.save(
        interpretation,
        corrected=True,
    )

    rows = repository.list_recent()

    assert record_id > 0
    assert rows[0]["corrected"] == 1

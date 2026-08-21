from pathlib import Path

from storage.context_query_history_repository import (
    ContextQueryHistoryRepository,
)


def test_context_query_history_save_load_search_delete(
    tmp_path: Path,
) -> None:
    repository = ContextQueryHistoryRepository(
        tmp_path / "history.sqlite3"
    )

    history_id = repository.save(
        query="Prescripción tributaria",
        facts="Tributo municipal",
        objective="Investigación jurídica",
        additional_instruction="Priorizar CSJN",
        max_sources=12,
    )

    item = repository.get(history_id)
    assert item is not None
    assert item["query"] == "Prescripción tributaria"
    assert item["max_sources"] == 12

    matches = repository.list_recent(search="tributaria")
    assert len(matches) == 1
    assert matches[0]["id"] == history_id

    assert repository.delete(history_id) is True
    assert repository.get(history_id) is None
    assert repository.count() == 0

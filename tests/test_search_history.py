from pathlib import Path
from storage.search_history_repository import SearchHistoryRepository

def test_search_history_persists_query(tmp_path: Path) -> None:
    repository = SearchHistoryRepository(tmp_path / "history.sqlite3")
    repository.add("plazo razonable", "Jurisprudencia", 5)
    history = repository.list_recent()
    assert history[0]["query"] == "plazo razonable"

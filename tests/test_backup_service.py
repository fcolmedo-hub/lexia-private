import sqlite3
from pathlib import Path

from services.backup_service import BackupService


def test_sqlite_backup(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite3"
    target = tmp_path / "target.sqlite3"

    with sqlite3.connect(source) as connection:
        connection.execute(
            "CREATE TABLE test (value TEXT)"
        )
        connection.execute(
            "INSERT INTO test VALUES ('ok')"
        )

    service = BackupService()
    service._sqlite_backup(source, target)

    with sqlite3.connect(target) as connection:
        value = connection.execute(
            "SELECT value FROM test"
        ).fetchone()[0]

    assert value == "ok"

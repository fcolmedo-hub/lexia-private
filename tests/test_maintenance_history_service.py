from services.maintenance_history_service import MaintenanceHistoryService


def test_history_is_recent_first_and_respects_limit(tmp_path):
    service = MaintenanceHistoryService(
        tmp_path / "maintenance.sqlite3",
        retention=50,
    )
    for position in range(12):
        service.record(
            action="test",
            status="ok",
            message=f"acción {position}",
            details={"position": position},
        )

    recent = service.recent(limit=8)

    assert len(recent) == 8
    assert recent[0]["message"] == "acción 11"
    assert recent[-1]["message"] == "acción 4"
    assert recent[0]["details"] == {"position": 11}

from services.health_service import HealthService


def test_health_report_has_required_fields() -> None:
    report = HealthService().report()

    assert "version" in report
    assert "runtime_writable" in report
    assert "free_disk_gb" in report
    assert "healthy" in report

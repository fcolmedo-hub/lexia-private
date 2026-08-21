from services.intelligence_monitor import IntelligenceMonitor


def test_monitor_progress_is_monotonic():
    events = []
    monitor = IntelligenceMonitor("consulta", "modo", events.append)
    monitor.step("uno", "Primero", 30)
    monitor.step("dos", "Segundo", 20)
    monitor.finish(fuentes=3)
    assert [event.progress for event in events] == [30, 30, 100]
    assert monitor.snapshot.metrics["fuentes"] == 3

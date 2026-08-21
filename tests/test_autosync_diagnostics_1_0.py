from pathlib import Path

def test_autosync_diagnostics_installed():
    source = Path("services/autosync_service.py").read_text(encoding="utf-8")
    required = [
        "_configure_diagnostic_logging",
        "stage_timings",
        "last_failure_stage",
        "pipeline_failed",
        'stage = "pipeline"',
        'stage = "vector_indexing"',
        'stage = "knowledge"',
    ]
    for marker in required:
        assert marker in source

from pathlib import Path

def test_pipeline_has_partial_ocr():
    source = Path("core/pipeline.py").read_text(encoding="utf-8")
    assert "ocr_partial_pending" in source
    assert "ocr_partial_index_min_chars" in source
    assert "ocr_partial_indexed" in source

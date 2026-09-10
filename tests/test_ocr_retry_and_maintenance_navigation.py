from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from core import ocr_worker
from core.ocr_service import OCRService


ROOT = Path(__file__).resolve().parents[1]


class _SequentialOCR:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = 0

    def __call__(self, _image):
        self.calls += 1
        return next(self.results), None


def test_ocr_retries_visible_page_at_higher_contrast(monkeypatch) -> None:
    rendered_dpis = []

    def fake_render(_page, dpi):
        rendered_dpis.append(dpi)
        return Image.new("RGB", (80, 40), "white")

    engine = _SequentialOCR([
        None,
        [([0, 0, 1, 1], "Texto jurídico recuperado", 0.98)],
    ])
    monkeypatch.setattr(ocr_worker, "_render", fake_render)

    lines, attempts = ocr_worker._recognize_page(engine, object(), 170)

    assert lines == ["Texto jurídico recuperado"]
    assert rendered_dpis == [170, 260]
    assert [attempt["mode"] for attempt in attempts] == ["normal", "contrast"]


def test_ocr_uses_threshold_as_last_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        ocr_worker,
        "_render",
        lambda _page, _dpi: Image.new("RGB", (80, 40), "white"),
    )
    engine = _SequentialOCR([
        None,
        None,
        [([0, 0, 1, 1], "Texto tenue recuperado", 0.92)],
    ])

    lines, attempts = ocr_worker._recognize_page(engine, object(), 170)

    assert lines == ["Texto tenue recuperado"]
    assert engine.calls == 3
    assert [attempt["mode"] for attempt in attempts] == [
        "normal",
        "contrast",
        "threshold",
    ]


def test_autosync_card_opens_and_marks_maintenance_route() -> None:
    source = (ROOT / "app/ui2/assets/maintenance.js").read_text(encoding="utf-8")

    assert "document.getElementById('casespage')" in source
    assert "document.getElementById('lexiaStandardsShell')?.classList.remove('open')" in source
    assert "routeNav.querySelector('[data-route=\"maintenance\"]')" in source
    assert "maintenanceButton.classList.add('active')" in source


def test_macos_launcher_cache_busts_maintenance_asset() -> None:
    source = (ROOT / "app/ui2/macos_desktop.py").read_text(encoding="utf-8")

    assert 'maintenance = here / "assets" / "maintenance.js"' in source
    assert "maintenance-{version}" in source


def test_direct_ocr_diagnostics_are_written_to_runtime(monkeypatch, tmp_path) -> None:
    from core import ocr_service

    monkeypatch.setattr(
        ocr_service,
        "SETTINGS",
        SimpleNamespace(runtime_path=tmp_path),
    )
    OCRService._record_diagnostics(
        tmp_path / "fallo.pdf",
        {1: [{"mode": "normal", "dpi": 170, "lines": 0}]},
    )

    log = (tmp_path / "ocr_diagnostic.log").read_text(encoding="utf-8")
    assert "DIRECT_OCR" in log
    assert "normal@170dpi=0" in log

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "ui2" / "index.html"


def test_home_context_metric_is_named_investigations():
    source = INDEX.read_text(encoding="utf-8")
    start = source.index('<article data-home-target="contextpage">')
    end = source.index("</article>", start)
    card = source[start:end]

    assert "<b>Investigaciones</b>" in card
    assert "<span>Realizadas</span>" in card
    assert "<small>Última investigación</small>" in card
    assert "<b>Contextos</b>" not in card

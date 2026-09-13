from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_research_reuses_the_application_catalog_instead_of_reinitializing_it():
    source = (ROOT / "ai" / "knowledge_context_builder.py").read_text(
        encoding="utf-8"
    )

    assert "self.catalog = catalog" in source
    assert "def _research_catalog(self)" in source
    assert "if self.catalog is not None:" in source
    assert "return self.catalog" in source


def test_application_injects_its_initialized_catalog_into_research():
    source = (ROOT / "services" / "application.py").read_text(encoding="utf-8")

    call = source[source.index("KnowledgeContextPackageBuilder(") :]
    assert "self.catalog," in call[:500]


def test_quick_and_fallback_research_use_the_shared_catalog_accessor():
    source = (ROOT / "ai" / "knowledge_context_builder.py").read_text(
        encoding="utf-8"
    )

    assert source.count("catalog = self._research_catalog()") == 2

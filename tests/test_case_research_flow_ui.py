from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "ui2" / "assets"


def test_case_research_flow_is_loaded_before_app_runtime_early_return():
    runtime = (ASSETS / "app_runtime.js").read_text(encoding="utf-8")

    assert "assets/case_research_flow.js?v=case-research-1" in runtime
    assert "data-lexia-case-research-flow" in runtime
    assert runtime.index("loadCaseResearchFlow();") < runtime.index("if(params.get('lexia_app')!=='1')return;")


def test_case_blocks_expose_investigate_and_individual_source_delete_actions():
    flow = (ASSETS / "case_research_flow.js").read_text(encoding="utf-8")

    assert ".argument-block-actions" in flow
    assert "lexia-case-investigate" in flow
    assert "Investigar este fundamento" in flow
    assert "/api/cases/block/highlight/delete" in flow
    assert "Eliminar sub-bloque" in flow


def test_case_research_uses_own_position_as_query_and_counterpart_as_adversarial_context():
    flow = (ASSETS / "case_research_flow.js").read_text(encoding="utf-8")

    assert "Nuestra postura a investigar" in flow
    assert "Planteo de la contraparte" in flow
    assert "solo referencia adversarial" in flow
    assert "no buscar fundamentos que lo respalden" in flow
    assert "Planteá primero el fundamento propio" in flow


def test_selected_research_sources_link_to_the_same_case_block():
    flow = (ASSETS / "case_research_flow.js").read_text(encoding="utf-8")

    assert "/api/cases/link-document" in flow
    assert "linked.link_id" in flow
    assert "/api/cases/block/highlight" in flow
    assert "block_id:ctx.blockId" in flow
    assert "Incorporar fuentes seleccionadas" in flow


def test_research_removes_legacy_to_case_action_and_prevents_compact_overlap():
    flow = (ASSETS / "case_research_flow.js").read_text(encoding="utf-8")

    assert "[data-lexia-case-link]" in flow
    assert "@media(max-width:1199px)" in flow
    assert "#researchPanel" in flow
    assert "clear:both!important" in flow

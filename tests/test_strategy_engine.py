from legal.case_strategy import CaseStrategyEngine


def test_strategy_detects_missing_evidence() -> None:
    report = CaseStrategyEngine().build(
        thesis="Existe responsabilidad estatal.",
        facts="Hubo demora.",
        evidence="",
        adverse_position="La demora fue razonable.",
        sources_count=2,
    )
    assert report.missing_evidence

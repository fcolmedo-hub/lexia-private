from legal.drafting_engine import DraftingEngine


def test_drafting_outline_contains_petitorio() -> None:
    outline = DraftingEngine().build_outline(
        "Demanda",
        "La demandada debe responder.",
        "Existió incumplimiento.",
        [],
    )
    assert "Petitorio" in outline

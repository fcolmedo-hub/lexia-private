from legal.query_interpreter import LegalQueryInterpreter
from legal.search_planner import LegalSearchPlanner


def test_planner_uses_interpretation_queries() -> None:
    interpretation = LegalQueryInterpreter().interpret(
        "solve et repete en Entre Ríos"
    )

    plan = LegalSearchPlanner().build(interpretation)

    assert plan.queries
    assert "Legislación" in plan.category_order

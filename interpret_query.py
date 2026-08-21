import json
import sys

from services.application import LexIAApplication


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            'Usá: python .\\interpret_query.py "consulta jurídica"'
        )

    query = " ".join(sys.argv[1:])
    app = LexIAApplication()

    interpretation = app.query_interpreter.interpret(query)
    plan = app.search_planner.build(interpretation)

    payload = {
        "interpretation": interpretation.to_dict(),
        "plan": {
            "main_query": plan.main_query,
            "queries": plan.queries,
            "category_order": plan.category_order,
            "strategy_notes": plan.strategy_notes,
        },
    }

    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

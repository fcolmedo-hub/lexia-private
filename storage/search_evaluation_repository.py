import json
from pathlib import Path


class SearchEvaluationRepository:
    def __init__(
        self,
        path: str | Path = "runtime/search_evaluation.json",
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():
            self.path.write_text(
                json.dumps(
                    {
                        "queries": [
                            {
                                "query": "responsabilidad del Estado por demora administrativa",
                                "notes": "",
                            },
                            {
                                "query": "plazo razonable en proceso penal",
                                "notes": "",
                            },
                            {
                                "query": "prórroga de competencia territorial entre comerciantes",
                                "notes": "",
                            },
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    def load(self) -> dict:
        return json.loads(
            self.path.read_text(encoding="utf-8")
        )

    def save(self, payload: dict) -> None:
        self.path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

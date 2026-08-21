import json
from services.application import LexIAApplication


def main() -> None:
    app = LexIAApplication()
    payload = app.evaluations.load()
    details = []
    for item in payload.get("queries", []):
        query = item.get("query", "").strip()
        if not query:
            continue
        results = app.search.search(query, limit=5)
        details.append({
            "query": query,
            "results": [
                {"document": r.document_name, "page": r.page_label, "score": round(r.score, 6)}
                for r in results
            ],
        })
    print(json.dumps({"executed": len(details), "details": details}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

import sys

from services.application import LexIAApplication


def mark(value: bool) -> str:
    return "OK" if value else "PENDIENTE"


def main() -> None:
    if len(sys.argv) < 2:
        print(
            'Uso: python .\\verify_document.py "nombre o ruta.pdf"'
        )
        raise SystemExit(1)

    term = " ".join(sys.argv[1:]).strip()
    app = LexIAApplication()
    inspector = app.document_inspector

    matches = inspector.search(term, limit=20)

    if not matches:
        print(f"No se encontraron coincidencias para: {term}")
        raise SystemExit(2)

    if len(matches) > 1:
        print("Se encontraron varias coincidencias:\n")

        for position, item in enumerate(matches, start=1):
            print(
                f"{position}. {item['name']}\n"
                f"   {item['path']}"
            )

        print(
            "\nUsá la ruta completa o un nombre más específico."
        )
        raise SystemExit(3)

    result = inspector.inspect(matches[0]["path"])

    print("\nLEXIA DOCUMENT INSPECTOR\n")
    print(f"Documento      : {result.name}")
    print(f"Ruta           : {result.path}")
    print(f"Estado general : {result.overall_status}")
    print(f"Categoría      : {result.category}")
    print(f"Actualizado    : {result.updated_at}")
    print(f"Hash           : {result.content_hash}")
    print()

    for row in result.status_rows():
        print(
            f"{mark(row['correcto']):10} "
            f"{row['componente']}: {row['detalle']}"
        )

    if result.extraction_error:
        print(f"\nError: {result.extraction_error}")

    if result.knowledge:
        print(
            "\nConceptos: "
            + ", ".join(
                result.knowledge.get("concepts", [])
            )
        )


if __name__ == "__main__":
    main()

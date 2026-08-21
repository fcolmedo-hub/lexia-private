from legal.metadata_extractor import LegalMetadataExtractor


def test_metadata_detects_matter_and_expedient() -> None:
    text = (
        "Corte Suprema de Justicia de la Nación\n"
        "Expte. 1234/2024\n"
        "Impuesto sobre los ingresos brutos. Ley 23.548."
    )

    metadata = LegalMetadataExtractor().extract(
        text,
        "fallo.pdf",
        "Jurisprudencia",
    )

    assert metadata["matter"] == "Tributario"
    assert "1234/2024" in metadata["expedient"]

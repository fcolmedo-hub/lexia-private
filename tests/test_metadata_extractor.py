from legal.metadata_extractor import LegalMetadataExtractor


def test_metadata_detects_court_and_law() -> None:
    text = (
        "Corte Suprema de Justicia de la Nación\n"
        "Buenos Aires, 12/03/2024\n"
        "Ley 19.549 y artículo 7."
    )

    metadata = LegalMetadataExtractor().extract(
        text,
        "fallo.pdf",
        "Jurisprudencia",
    )

    assert "Corte Suprema" in metadata["court"]
    assert "Ley 19.549" in metadata["laws"]
    assert metadata["document_kind"] == "Fallo judicial"

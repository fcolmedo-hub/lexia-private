from legal.document_comparator import DocumentComparator


def test_comparator_detects_common_citation() -> None:
    comparison = DocumentComparator().compare(
        "Ley 23.548. OBJETO. HECHOS.",
        "Ley 23.548. HECHOS. PETITORIO.",
    )

    assert any(
        "23.548" in citation
        for citation in comparison.common_citations
    )
    assert comparison.structural_differences

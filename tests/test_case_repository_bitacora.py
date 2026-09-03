from storage.case_repository import CaseRepository


def test_case_keeps_documents_as_links_and_entries_as_a_timeline(tmp_path) -> None:
    repository = CaseRepository(tmp_path / "cases.sqlite3")
    case_id = repository.create_case("AMPJBON", "Exención de ingresos brutos")

    link_id = repository.link_document(
        case_id,
        document_id=41,
        document_name="Cooperativa Farmacéutica Alberdi.pdf",
        document_path="/Biblioteca/Jurisprudencia/alberdi.pdf",
        category="Jurisprudencia",
        relation_kind="precedente favorable",
    )
    entry_id = repository.add_entry(
        case_id,
        entry_type="extracto documental",
        title="Alcance de la exención",
        content="La exención debe interpretarse según la ley de coparticipación.",
        document_id=41,
        document_name="Cooperativa Farmacéutica Alberdi.pdf",
        document_path="/Biblioteca/Jurisprudencia/alberdi.pdf",
        page_start=12,
        source_excerpt="…la exención…",
    )

    snapshot = repository.case_snapshot(case_id)

    assert link_id == snapshot["documents"][0]["id"]
    assert snapshot["documents"][0]["category"] == "Jurisprudencia"
    assert entry_id == snapshot["entries"][0]["id"]
    assert snapshot["entries"][0]["page_start"] == 12
    assert snapshot["entries"][0]["entry_type"] == "extracto documental"


def test_linking_the_same_document_updates_the_link_instead_of_copying_it(tmp_path) -> None:
    repository = CaseRepository(tmp_path / "cases.sqlite3")
    case_id = repository.create_case("Prueba")

    repository.link_document(
        case_id,
        document_name="Ley 20.321",
        document_path="/Biblioteca/Legislación/ley-20321.pdf",
        category="Legislación",
    )
    repository.link_document(
        case_id,
        document_name="Ley 20.321",
        document_path="/Biblioteca/Legislación/ley-20321.pdf",
        category="Legislación",
        relation_kind="norma aplicable",
        note="Controlar vigencia.",
    )

    documents = repository.list_documents(case_id)
    assert len(documents) == 1
    assert documents[0]["relation_kind"] == "norma aplicable"

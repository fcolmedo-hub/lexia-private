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


def test_case_keeps_principal_branches_questions_and_their_sources(tmp_path) -> None:
    repository = CaseRepository(tmp_path / "cases.sqlite3")
    case_id = repository.create_case(
        "Pérez c/ Empresa X",
        "Diferencias salariales.",
        authority="Juzgado Laboral N.º 2",
        file_number="12345/2026",
    )
    document_id = repository.link_document(
        case_id,
        document_name="Demanda.pdf",
        document_path="/Biblioteca/Escritos/demanda.pdf",
        category="Escritos",
    )
    demand_id = repository.add_node(
        case_id,
        node_kind="hito",
        title="Demanda",
        primary_document_id=document_id,
    )
    question_id = repository.add_node(
        case_id,
        node_kind="cuestion",
        parent_id=demand_id,
        title="Fecha de ingreso",
        adversary_text="La actora denuncia ingreso el 1/11/2022.",
        own_position="La fecha no se encuentra acreditada.",
    )
    repository.add_node_source(
        case_id,
        question_id,
        case_document_id=document_id,
        stance="fundamento",
    )

    snapshot = repository.case_snapshot(case_id)

    assert snapshot["case"]["authority"] == "Juzgado Laboral N.º 2"
    assert snapshot["nodes"][0]["title"] == "Demanda"
    assert snapshot["nodes"][0]["primary_document_name"] == "Demanda.pdf"
    question = snapshot["nodes"][0]["children"][0]
    assert question["adversary_text"] == "La actora denuncia ingreso el 1/11/2022."
    assert question["own_position"] == "La fecha no se encuentra acreditada."
    assert question["sources"][0]["document_name"] == "Demanda.pdf"


def test_deleting_principal_branch_removes_its_questions_but_not_documents(tmp_path) -> None:
    repository = CaseRepository(tmp_path / "cases.sqlite3")
    case_id = repository.create_case("Prueba")
    document_id = repository.link_document(
        case_id,
        document_name="Demanda.pdf",
        document_path="/Biblioteca/Escritos/demanda.pdf",
    )
    branch_id = repository.add_node(case_id, node_kind="hito", title="Demanda")
    question_id = repository.add_node(
        case_id, node_kind="cuestion", parent_id=branch_id, title="Cuestión"
    )
    repository.add_node_source(case_id, question_id, case_document_id=document_id)

    repository.delete_node(case_id, branch_id)

    snapshot = repository.case_snapshot(case_id)
    assert snapshot["nodes"] == []
    assert len(snapshot["documents"]) == 1


def test_deleting_block_releases_only_its_unreferenced_imported_document(tmp_path) -> None:
    repository = CaseRepository(tmp_path / "cases.sqlite3")
    case_id = repository.create_case("Prueba")
    imported_id = repository.link_document(
        case_id,
        document_name="escrito.docx",
        document_path="/Biblioteca/Escritos/Casos/Prueba/escrito.docx",
        category="Escritos",
        relation_kind="archivo de rama",
    )
    library_id = repository.link_document(
        case_id,
        document_name="fallo.pdf",
        document_path="/Biblioteca/Jurisprudencia/fallo.pdf",
        category="Jurisprudencia",
    )
    root_id = repository.add_node(
        case_id, node_kind="hito", title="Demanda", primary_document_id=library_id
    )
    question_id = repository.add_node(case_id, node_kind="cuestion", parent_id=root_id, title="Cuestión")
    repository.add_node_source(case_id, question_id, case_document_id=imported_id, stance="archivo de rama")
    block_id = repository.add_argument_block(case_id, question_id, side="contraparte")
    repository.add_block_highlight(case_id, block_id, case_document_id=imported_id, selected_text="Texto elegido")
    repository.add_node_source(case_id, root_id, case_document_id=library_id, stance="fundamento")

    orphaned = repository.delete_argument_block(case_id, block_id)

    assert [item["id"] for item in orphaned] == [imported_id]
    assert [item["id"] for item in repository.list_documents(case_id)] == [library_id]


def test_deleting_block_keeps_an_imported_document_used_by_another_block(tmp_path) -> None:
    repository = CaseRepository(tmp_path / "cases.sqlite3")
    case_id = repository.create_case("Prueba")
    document_id = repository.link_document(
        case_id,
        document_name="escrito.docx",
        document_path="/Biblioteca/Escritos/Casos/Prueba/escrito.docx",
        category="Escritos",
        relation_kind="archivo de rama",
    )
    foundation_id = repository.link_document(
        case_id,
        document_name="demanda.pdf",
        document_path="/Biblioteca/Escritos/demanda.pdf",
        category="Escritos",
    )
    root_id = repository.add_node(
        case_id, node_kind="hito", title="Demanda", primary_document_id=foundation_id
    )
    question_id = repository.add_node(case_id, node_kind="cuestion", parent_id=root_id, title="Cuestión")
    first_block = repository.add_argument_block(case_id, question_id, side="contraparte")
    second_block = repository.add_argument_block(case_id, question_id, side="contraparte")
    repository.add_block_highlight(case_id, first_block, case_document_id=document_id, selected_text="Primer pasaje")
    repository.add_block_highlight(case_id, second_block, case_document_id=document_id, selected_text="Segundo pasaje")

    orphaned = repository.delete_argument_block(case_id, first_block)

    assert orphaned == []
    assert {item["id"] for item in repository.list_documents(case_id)} == {document_id, foundation_id}

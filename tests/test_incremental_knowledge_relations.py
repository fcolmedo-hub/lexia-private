from dataclasses import dataclass
from pathlib import Path

from knowledge.repository import KnowledgeRepository


@dataclass
class FakeDocument:
    document_path: str
    content_hash: str
    document_name: str
    category: str
    court: str = ""
    jurisdiction: str = ""
    decision_date: str = ""
    document_type: str = ""
    matter: str = ""
    concepts: tuple[str, ...] = ()
    citations: tuple[str, ...] = ()


def test_incremental_relation_created(tmp_path: Path):
    repository = KnowledgeRepository(
        tmp_path / "knowledge.sqlite3"
    )

    repository.save(
        FakeDocument(
            "A.pdf",
            "1",
            "A",
            "Jurisprudencia",
            concepts=("IVA", "AFIP"),
        )
    )
    repository.save(
        FakeDocument(
            "B.pdf",
            "2",
            "B",
            "Jurisprudencia",
            concepts=("IVA", "AFIP"),
        )
    )

    with repository._connect() as connection:
        row = connection.execute(
            """
            SELECT document_count
            FROM concept_relations
            WHERE source_concept = 'AFIP'
              AND target_concept = 'IVA'
            """
        ).fetchone()

    assert row is not None
    assert row["document_count"] == 2


def test_remove_updates_only_relation(tmp_path: Path):
    repository = KnowledgeRepository(
        tmp_path / "knowledge.sqlite3"
    )

    for name in ("A.pdf", "B.pdf", "C.pdf"):
        repository.save(
            FakeDocument(
                name,
                name,
                name,
                "Jurisprudencia",
                concepts=("IVA", "AFIP"),
            )
        )

    repository.remove_path("A.pdf")

    with repository._connect() as connection:
        row = connection.execute(
            """
            SELECT document_count
            FROM concept_relations
            WHERE source_concept = 'AFIP'
              AND target_concept = 'IVA'
            """
        ).fetchone()

    assert row is not None
    assert row["document_count"] == 2


def test_move_preserves_knowledge(tmp_path: Path):
    repository = KnowledgeRepository(
        tmp_path / "knowledge.sqlite3"
    )

    repository.save(
        FakeDocument(
            "old/A.pdf",
            "1",
            "A",
            "Jurisprudencia",
            concepts=("IVA", "AFIP"),
        )
    )

    assert repository.move_path(
        "old/A.pdf",
        "new/A.pdf",
    ) == 1

    assert not repository.knowledge_for_path(
        "old/A.pdf"
    )
    assert repository.knowledge_for_path(
        "new/A.pdf"
    )


def test_manual_rebuild_still_works(tmp_path: Path):
    repository = KnowledgeRepository(
        tmp_path / "knowledge.sqlite3"
    )

    repository.save(
        FakeDocument(
            "A.pdf",
            "1",
            "A",
            "Jurisprudencia",
            concepts=("IVA", "AFIP"),
        )
    )
    repository.save(
        FakeDocument(
            "B.pdf",
            "2",
            "B",
            "Jurisprudencia",
            concepts=("IVA", "AFIP"),
        )
    )

    repository.rebuild_relations()

    with repository._connect() as connection:
        row = connection.execute(
            """
            SELECT document_count
            FROM concept_relations
            WHERE source_concept = 'AFIP'
              AND target_concept = 'IVA'
            """
        ).fetchone()

    assert row is not None
    assert row["document_count"] == 2

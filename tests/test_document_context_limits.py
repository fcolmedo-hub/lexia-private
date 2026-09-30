"""Limit boundaries and real builder methods, without OCR/Qdrant startup."""
import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

from ai.document_context_limits import (
    DocumentContextLimitError,
    require_complete_documents,
)


ROOT = Path(__file__).resolve().parents[1]


def builder_method(filename, class_name, method_name, namespace):
    # Load the production method alone so these checks do not start the
    # application's catalog, OCR or vector dependencies.
    tree = ast.parse((ROOT / "ai" / filename).read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == class_name)
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                  and node.name == method_name)
    module = ast.Module(body=[method], type_ignores=[])
    exec(compile(module, filename, "exec"), namespace)
    return namespace[method_name]


class DocumentContextLimitsTests(unittest.TestCase):
    def test_exact_boundary_is_complete(self):
        require_complete_documents([{"name": "ley.pdf", "text": "x" * 10}], 10)

    def test_only_oversized_sources_are_reported(self):
        with self.assertRaises(DocumentContextLimitError) as caught:
            require_complete_documents([
                {"name": "fallo.pdf", "text": "x" * 11},
                {"name": "ley.pdf", "text": "x" * 10},
                {"name": "doctrina.pdf", "text": "x" * 12},
            ], 10)
        self.assertEqual(caught.exception.limit, 10)
        self.assertEqual([d["name"] for d in caught.exception.documents],
                         ["fallo.pdf", "doctrina.pdf"])
        self.assertIn("No se envió", str(caught.exception))

    def make_multiple_builder(self, texts):
        settings = SimpleNamespace(
            catalog_path="unused.sqlite3",
            context_builder_max_total_chars=52000,
            context_builder_upload_max_chars=95000,
        )
        catalog = SimpleNamespace(get_file_state=lambda path: {
            "text_content": texts[str(path)], "is_deleted": 0,
            "extraction_method": "catalog", "total_pages": 100,
        })
        namespace = dict(
            Path=Path, datetime=datetime, SETTINGS=settings,
            DocumentCatalog=lambda _: catalog, ContextPackage=SimpleNamespace,
            require_complete_documents=require_complete_documents,
        )
        method = builder_method("knowledge_context_builder.py",
                                "KnowledgeContextPackageBuilder",
                                "build_documents_package", namespace)
        owner = SimpleNamespace(TASKS={"Análisis de jurisprudencia": "Analizá"})
        return method, owner

    def test_actual_single_source_budget_for_all_document_types(self):
        for document_type in ("Fallo judicial", "Legislación", "Doctrina", "Libro"):
            with self.subTest(document_type=document_type):
                method, owner = self.make_multiple_builder({"a.pdf": "x" * 47841})
                with self.assertRaises(DocumentContextLimitError) as caught:
                    method(owner, ["a.pdf"], document_type=document_type)
                self.assertEqual(caught.exception.limit, 47840)

    def test_actual_builder_keeps_all_text_at_limit(self):
        text = "x" * 47840
        method, owner = self.make_multiple_builder({"a.pdf": text})
        package = method(owner, ["a.pdf"])
        self.assertIn(text, package.content)
        self.assertNotIn("TRUNCADO", package.content)

    def test_shared_budget_rejects_second_source(self):
        method, owner = self.make_multiple_builder({
            "a.pdf": "x", "b.pdf": "y" * 23921,
        })
        with self.assertRaises(DocumentContextLimitError) as caught:
            method(owner, ["a.pdf", "b.pdf"])
        self.assertEqual(caught.exception.limit, 23920)
        self.assertEqual(caught.exception.documents[0]["name"], "b.pdf")

    def test_legacy_builder_also_rejects_recognition_cut(self):
        settings = SimpleNamespace(context_builder_upload_max_chars=95000)
        owner = SimpleNamespace(
            extractor=SimpleNamespace(extract=lambda _: SimpleNamespace(text="x" * 95001)),
        )
        namespace = dict(Path=Path, SETTINGS=settings, ContextPackage=SimpleNamespace,
                         require_complete_documents=require_complete_documents)
        method = builder_method("context_package_builder.py", "ContextPackageBuilder",
                                "build_document_package", namespace)
        with self.assertRaises(DocumentContextLimitError) as caught:
            method(owner, "a.pdf")
        self.assertEqual(caught.exception.limit, 95000)


if __name__ == "__main__":
    unittest.main()

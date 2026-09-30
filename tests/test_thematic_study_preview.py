from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

class ThematicStudyPreviewTest(TestCase):
    def test_reports_selected_passages_and_budget_cut(self):
        # La selección semántica se sustituye más abajo; esta prueba solo
        # necesita importar el constructor sin levantar Qdrant.
        try:
            from ai import thematic_document_study as thematic
        except ModuleNotFoundError as error:
            if error.name != "qdrant_client":
                raise
            with patch.dict(sys.modules, {"qdrant_client": SimpleNamespace(models=SimpleNamespace())}):
                from ai import thematic_document_study as thematic
        fragment = {
            "fragment_index": 0, "text_content": "tema jurídico " * 6000,
            "page_start": 1, "page_end": 20,
        }
        document = {
            "name": "doctrina.pdf", "path": "/tmp/doctrina.pdf", "category": "Doctrina",
            "pages": 20, "method": "ocr", "fragments": [fragment],
        }
        builder = SimpleNamespace(
            TASKS={"Investigación jurídica": "Analizar las fuentes."},
            _safe_title=lambda text: text,
        )
        region = {"indices": [0], "score": 0.9, "page_start": 1, "page_end": 20}
        with (
            patch.object(thematic, "_load_document", return_value=document),
            patch.object(thematic, "_query_variants", return_value=["tema jurídico"]),
            patch.object(thematic, "_semantic_scores", return_value={}),
            patch.object(thematic, "_rank_fragments", return_value=([(0.9, 0)], {0: fragment}, {0: 0.9})),
            patch.object(thematic, "_selected_regions", return_value=[region]),
        ):
            package = thematic._build_thematic_package(
                builder, object(), object(), [(Path("doctrina.pdf"), "doctrina.pdf")],
                "Investigación jurídica", "tema jurídico", "Doctrina",
            )

        selection = package.interpretation["study_selection"]
        self.assertEqual(selection["kind"], "thematic")
        self.assertEqual(selection["regions_found"], 1)
        self.assertEqual(selection["regions_included"], 1)
        self.assertTrue(selection["cut_by_budget"])
        self.assertGreater(selection["included_characters"], 0)
        self.assertIn("CORTE POR LÍMITE DEL PAQUETE", package.content)

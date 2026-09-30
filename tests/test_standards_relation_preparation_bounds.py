import sqlite3
import unittest

from tools.preparar_canonicalizacion_estandares import build_candidates


class RelationPreparationBoundsTests(unittest.TestCase):
    def test_dense_common_vocabulary_keeps_every_pair_in_same_document(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.executescript("""
            CREATE TABLE documents(document_id INTEGER PRIMARY KEY, document_name TEXT,
                                   court TEXT, judgment_date TEXT);
            CREATE TABLE standards(standard_uid TEXT, document_id INTEGER, statement TEXT,
                speaker TEXT, source_speaker TEXT, treatment TEXT, conditions_json TEXT,
                consequence TEXT, exceptions_json TEXT, review_status TEXT, publication_status TEXT);
            CREATE TABLE quotes(standard_uid TEXT, evidence_index INTEGER, quote_text TEXT);
        """)
        for number in range(200):
            if number % 2 == 0:
                conn.execute("INSERT INTO documents VALUES (?, ?, ?, ?)",
                             (number // 2, str(number), "tribunal", ""))
            conn.execute("INSERT INTO standards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (str(number), number // 2,
                          "El tribunal considera criterio administrativo relevante",
                          "tribunal", "tribunal", "adopta", "[]", "", "[]", "validated", "ready"))

        candidates = build_candidates(conn, 0.08, 1, 24,
                                      max_posting_size=10, max_pair_pool=200)
        self.assertEqual(len(candidates), 100)
        self.assertTrue(all(item["same_document"] for item in candidates))


if __name__ == "__main__":
    unittest.main()

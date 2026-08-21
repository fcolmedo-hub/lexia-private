from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import SETTINGS
from knowledge.citation_graph import CitationGraphEngine

engine = CitationGraphEngine(SETTINGS.knowledge_path)

before = engine.stats()
print("Antes")
print(f"Resueltas: {before.resolved_edges}")
print(f"No resueltas: {before.unresolved_edges}")

after = engine.rebuild()

print()
print("Después — Jurisprudential Citation Resolver 2.0")
print(f"Nodos de cita: {after.citation_nodes}")
print(f"Aristas: {after.edges}")
print(f"Resueltas: {after.resolved_edges}")
print(f"No resueltas: {after.unresolved_edges}")
print(f"Documentos fuente: {after.source_documents}")

if after.edges:
    rate = after.resolved_edges / after.edges * 100
else:
    rate = 0.0

print(f"Tasa de resolución: {rate:.2f}%")

with sqlite3.connect(SETTINGS.knowledge_path) as con:
    rows = con.execute(
        """
        SELECT resolution_method, COUNT(*)
        FROM citation_nodes
        WHERE resolved_document_path IS NOT NULL
        GROUP BY resolution_method
        ORDER BY COUNT(*) DESC
        LIMIT 15
        """
    ).fetchall()

if rows:
    print()
    print("Métodos de resolución:")
    for method, count in rows:
        print(f"- {method}: {count}")

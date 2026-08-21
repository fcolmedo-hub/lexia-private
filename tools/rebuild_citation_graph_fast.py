from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import SETTINGS
from knowledge.citation_graph import CitationGraphEngine

engine = CitationGraphEngine(SETTINGS.knowledge_path)
before = engine.stats()

print("Citation Graph Resolver 2.1 — reconstrucción optimizada")
print(f"Antes: {before.resolved_edges} resueltas / {before.unresolved_edges} no resueltas")
print("Procesando con índices invertidos...", flush=True)

started = time.perf_counter()
after = engine.rebuild()
elapsed = time.perf_counter() - started

rate = (
    after.resolved_edges / after.edges * 100
    if after.edges else 0.0
)

print()
print("Finalizado")
print(f"Tiempo: {elapsed:.2f} s")
print(f"Nodos de cita: {after.citation_nodes}")
print(f"Aristas: {after.edges}")
print(f"Resueltas: {after.resolved_edges}")
print(f"No resueltas: {after.unresolved_edges}")
print(f"Documentos fuente: {after.source_documents}")
print(f"Tasa de resolución: {rate:.2f}%")

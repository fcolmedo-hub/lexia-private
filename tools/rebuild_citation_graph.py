from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import SETTINGS
from knowledge.citation_graph import CitationGraphEngine

engine = CitationGraphEngine(SETTINGS.knowledge_path)
stats = engine.rebuild()

print("Citation Graph Engine")
print(f"Nodos de cita: {stats.citation_nodes}")
print(f"Aristas: {stats.edges}")
print(f"Resueltas: {stats.resolved_edges}")
print(f"No resueltas: {stats.unresolved_edges}")
print(f"Documentos fuente: {stats.source_documents}")

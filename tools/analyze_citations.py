from pathlib import Path
import csv
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import SETTINGS
from knowledge.citation_analyzer import CitationAnalyzer

analyzer = CitationAnalyzer(SETTINGS.knowledge_path)
result = analyzer.analyze()
summary = result["summary"]

print("Citation Analyzer")
print()
print(f"Aristas totales: {summary.total_edges}")
print(f"Citas distintas: {summary.distinct_citations}")
print(f"Resueltas: {summary.resolved_edges}")
print(f"No resueltas: {summary.unresolved_edges}")
print(f"Documentos fuente: {summary.source_documents}")
print()
print("Clasificación:")
print(f"- Fallos tomo:página: {summary.fallos_refs}")
print(f"- Nombre de causa: {summary.case_names}")
print(f"- Número de causa/expediente: {summary.case_numbers}")
print(f"- Sólo tribunal: {summary.tribunal_only}")
print(f"- Sólo fecha: {summary.date_only}")
print(f"- Referencia normativa: {summary.normative_refs}")
print(f"- Texto genérico: {summary.generic_text}")
print(f"- Ruido / inválidas: {summary.invalid_like}")

output_dir = ROOT / "runtime" / "citation_analysis"
output_dir.mkdir(parents=True, exist_ok=True)

summary_path = output_dir / "citation_analysis_summary.json"
summary_path.write_text(
    json.dumps(
        {
            "summary": summary.__dict__,
            "category_counts": result["category_counts"],
            "top_citations": result["top_citations"],
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)

csv_path = output_dir / "citation_analysis_rows.csv"
with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "citation",
            "category",
            "resolved",
            "confidence",
            "source_document_path",
            "target_document_path",
        ],
    )
    writer.writeheader()
    writer.writerows(result["rows"])

top_path = output_dir / "top_100_citations.txt"
with top_path.open("w", encoding="utf-8") as handle:
    for index, (citation, count) in enumerate(
        result["top_citations"],
        start=1,
    ):
        handle.write(f"{index:03d}. [{count}] {citation}\n")

print()
print("Archivos generados:")
print(f"- {summary_path}")
print(f"- {csv_path}")
print(f"- {top_path}")

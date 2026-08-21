from services.ocr_pending_recovery_service import OCRPendingRecoveryService

r = OCRPendingRecoveryService().run()
print("OCR Pending Recovery")
print(f"Examinados: {r.examined}")
print(f"Recuperados: {r.recovered}")
print(f"Omitidos por texto insuficiente: {r.skipped_short_text}")
print(f"Archivos ausentes: {r.missing_files}")
print(f"Errores: {r.errors}")
print(f"Fragmentos generados: {r.fragments_generated}")

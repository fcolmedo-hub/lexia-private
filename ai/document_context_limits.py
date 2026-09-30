"""Reject incomplete document studies before any paid API request."""


class DocumentContextLimitError(ValueError):
    def __init__(self, documents, limit):
        self.documents = documents
        self.limit = limit
        details = "; ".join(
            f"'{item['name']}': {item['characters']:,} caracteres"
            for item in documents
        )
        super().__init__(
            "Estudio detenido: el documento excede el límite de contexto. "
            f"Límite disponible por documento: {limit:,} caracteres. {details}. "
            "No se envió el documento al API ni se consumieron tokens del estudio. "
            "Dividí el archivo en partes más pequeñas y volvé a estudiarlo. "
            "LexIA no enviará un análisis con el contenido recortado."
        )


def require_complete_documents(documents, limit):
    """Use the exact source budget chosen by the context builder."""
    oversized = [
        {"name": item["name"], "characters": len(item["text"])}
        for item in documents
        if len(item["text"]) > limit
    ]
    if oversized:
        raise DocumentContextLimitError(oversized, limit)

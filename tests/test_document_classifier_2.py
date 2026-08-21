from core.document_classifier import (
    DeterministicDocumentClassifier,
)


def test_classifies_judgment():
    classifier = DeterministicDocumentClassifier()
    result = classifier.classify(
        """
        CORTE SUPREMA DE JUSTICIA DE LA NACIÓN
        SENTENCIA
        Considerando que...
        Por ello, el Tribunal RESUELVE:
        """,
        "documento.pdf",
    )
    assert result.document_type == "Jurisprudencia"


def test_classifies_legal_brief():
    classifier = DeterministicDocumentClassifier()
    result = classifier.classify(
        """
        SEÑOR JUEZ:
        Que vengo a interponer recurso de apelación.
        OBJETO
        PETITORIO
        Proveer de conformidad.
        """,
        "archivo.pdf",
    )
    assert result.document_type == "Escritos"
    assert result.subtype == "Recurso de apelación"


def test_folder_does_not_affect_classification():
    classifier = DeterministicDocumentClassifier()
    text = """
    LEY 26944
    El Senado y Cámara de Diputados...
    ARTÍCULO 1° —
    PROMÚLGASE.
    """
    first = classifier.classify(
        text,
        "data/Jurisprudencia/archivo.pdf",
    )
    second = classifier.classify(
        text,
        "data/Inbox/archivo.pdf",
    )
    assert first.document_type == "Legislación"
    assert (
        first.document_type
        == second.document_type
    )

from storage.jurisprudence_content_probe import extract


def test_rejects_narrative_court_sentence():
    result = extract(
        "CAMARA SEÑALÓ QUE RESULTABA CONTRARIO AL PRINCIPIO\n",
        context={"hierarchy_group": "CSJN", "scope": "Nacional", "province": ""},
    )
    assert result["court"] == ""


def test_csjn_rejects_lower_court_chamber_and_provincial_court():
    result = extract(
        """
CORTE SUPREMA DE JUSTICIA (SANTA FE) - SANTA FE
Sala II
Fecha de firma: 23/10/2025
""",
        context={"hierarchy_group": "CSJN", "scope": "Nacional", "province": ""},
    )
    assert result["court"] == ""
    assert result["chamber"] == ""
    assert result["date"] == "2025-10-23"


def test_csjn_accepts_national_supreme_court():
    result = extract(
        """
CORTE SUPREMA DE JUSTICIA DE LA NACIÓN
Buenos Aires, 11 de Marzo de 2021
""",
        context={"hierarchy_group": "CSJN", "scope": "Nacional", "province": ""},
    )
    assert result["court"] == "CORTE SUPREMA DE JUSTICIA DE LA NACIÓN"
    assert result["chamber"] == ""
    assert result["date"] == "2021-03-11"


def test_rejects_weak_single_letter_case_prefix():
    result = extract("Expediente N° s 620\n")
    assert result["case_number"] == ""


def test_accepts_known_style_case_prefix():
    result = extract("CAUSA N° CPE 835/2018\n")
    assert result["case_number"] == "CPE 835/2018"

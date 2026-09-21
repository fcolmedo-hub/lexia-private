from zipfile import ZipFile

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt

from services.docx_exporter import DocxExporter


def _export(tmp_path, content="# CONTESTA TRASLADO\n\nTexto de la contestación."):
    path = tmp_path / "contestacion.docx"
    DocxExporter().export_markdown_like(
        "Contestación · Audiencia",
        content,
        path,
    )
    return path, DocxDocument(path)


def test_export_uses_fixed_a4_mirrored_margins(tmp_path):
    path, document = _export(tmp_path)
    section = document.sections[0]

    assert abs(section.page_width - Mm(210)) < 1000
    assert abs(section.page_height - Mm(297)) < 1000
    assert abs(section.top_margin - Cm(4)) < 1000
    assert abs(section.bottom_margin - Cm(2)) < 1000
    assert abs(section.left_margin - Cm(4)) < 1000
    assert abs(section.right_margin - Cm(2)) < 1000

    with ZipFile(path) as package:
        settings = package.read("word/settings.xml").decode("utf-8")
    assert "<w:mirrorMargins" in settings


def test_export_uses_times_new_roman_12_and_one_point_five_spacing(tmp_path):
    _path, document = _export(tmp_path)
    normal = document.styles["Normal"]
    assert normal.font.name == "Times New Roman"
    assert normal.font.size == Pt(12)
    assert normal.paragraph_format.line_spacing == 1.5

    body = next(
        paragraph for paragraph in document.paragraphs
        if paragraph.text == "Texto de la contestación."
    )
    assert body.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY
    assert body.paragraph_format.line_spacing == 1.5
    assert body.paragraph_format.space_before == Pt(0)
    assert body.paragraph_format.space_after == Pt(0)
    assert body.runs[0].font.name == "Times New Roman"
    assert body.runs[0].font.size == Pt(12)
    fonts = body.runs[0]._r.rPr.rFonts
    assert fonts.get(qn("w:ascii")) == "Times New Roman"
    assert fonts.get(qn("w:hAnsi")) == "Times New Roman"
    assert document.styles["Title"].element.pPr.find(qn("w:pBdr")) is None


def test_export_sets_26_line_grid_and_footer_page_number(tmp_path):
    path, document = _export(tmp_path)
    section = document.sections[0]
    grid = section._sectPr.find(qn("w:docGrid"))
    usable_height_twips = int(Cm(29.7 - 4 - 2)) / 635
    expected_pitch = round(usable_height_twips / 26)

    assert grid is not None
    assert grid.get(qn("w:type")) == "lines"
    assert int(grid.get(qn("w:linePitch"))) == expected_pitch
    assert abs(section.footer_distance - Cm(1.2)) < 1000

    footer = section.footer.paragraphs[0]
    assert footer.alignment == WD_ALIGN_PARAGRAPH.CENTER
    assert " PAGE " in footer._p.xml
    assert footer.runs[0].font.name == "Times New Roman"
    assert footer.runs[0].font.size == Pt(12)

    with ZipFile(path) as package:
        settings = package.read("word/settings.xml").decode("utf-8")
    assert '<w:updateFields w:val="true"' in settings


def test_export_has_no_template_or_marker_requirement(tmp_path):
    path, document = _export(tmp_path, "Respuesta lista para presentar.")
    assert path.is_file()
    assert "Respuesta lista para presentar." in [
        paragraph.text for paragraph in document.paragraphs
    ]

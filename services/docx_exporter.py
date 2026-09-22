from pathlib import Path
import re

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor


class DocxExporter:
    """Create editable legal Word files with LexIA's fixed court format."""

    FONT_NAME = "Times New Roman"
    FONT_SIZE_PT = 12
    PAGE_WIDTH_MM = 210
    PAGE_HEIGHT_MM = 297
    TOP_MARGIN_CM = 4
    BOTTOM_MARGIN_CM = 2
    INNER_MARGIN_CM = 4
    OUTER_MARGIN_CM = 2
    # 516 twips: allows 26 effective text lines with the court margins below.
    # 517 twips makes Word/LibreOffice drop an additional line on many pages.
    LINE_PITCH_PT = 25.8
    FIRST_LINE_INDENT_CM = 1.5
    MAX_LINES_PER_PAGE = 26
    FOOTER_GAP_FROM_TEXT_CM = 0.8

    def export_markdown_like(
        self,
        title: str,
        content: str,
        destination: str | Path,
    ) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)

        document = DocxDocument()
        self._configure_document(document)
        self._add_paragraph(
            document,
            str(title or "").strip().upper(),
            "Title",
            bold=True,
            underline=True,
        )

        for kind, text, level in self._content_blocks(content):
            if kind == "chapter":
                self._add_paragraph(
                    document,
                    text,
                    "Heading 1",
                    bold=True,
                )
            elif kind == "subchapter":
                self._add_paragraph(
                    document,
                    text,
                    f"Heading {min(max(level, 2), 3)}",
                    left_indent=True,
                )
            elif kind == "bullet":
                self._add_paragraph(document, "• " + text, "Normal")
            elif kind == "number":
                self._add_paragraph(document, text, "Normal")
            else:
                self._add_paragraph(
                    document,
                    text,
                    "Normal",
                    first_line_indent=True,
                )

        document.save(path)
        return path

    def _configure_document(self, document):
        section = document.sections[0]
        section.page_width = Mm(self.PAGE_WIDTH_MM)
        section.page_height = Mm(self.PAGE_HEIGHT_MM)
        section.top_margin = Cm(self.TOP_MARGIN_CM)
        section.bottom_margin = Cm(self.BOTTOM_MARGIN_CM)
        section.left_margin = Cm(self.INNER_MARGIN_CM)
        section.right_margin = Cm(self.OUTER_MARGIN_CM)
        section.gutter = Cm(0)
        section.footer_distance = Cm(
            self.BOTTOM_MARGIN_CM - self.FOOTER_GAP_FROM_TEXT_CM
        )

        self._enable_mirrored_margins(document)
        self._set_page_grid(section)
        self._configure_styles(document)
        self._add_page_number(section)
        self._request_field_updates(document)

    @staticmethod
    def _enable_mirrored_margins(document):
        settings = document.settings.element
        if settings.find(qn("w:mirrorMargins")) is None:
            settings.append(OxmlElement("w:mirrorMargins"))

    def _set_page_grid(self, section):
        usable_height = Cm(
            self.PAGE_HEIGHT_MM / 10
            - self.TOP_MARGIN_CM
            - self.BOTTOM_MARGIN_CM
        )
        line_pitch_twips = round(
            int(usable_height) / 635 / self.MAX_LINES_PER_PAGE
        )
        section_properties = section._sectPr
        grid = section_properties.find(qn("w:docGrid"))
        if grid is None:
            grid = OxmlElement("w:docGrid")
            section_properties.append(grid)
        grid.set(qn("w:type"), "lines")
        grid.set(qn("w:linePitch"), str(line_pitch_twips))

    def _configure_styles(self, document):
        for style_name in (
            "Normal",
            "Title",
            "Heading 1",
            "Heading 2",
            "Heading 3",
            "List Bullet",
            "List Number",
        ):
            style = document.styles[style_name]
            self._set_style_font(style)
            paragraph_format = style.paragraph_format
            paragraph_format.line_spacing = Pt(self.LINE_PITCH_PT)
            paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
            paragraph_format.space_before = Pt(0)
            paragraph_format.space_after = Pt(0)
            paragraph_format.keep_with_next = False
            self._disable_grid_snapping(style.element.get_or_add_pPr())

        document.styles["Normal"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        document.styles["Title"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        document.styles["Title"].font.bold = True
        title_properties = document.styles["Title"].element.get_or_add_pPr()
        title_border = title_properties.find(qn("w:pBdr"))
        if title_border is not None:
            title_properties.remove(title_border)
        document.styles["Heading 1"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        document.styles["Heading 1"].font.bold = True
        for style_name in ("Heading 2", "Heading 3"):
            document.styles[style_name].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
            document.styles[style_name].paragraph_format.left_indent = Cm(
                self.FIRST_LINE_INDENT_CM
            )
            document.styles[style_name].font.bold = False

    def _set_style_font(self, style):
        style.font.name = self.FONT_NAME
        style.font.size = Pt(self.FONT_SIZE_PT)
        style.font.color.rgb = RGBColor(0, 0, 0)
        run_properties = style.element.get_or_add_rPr()
        fonts = run_properties.rFonts
        if fonts is None:
            fonts = OxmlElement("w:rFonts")
            run_properties.insert(0, fonts)
        for attribute in ("ascii", "hAnsi", "eastAsia", "cs"):
            fonts.set(qn(f"w:{attribute}"), self.FONT_NAME)
        color = run_properties.find(qn("w:color"))
        if color is not None:
            color.set(qn("w:val"), "000000")
            color.attrib.pop(qn("w:themeColor"), None)

    def _add_paragraph(
        self,
        document,
        text,
        style,
        *,
        bold=False,
        underline=False,
        first_line_indent=False,
        left_indent=False,
    ):
        paragraph = document.add_paragraph(style=style)
        paragraph.paragraph_format.line_spacing = Pt(self.LINE_PITCH_PT)
        paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.keep_with_next = False
        paragraph.paragraph_format.first_line_indent = Cm(
            self.FIRST_LINE_INDENT_CM if first_line_indent else 0
        )
        paragraph.paragraph_format.left_indent = Cm(
            self.FIRST_LINE_INDENT_CM if left_indent else 0
        )
        if style == "Normal":
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        elif style == "Title":
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        elif style == "Heading 1":
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif style in ("Heading 2", "Heading 3"):
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        self._disable_grid_snapping(paragraph._p.get_or_add_pPr())
        if text:
            self._write_rich_text(
                paragraph,
                text,
                force_bold=bold,
                force_underline=underline,
            )
        return paragraph

    @staticmethod
    def _disable_grid_snapping(paragraph_properties):
        snap = paragraph_properties.find(qn("w:snapToGrid"))
        if snap is None:
            snap = OxmlElement("w:snapToGrid")
            paragraph_properties.append(snap)
        snap.set(qn("w:val"), "0")

    def _write_rich_text(
        self,
        paragraph,
        text,
        *,
        force_bold=False,
        force_underline=False,
    ):
        parts = re.split(r"(\*\*.+?\*\*|(?<!\*)\*[^*]+?\*(?!\*))", str(text or ""))
        for part in parts:
            if not part:
                continue
            bold = force_bold
            italic = False
            value = part
            if part.startswith("**") and part.endswith("**"):
                value = part[2:-2]
                bold = True
            elif part.startswith("*") and part.endswith("*"):
                value = part[1:-1]
                italic = True
            run = paragraph.add_run(value)
            self._set_run_font(run)
            if bold:
                run.bold = True
            if force_underline:
                run.underline = True
            if italic:
                run.italic = True

    def _set_run_font(self, run):
        run.font.name = self.FONT_NAME
        run.font.size = Pt(self.FONT_SIZE_PT)
        run.font.color.rgb = RGBColor(0, 0, 0)
        properties = run._element.get_or_add_rPr()
        fonts = properties.rFonts
        if fonts is None:
            fonts = OxmlElement("w:rFonts")
            properties.insert(0, fonts)
        for attribute in ("ascii", "hAnsi", "eastAsia", "cs"):
            fonts.set(qn(f"w:{attribute}"), self.FONT_NAME)

    def _add_page_number(self, section):
        paragraph = section.footer.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.line_spacing = 1

        run = paragraph.add_run()
        self._set_run_font(run)
        begin = OxmlElement("w:fldChar")
        begin.set(qn("w:fldCharType"), "begin")
        instruction = OxmlElement("w:instrText")
        instruction.set(qn("xml:space"), "preserve")
        instruction.text = " PAGE "
        separate = OxmlElement("w:fldChar")
        separate.set(qn("w:fldCharType"), "separate")
        display = OxmlElement("w:t")
        display.text = "1"
        end = OxmlElement("w:fldChar")
        end.set(qn("w:fldCharType"), "end")
        run._r.extend((begin, instruction, separate, display, end))

    @staticmethod
    def _request_field_updates(document):
        settings = document.settings.element
        update = settings.find(qn("w:updateFields"))
        if update is None:
            update = OxmlElement("w:updateFields")
            settings.append(update)
        update.set(qn("w:val"), "true")

    @classmethod
    def _content_blocks(cls, content):
        number_pattern = re.compile(r"^(\d+[.)])\s+(.*)$")
        subchapter_pattern = re.compile(r"^(\d+(?:\.\d+)*)\)\s*(.*)$")
        chapter_pattern = re.compile(
            r"^([IVXLCDM]+)\s*[-–—]\s*(.*)$",
            re.IGNORECASE,
        )
        blocks = []
        chapter_number = 0
        subchapter_number = 0
        for raw_line in str(content or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue

            heading_level = 0
            heading_text = line
            if line.startswith("### "):
                heading_level, heading_text = 3, line[4:].strip()
            elif line.startswith("## "):
                heading_level, heading_text = 2, line[3:].strip()
            elif line.startswith("# "):
                heading_level, heading_text = 1, line[2:].strip()

            explicit_chapter = chapter_pattern.match(heading_text)
            explicit_subchapter = subchapter_pattern.match(heading_text)
            if heading_level == 1 or (not heading_level and explicit_chapter):
                if explicit_chapter:
                    roman = explicit_chapter.group(1).upper()
                    chapter_number = cls._roman_to_int(roman) or chapter_number + 1
                    chapter_title = explicit_chapter.group(2).strip()
                else:
                    chapter_number += 1
                    roman = cls._int_to_roman(chapter_number)
                    chapter_title = heading_text
                subchapter_number = 0
                blocks.append(
                    ("chapter", f"{roman} - {chapter_title.upper()}", 1)
                )
            elif heading_level in (2, 3) or (not heading_level and explicit_subchapter):
                if explicit_subchapter:
                    prefix = explicit_subchapter.group(1)
                    subchapter_title = explicit_subchapter.group(2).strip()
                else:
                    if chapter_number < 1:
                        chapter_number = 1
                    subchapter_number += 1
                    prefix = f"{chapter_number}.{subchapter_number}"
                    subchapter_title = heading_text
                if subchapter_title and subchapter_title[-1] not in ".?!":
                    subchapter_title += "."
                blocks.append(
                    ("subchapter", f"{prefix}) {subchapter_title}".rstrip(), heading_level or 2)
                )
            elif line.startswith("- "):
                blocks.append(("bullet", line[2:].strip(), 0))
            else:
                numbered = number_pattern.match(line)
                if numbered:
                    blocks.append(
                        ("number", f"{numbered.group(1)} {numbered.group(2).strip()}", 0)
                    )
                else:
                    blocks.append(("body", line, 0))
        return blocks

    @staticmethod
    def _int_to_roman(number):
        values = (
            (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
            (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
            (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
        )
        remaining = max(1, int(number or 1))
        result = []
        for value, symbol in values:
            while remaining >= value:
                result.append(symbol)
                remaining -= value
        return "".join(result)

    @staticmethod
    def _roman_to_int(value):
        digits = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
        total = previous = 0
        for char in reversed(str(value or "").upper()):
            current = digits.get(char, 0)
            if current < previous:
                total -= current
            else:
                total += current
                previous = current
        return total

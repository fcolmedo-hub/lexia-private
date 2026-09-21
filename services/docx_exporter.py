from copy import deepcopy
from pathlib import Path
import re

from docx import Document as DocxDocument
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.text.paragraph import Paragraph


class DocxExporter:
    """Export LexIA text either to a new DOCX or onto a Word model.

    A model is always opened read-only and the result is saved elsewhere. Its
    package remains the authority for sections, margins, styles, headers,
    footers, numbering, theme and compatibility settings.
    """

    CONTENT_MARKERS = ("[[CONTENIDO_LEXIA]]", "{{CONTENIDO_LEXIA}}")

    def export_markdown_like(
        self,
        title: str,
        content: str,
        destination: str | Path,
        *,
        template: str | Path | None = None,
    ) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)

        if template:
            return self._export_from_template(
                title=title,
                content=content,
                destination=path,
                template=Path(template),
            )

        document = DocxDocument()
        document.add_heading(title, level=0)

        for kind, text, level in self._content_blocks(content):
            if kind == "blank":
                document.add_paragraph()
            elif kind == "heading":
                document.add_heading(text, level=level)
            elif kind == "bullet":
                document.add_paragraph(text, style="List Bullet")
            elif kind == "number":
                document.add_paragraph(text, style="List Number")
            else:
                paragraph = document.add_paragraph(text)
                paragraph.style.font.size = Pt(11)

        document.save(path)
        return path

    def _export_from_template(self, *, title, content, destination, template):
        if not template.is_file():
            raise FileNotFoundError(f"No se encontró el modelo Word: {template}")
        if template.suffix.lower() != ".docx":
            raise ValueError("El modelo Word debe estar guardado en formato .docx.")
        if template.resolve() == destination.resolve():
            raise ValueError("El archivo exportado no puede reemplazar el modelo original.")

        document = DocxDocument(str(template))
        paragraphs = list(document.paragraphs)
        marker = self._find_marker(paragraphs)
        profiles = self._format_profiles(paragraphs, marker)

        if marker is None:
            self._clear_document_body(document)
            reference = document._body._element.sectPr
            include_title = True
        else:
            reference = marker._p
            marker_index = paragraphs.index(marker)
            include_title = not any(
                paragraph.text.strip() for paragraph in paragraphs[:marker_index]
            )

        blocks = []
        if include_title and str(title or "").strip():
            blocks.append(("title", str(title).strip(), 0))
        blocks.extend(self._content_blocks(content))

        for kind, text, level in blocks:
            profile_name = "body"
            force_bold = False
            if kind == "title":
                profile_name = "title"
                force_bold = True
            elif kind == "heading":
                profile_name = f"heading{min(max(level, 1), 3)}"
                force_bold = True

            prefix = ""
            if kind == "bullet":
                prefix = "• "
            elif kind == "number":
                prefix = f"{level}. "

            profile = profiles.get(profile_name) or profiles["body"]
            paragraph = self._insert_paragraph_before(document, reference, profile)
            if kind != "blank":
                self._write_rich_text(
                    paragraph,
                    prefix + text,
                    profile,
                    force_bold=force_bold,
                )

        if marker is not None:
            marker._p.getparent().remove(marker._p)

        document.save(destination)
        return destination

    def _find_marker(self, paragraphs):
        found = None
        for paragraph in paragraphs:
            text = paragraph.text.strip()
            matching = [marker for marker in self.CONTENT_MARKERS if marker in text]
            if not matching:
                continue
            if text not in self.CONTENT_MARKERS:
                raise ValueError(
                    "El marcador [[CONTENIDO_LEXIA]] debe ocupar un párrafo completo."
                )
            if found is not None:
                raise ValueError("El modelo Word contiene más de un marcador de contenido.")
            found = paragraph
        return found

    @staticmethod
    def _clear_document_body(document):
        body = document._body._element
        for child in list(body):
            if child.tag != qn("w:sectPr"):
                body.remove(child)

    def _format_profiles(self, paragraphs, marker):
        candidates = [
            paragraph for paragraph in paragraphs
            if paragraph is not marker and paragraph.text.strip()
        ]
        body_candidates = [
            paragraph for paragraph in candidates
            if not self._looks_like_heading(paragraph) and len(paragraph.text.strip()) >= 35
        ]
        body = marker or (
            max(body_candidates, key=lambda paragraph: len(paragraph.text.strip()))
            if body_candidates else (candidates[0] if candidates else None)
        )

        headings = [paragraph for paragraph in candidates if self._looks_like_heading(paragraph)]
        title = self._first_style_match(candidates, ("title", "titulo", "título"))
        heading1 = self._first_style_match(candidates, ("heading 1", "titulo 1", "título 1"))
        heading2 = self._first_style_match(candidates, ("heading 2", "titulo 2", "título 2"))
        heading3 = self._first_style_match(candidates, ("heading 3", "titulo 3", "título 3"))
        fallback_heading = headings[0] if headings else body

        return {
            "body": self._profile(body),
            "title": self._profile(title or fallback_heading or body),
            "heading1": self._profile(heading1 or fallback_heading or body),
            "heading2": self._profile(heading2 or fallback_heading or body),
            "heading3": self._profile(heading3 or fallback_heading or body),
        }

    @staticmethod
    def _first_style_match(paragraphs, names):
        wanted = tuple(value.casefold() for value in names)
        for paragraph in paragraphs:
            style_name = str(getattr(paragraph.style, "name", "") or "").casefold()
            if any(value in style_name for value in wanted):
                return paragraph
        return None

    @staticmethod
    def _looks_like_heading(paragraph):
        text = paragraph.text.strip()
        style_name = str(getattr(paragraph.style, "name", "") or "").casefold()
        if any(value in style_name for value in ("heading", "title", "titulo", "título")):
            return True
        if not text or len(text) > 160:
            return False
        letters = [character for character in text if character.isalpha()]
        all_caps = bool(letters) and all(character.isupper() for character in letters)
        bold = any(run.bold is True for run in paragraph.runs if run.text.strip())
        return all_caps or bold

    @staticmethod
    def _profile(paragraph):
        if paragraph is None:
            return {"pPr": None, "rPr": None}

        p_pr = deepcopy(paragraph._p.pPr) if paragraph._p.pPr is not None else None
        if p_pr is not None:
            section = p_pr.find(qn("w:sectPr"))
            if section is not None:
                p_pr.remove(section)

        sample_run = next((run for run in paragraph.runs if run.text.strip()), None)
        r_pr = (
            deepcopy(sample_run._r.rPr)
            if sample_run is not None and sample_run._r.rPr is not None
            else None
        )
        return {"pPr": p_pr, "rPr": r_pr}

    @staticmethod
    def _insert_paragraph_before(document, reference, profile):
        paragraph_xml = OxmlElement("w:p")
        if profile.get("pPr") is not None:
            paragraph_xml.append(deepcopy(profile["pPr"]))
        reference.addprevious(paragraph_xml)
        return Paragraph(paragraph_xml, document._body)

    def _write_rich_text(self, paragraph, text, profile, *, force_bold=False):
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
            if profile.get("rPr") is not None:
                if run._r.rPr is not None:
                    run._r.remove(run._r.rPr)
                run._r.insert(0, deepcopy(profile["rPr"]))
            if bold:
                run.bold = True
            if italic:
                run.italic = True

    @staticmethod
    def _content_blocks(content):
        number_pattern = re.compile(r"^(\d+)[.)]\s+(.*)$")
        blocks = []
        for raw_line in str(content or "").splitlines():
            line = raw_line.rstrip()
            if not line:
                blocks.append(("blank", "", 0))
            elif line.startswith("### "):
                blocks.append(("heading", line[4:].strip(), 3))
            elif line.startswith("## "):
                blocks.append(("heading", line[3:].strip(), 2))
            elif line.startswith("# "):
                blocks.append(("heading", line[2:].strip(), 1))
            elif line.startswith("- "):
                blocks.append(("bullet", line[2:].strip(), 0))
            else:
                numbered = number_pattern.match(line)
                if numbered:
                    blocks.append(("number", numbered.group(2).strip(), int(numbered.group(1))))
                else:
                    blocks.append(("body", line, 0))
        return blocks

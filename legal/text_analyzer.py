import re


class LegalWritingAnalyzer:
    SECTIONS = (
        "objeto",
        "hechos",
        "derecho",
        "prueba",
        "petitorio",
        "competencia",
        "legitimación",
        "reserva del caso federal",
    )

    def analyze(self, text: str) -> dict:
        text = text.strip()
        detected = [
            section
            for section in self.SECTIONS
            if re.search(
                rf"\b{re.escape(section)}\b",
                text,
                flags=re.IGNORECASE,
            )
        ]

        omissions = []
        if "prueba" not in detected:
            omissions.append("No se detectó un desarrollo explícito de prueba.")
        if "petitorio" not in detected:
            omissions.append("No se detectó un petitorio claramente identificado.")
        if not re.search(
            r"\b(art\.?|artículo|ley|decreto|resolución)\b",
            text,
            flags=re.IGNORECASE,
        ):
            omissions.append("No se detectaron referencias normativas expresas.")
        if not re.search(
            r"\b(fallos|jurisprudencia|corte|cámara|tribunal)\b",
            text,
            flags=re.IGNORECASE,
        ):
            omissions.append("No se detectaron referencias jurisprudenciales.")

        weaknesses = []
        if len(text) < 1200:
            weaknesses.append(
                "El desarrollo es breve; revisar si todas las premisas "
                "y consecuencias jurídicas quedaron fundadas."
            )
        if re.search(
            r"\b(podría|aparentemente|quizás|tal vez|se estima)\b",
            text,
            flags=re.IGNORECASE,
        ):
            weaknesses.append(
                "Se detectaron expresiones dubitativas que podrían "
                "debilitar afirmaciones centrales."
            )

        evidence = sorted(
            set(
                re.findall(
                    r"\b(documental|testimonial|pericial|informativa|"
                    r"confesional|inspección ocular)\b",
                    text,
                    flags=re.IGNORECASE,
                )
            )
        )

        return {
            "summary": (
                f"Texto analizado: {len(text)} caracteres. "
                f"Se detectaron {len(detected)} secciones jurídicas."
            ),
            "sections": detected,
            "omissions": omissions,
            "weaknesses": weaknesses,
            "evidence": evidence,
            "questions": [
                "¿Cada hecho relevante tiene una prueba asociada?",
                "¿Las citas fueron verificadas en el documento original?",
                "¿Se respondió la principal defensa contraria?",
                "¿El petitorio coincide con el desarrollo previo?",
            ],
        }

from __future__ import annotations

from datetime import date, datetime


class LegalAuthorityRanker:
    """
    Reordenamiento jurídico determinista aplicado DESPUÉS del Knowledge Engine.

    No reemplaza similitud semántica ni Knowledge:
    agrega una capa de autoridad relativa usando metadatos ya existentes.
    """

    AUTHORITY_RULES = (
        (("corte suprema", "csjn"), 0.32, "CSJN"),
        (("corte interamericana", "corte idh", "cidh"), 0.30, "Corte IDH"),
        (("cámara nacional de casación", "cámara federal de casación",
          "casación penal", "cfcp"), 0.24, "Casación"),
        (("cámara nacional", "cámara federal", "camara federal"), 0.19, "Cámara"),
        (("tribunal fiscal",), 0.15, "Tribunal Fiscal"),
        (("superior tribunal", "suprema corte provincial",
          "corte de justicia"), 0.17, "Superior Tribunal"),
        (("juzgado federal", "juzgado nacional", "juzgado"), 0.08, "Primera instancia"),
    )

    CATEGORY_BONUS = {
        "jurisprudencia": 0.10,
        "leyes": 0.09,
        "legislación": 0.09,
        "legislacion": 0.09,
        "doctrina": 0.04,
        "escritos": 0.00,
        "sin categoría": 0.00,
        "sin categoria": 0.00,
    }

    def rerank(self, ranked, plan=None):
        output = []

        preferred = {
            str(value).casefold()
            for value in getattr(plan, "preferred_authorities", []) or []
            if value
        }
        jurisdictions = {
            str(value).casefold()
            for value in getattr(plan, "jurisdictions", []) or []
            if value
        }

        for original_position, item in enumerate(ranked or [], start=1):
            base_score = float(item[0])
            result = item[1]
            metadata = getattr(result, "metadata", {}) or {}
            category = str(getattr(result, "category", "") or "")
            court = str(
                metadata.get("court")
                or metadata.get("tribunal")
                or metadata.get("authority")
                or ""
            )
            jurisdiction = str(
                metadata.get("jurisdiction")
                or metadata.get("jurisdiccion")
                or ""
            )

            bonus = 0.0
            reasons = []

            authority_bonus, authority_label = self._authority_bonus(court)
            if authority_bonus:
                bonus += authority_bonus
                reasons.append(f"autoridad:{authority_label}")

            category_bonus = self.CATEGORY_BONUS.get(
                category.casefold().strip(),
                0.0,
            )
            if category_bonus:
                bonus += category_bonus
                reasons.append(f"categoría:{category}")

            if preferred and self._matches_any(court, preferred):
                bonus += 0.12
                reasons.append("autoridad_preferida")

            if jurisdictions and self._matches_any(jurisdiction, jurisdictions):
                bonus += 0.07
                reasons.append("jurisdicción_coincidente")

            recency_bonus = self._recency_bonus(metadata.get("date"))
            if recency_bonus:
                bonus += recency_bonus
                reasons.append("recencia")

            # Preserve la ventaja del ranking anterior y usa bonus moderados.
            legal_score = base_score + bonus

            output.append(
                (
                    legal_score,
                    result,
                    item[2] if len(item) > 2 else [],
                    item[3] if len(item) > 3 else "",
                    {
                        "base_score": base_score,
                        "legal_bonus": bonus,
                        "legal_reasons": reasons,
                        "original_position": original_position,
                    },
                )
            )

        output.sort(
            key=lambda item: (
                -float(item[0]),
                item[4]["original_position"],
            )
        )
        return output

    def _authority_bonus(self, court):
        clean = str(court or "").casefold()
        for needles, bonus, label in self.AUTHORITY_RULES:
            if any(needle in clean for needle in needles):
                return bonus, label
        return 0.0, ""

    @staticmethod
    def _matches_any(value, expected):
        clean = str(value or "").casefold()
        return any(
            candidate in clean or clean in candidate
            for candidate in expected
            if candidate
        )

    @staticmethod
    def _recency_bonus(raw_date):
        if not raw_date:
            return 0.0

        parsed = None
        text = str(raw_date).strip()

        for parser in (
            lambda: datetime.fromisoformat(text).date(),
            lambda: datetime.strptime(text[:10], "%Y-%m-%d").date(),
            lambda: datetime.strptime(text[:10], "%d/%m/%Y").date(),
        ):
            try:
                parsed = parser()
                break
            except Exception:
                pass

        if not parsed:
            return 0.0

        years = max(0.0, (date.today() - parsed).days / 365.25)

        if years <= 2:
            return 0.06
        if years <= 5:
            return 0.04
        if years <= 10:
            return 0.02
        return 0.0

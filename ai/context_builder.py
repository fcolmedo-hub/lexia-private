from dataclasses import dataclass

from config.settings import SETTINGS
from models.search_result import SearchResult


@dataclass(slots=True)
class SourcePacket:
    number: int
    label: str
    content: str
    result: SearchResult


class LegalContextBuilder:
    def build(
        self,
        results: list[SearchResult],
    ) -> list[SourcePacket]:
        packets: list[SourcePacket] = []
        total_chars = 0

        for result in results[: SETTINGS.ai_max_sources]:
            metadata = result.metadata or {}

            label = (
                f"{result.document_name} | {result.category} | "
                f"{result.page_label} | "
                f"Tribunal: {metadata.get('court', 'No detectado')} | "
                f"Fecha: {metadata.get('date', 'No detectada')}"
            )

            remaining = (
                SETTINGS.ai_max_context_chars
                - total_chars
                - len(label)
                - 40
            )

            if remaining <= 180:
                break

            text_limit = min(
                SETTINGS.ai_max_chars_per_source,
                remaining,
            )
            text = self._compact(
                result.text.strip(),
                text_limit,
            )

            if not text:
                continue

            packets.append(
                SourcePacket(
                    number=len(packets) + 1,
                    label=label,
                    content=text,
                    result=result,
                )
            )
            total_chars += len(label) + len(text) + 40

        return packets

    def render(
        self,
        packets: list[SourcePacket],
    ) -> str:
        return "\n\n".join(
            f"[FUENTE {packet.number}]\n"
            f"{packet.label}\n"
            f"{packet.content}"
            for packet in packets
        )

    def _compact(
        self,
        text: str,
        limit: int,
    ) -> str:
        normalized = " ".join(text.split())

        if len(normalized) <= limit:
            return normalized

        cut = normalized[:limit]
        last_sentence = max(
            cut.rfind(". "),
            cut.rfind("; "),
            cut.rfind(": "),
        )

        if last_sentence >= int(limit * 0.55):
            cut = cut[: last_sentence + 1]

        return cut.rstrip() + " […]"

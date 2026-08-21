from models.search_result import SearchResult


class CitationBuilder:
    def build(self, result: SearchResult) -> str:
        return (
            f"{result.document_name}, {result.page_label}, "
            f"fragmento {result.fragment_index}. "
            f"Fuente local: {result.document_path}"
        )

    def build_source_note(
        self,
        result: SearchResult,
        quote_length: int = 500,
    ) -> str:
        return (
            f"Fuente: {self.build(result)}\n\n"
            f"Extracto recuperado:\n{result.text[:quote_length].strip()}"
        )

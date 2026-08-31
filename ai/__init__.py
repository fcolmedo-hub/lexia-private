"""Inicialización acotada de componentes AI de LexIA."""

from ai.context_package_builder import ContextPackageBuilder as _ContextPackageBuilder


_original_context_builder_init = _ContextPackageBuilder.__init__


def _lexia_context_builder_init(self, interpreted_search, query_interpreter):
    _original_context_builder_init(self, interpreted_search, query_interpreter)

    # El builder recibe la cadena de búsqueda ya construida por LexIA. Desde
    # ella reutilizamos exactamente el catálogo y VectorStore activos, sin
    # abrir un segundo Qdrant ni duplicar modelos de embeddings.
    try:
        cached_search = interpreted_search.search_engine
        fast_search = cached_search.engine
        hotfix_search = fast_search.delegate
        professional_search = hotfix_search.wrapped

        from ai.thematic_document_study import install_thematic_document_study

        install_thematic_document_study(
            self,
            professional_search.catalog,
            professional_search.vector_store,
        )
    except (AttributeError, ImportError):
        # Mantiene compatibilidad con tests o builders mínimos que no montan
        # toda la cadena de búsqueda de la aplicación.
        pass


_ContextPackageBuilder.__init__ = _lexia_context_builder_init

import threading
from services.platform_info_service import PlatformInfoService
from config.settings import SETTINGS
from ai.legal_ai_engine import LegalAIEngine
from ai.prompt_bridge import PromptBridge
from ai.context_package_builder import ContextPackageBuilder
from ai.intelligence_core import LexIAIntelligenceCore
from ai.lm_studio_client import LMStudioClient
from legal.argument_builder import ArgumentBuilder
from legal.case_strategy import CaseStrategyEngine
from legal.drafting_engine import DraftingEngine
from legal.precedent_extractor import PrecedentExtractor
from legal.copilot import LocalLegalCopilot
from legal.query_interpreter import LegalQueryInterpreter
from legal.search_planner import LegalSearchPlanner
from legal.citation_builder import CitationBuilder
from legal.document_comparator import DocumentComparator
from legal.opposing_counsel import OpposingCounselEngine
from legal.text_analyzer import LegalWritingAnalyzer
from search.cached_search import CachedSearchEngine
from search.embedding_service import EmbeddingService
from search.indexer import VectorIndexer
from search.interpreted_search import InterpretedLegalSearchEngine
from search.professional_search import (
    ProfessionalLegalSearchEngine,
)
from search.result_highlighter import ResultHighlighter
from search.search_hotfix import SearchHotfixEngine
from search.fast_search import FastSearchCatalogProxy, FastSearchEngine
from search.vector_store import VectorStore
from services.autosync_service import AutoSyncService
from services.ocr_queue_service import OCRQueueService
from services.activity_center_service import ActivityCenterService
from services.maintenance_history_service import (
    MaintenanceHistoryService,
)
from services.performance_profiler import PerformanceProfiler
from services.context_build_service import ContextBuildService
from services.prompt_launcher_service import PromptLauncherService
from services.backup_service import BackupService
from services.provider_registry import ProviderRegistry
from services.docx_exporter import DocxExporter
from services.health_service import HealthService
from services.document_inspector import DocumentInspector
from services.secure_document_deletion import SecureDocumentDeletionService
from services.knowledge_engine import KnowledgeEngine
from ai.knowledge_context_builder import KnowledgeContextPackageBuilder
from services.migration_service import MigrationService
from storage.case_repository import CaseRepository
from storage.drafting_repository import DraftingRepository
from storage.precedent_repository import PrecedentRepository
from storage.strategy_repository import StrategyRepository
from storage.catalog import DocumentCatalog
from storage.ingestion_job_repository import (
    IngestionJobRepository,
)
from storage.legal_matrix_repository import LegalMatrixRepository
from storage.query_interpretation_repository import QueryInterpretationRepository
from storage.search_cache_repository import SearchCacheRepository
from storage.search_evaluation_repository import (
    SearchEvaluationRepository,
)
from storage.search_feedback_repository import (
    SearchFeedbackRepository,
)
from storage.search_history_repository import (
    SearchHistoryRepository,
)
from storage.context_query_history_repository import (
    ContextQueryHistoryRepository,
)


_LEXIA_AUTOSYNC_INIT_LOCK = threading.RLock()

class LexIAApplication:
    def __init__(self):
        MigrationService().migrate()

        self.catalog = DocumentCatalog(SETTINGS.catalog_path)
        self.catalog.repair_ocr_pending_categories(
            SETTINGS.library_path
        )
        self.cases = CaseRepository(SETTINGS.cases_path)
        self.jobs = IngestionJobRepository(SETTINGS.jobs_path)
        self.matrix = LegalMatrixRepository(SETTINGS.matrix_path)
        self.feedback = SearchFeedbackRepository(
            SETTINGS.feedback_path
        )
        self.history = SearchHistoryRepository(
            SETTINGS.runtime_path / "search_history.sqlite3"
        )
        self.context_query_history = ContextQueryHistoryRepository(
            SETTINGS.runtime_path / "context_query_history.sqlite3"
        )
        self.cache = SearchCacheRepository(
            SETTINGS.search_cache_path
        )
        self.evaluations = SearchEvaluationRepository()
        self.precedents = PrecedentRepository(SETTINGS.precedent_path)
        self.strategies = StrategyRepository(SETTINGS.strategy_path)
        self.drafts = DraftingRepository(SETTINGS.drafting_path)
        self.interpretations = QueryInterpretationRepository(
            SETTINGS.query_interpretations_path
        )

        self.analyzer = LegalWritingAnalyzer()
        self.argument_builder = ArgumentBuilder()
        self.copilot = LocalLegalCopilot()
        self.providers = ProviderRegistry()
        self.document_comparator = DocumentComparator()
        self.precedent_extractor = PrecedentExtractor()
        self.strategy_engine = CaseStrategyEngine()
        self.drafting_engine = DraftingEngine()
        self.query_interpreter = LegalQueryInterpreter()
        self.search_planner = LegalSearchPlanner()
        self.opposing_counsel = OpposingCounselEngine()
        self.citation_builder = CitationBuilder()
        self.docx_exporter = DocxExporter()
        self.highlighter = ResultHighlighter()
        self.backups = BackupService()
        self.health = HealthService()

        self._embeddings = None
        self._vector_store = None
        self._raw_search = None
        self._search = None
        self._indexer = None
        self._interpreted_search = None
        self._autosync = None
        self._ocr_queue = None
        self._activity_center = None
        self._maintenance_history = None
        self._performance_profiler = None
        self._prompt_launcher = None
        self._platform_info = None
        self._document_inspector = None
        self._ai_engine = None
        self._intelligence_core = None
        self._prompt_bridge = None
        self._context_package_builder = None
        self._knowledge_engine = None
        self._context_build_jobs = None
        self._secure_document_deletion = None

    @property
    def embeddings(self):
        if self._embeddings is None:
            self._embeddings = EmbeddingService()
        return self._embeddings

    @property
    def vector_store(self):
        if self._vector_store is None:
            self._vector_store = VectorStore(self.embeddings)
        return self._vector_store

    @property
    def raw_search(self):
        if self._raw_search is None:
            # >>> LEXIA FAST SEARCH 1.0
            fast_catalog = FastSearchCatalogProxy(
                self.catalog,
                SETTINGS.catalog_path.parent.parent,
            )
            legacy_search = SearchHotfixEngine(
                ProfessionalLegalSearchEngine(
                    self.vector_store,
                    fast_catalog,
                    self.feedback,
                    self.history,
                ),
                fast_catalog,
            )
            self._raw_search = FastSearchEngine(
                legacy_search,
                fast_catalog,
            )
            # <<< LEXIA FAST SEARCH 1.0
        return self._raw_search

    @property
    def search(self):
        if self._search is None:
            self._search = CachedSearchEngine(
                self.raw_search,
                self.cache,
            )
        return self._search





    @property
    def platform_info(self):
        if self._platform_info is None:
            self._platform_info = PlatformInfoService()
        return self._platform_info

    @property
    def prompt_launcher(self):
        if self._prompt_launcher is None:
            self._prompt_launcher = PromptLauncherService()
        return self._prompt_launcher

    @property
    def performance_profiler(self):
        if self._performance_profiler is None:
            self._performance_profiler = (
                PerformanceProfiler()
            )
        return self._performance_profiler

    @property
    def knowledge_engine(self):
        if self._knowledge_engine is None:
            self._knowledge_engine = KnowledgeEngine()
        return self._knowledge_engine

    @property
    def context_builder(self):
        if self._context_package_builder is None:
            self._context_package_builder = KnowledgeContextPackageBuilder(
                self.interpreted_search,
                self.query_interpreter,
                self.knowledge_engine,
                self.performance_profiler,
            )
        return self._context_package_builder

    @property
    def context_build_jobs(self):
        if self._context_build_jobs is None:
            self._context_build_jobs = ContextBuildService(
                self.context_builder,
                self.context_query_history,
            )
        return self._context_build_jobs

    @property
    def prompt_bridge(self):
        if self._prompt_bridge is None:
            self._prompt_bridge = PromptBridge(
                self.interpreted_search,
                self.query_interpreter,
            )
        return self._prompt_bridge

    @property
    def lm_studio(self):
        return LMStudioClient()

    @property
    def intelligence_core(self):
        if self._intelligence_core is None:
            self._intelligence_core = LexIAIntelligenceCore(
                self.interpreted_search,
                self.query_interpreter,
            )
        return self._intelligence_core

    @property
    def ai_engine(self):
        if self._ai_engine is None:
            self._ai_engine = LegalAIEngine(
                self.interpreted_search,
                self.query_interpreter,
            )
        return self._ai_engine


    @property
    def document_inspector(self):
        if self._document_inspector is None:
            self._document_inspector = DocumentInspector(
                vector_store=self.vector_store,
            )
        return self._document_inspector



    @property
    def secure_document_deletion(self):
        if self._secure_document_deletion is None:
            self._secure_document_deletion = SecureDocumentDeletionService(
                catalog=self.catalog,
                vector_store=self.vector_store,
                autosync=self.autosync,
                ocr_queue=self.ocr_queue,
                knowledge_engine=self.knowledge_engine,
                search_cache=self.cache,
            )
        return self._secure_document_deletion


    @property
    def activity_center(self):
        if self._activity_center is None:
            self._activity_center = ActivityCenterService(
                self.autosync,
                self.ocr_queue,
            )
        return self._activity_center

    @property
    def maintenance_history(self):
        if self._maintenance_history is None:
            self._maintenance_history = MaintenanceHistoryService()
        return self._maintenance_history

    @property
    def ocr_queue(self):
        if self._ocr_queue is None:
            self._ocr_queue = OCRQueueService(
                lambda: self.indexer
            )
        return self._ocr_queue

    @property
    def autosync(self):
        # >>> LEXIA AUTOSYNC SINGLETON RACE FIX 1.0
        # Streamlit puede evaluar la app desde mas de un hilo.
        # La doble comprobacion evita crear dos AutoSyncService
        # sobre la misma LexIAApplication cacheada.
        if self._autosync is None:
            with _LEXIA_AUTOSYNC_INIT_LOCK:
                if self._autosync is None:
                    self._autosync = AutoSyncService(self.indexer)
        # <<< LEXIA AUTOSYNC SINGLETON RACE FIX 1.0
        return self._autosync

    @property
    def interpreted_search(self):
        if self._interpreted_search is None:
            self._interpreted_search = InterpretedLegalSearchEngine(
                self.search
            )
        return self._interpreted_search

    @property
    def indexer(self):
        if self._indexer is None:
            self._indexer = VectorIndexer(
                self.catalog,
                self.vector_store,
            )
        return self._indexer

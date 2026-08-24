from dataclasses import dataclass
import json
import os
import sys
from pathlib import Path


def _default_data_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "LexIA"
    return Path(r"D:\LexIA_2.3_DEV")


def _load_local_config() -> dict:
    """Load per-machine settings without ever storing them in Git."""
    configured = str(os.environ.get("LEXIA_CONFIG_FILE", "") or "").strip()
    if configured:
        path = Path(configured).expanduser()
    elif sys.platform == "darwin":
        path = _default_data_root() / "lexia.local.json"
    else:
        return {}

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


_LOCAL_CONFIG = _load_local_config()


def _setting(name: str, default):
    env_name = "LEXIA_" + name.upper()
    override = os.environ.get(env_name)
    if override is not None and str(override).strip():
        return override
    return _LOCAL_CONFIG.get(name, default)


def _path_setting(name: str, default: Path) -> Path:
    return Path(str(_setting(name, default))).expanduser()


_DATA_ROOT = _path_setting("data_root", _default_data_root())
_LIBRARY_DEFAULT = (
    Path.home() / "Documents" / "LexIA Biblioteca"
    if sys.platform == "darwin"
    else Path(r"D:\LexIA_2.3_DEV\data_test")
)
_LIBRARY_PATH = _path_setting("library_path", _LIBRARY_DEFAULT)
_RUNTIME_PATH = _path_setting("runtime_path", _DATA_ROOT / "runtime")
_LOGS_PATH = _path_setting("logs_path", _DATA_ROOT / "logs")
_EXPORTS_PATH = _path_setting("exports_path", _DATA_ROOT / "exports")
_BACKUPS_PATH = _path_setting("backups_path", _DATA_ROOT / "backups")
_REJECTED_PATH = _path_setting(
    "rejected_documents_path",
    _DATA_ROOT / "Rejected Documents",
)


@dataclass(frozen=True, slots=True)
class Settings:
    # Directorios
    library_path: Path = _LIBRARY_PATH
    runtime_path: Path = _RUNTIME_PATH
    logs_path: Path = _LOGS_PATH
    exports_path: Path = _EXPORTS_PATH
    backups_path: Path = _BACKUPS_PATH

    # Documentos rechazados
    rejected_documents_enabled: bool = True
    rejected_documents_path: Path = _REJECTED_PATH

    # Bases internas
    catalog_path: Path = _RUNTIME_PATH / "lexia_catalog.sqlite3"
    cases_path: Path = _RUNTIME_PATH / "cases.sqlite3"
    feedback_path: Path = _RUNTIME_PATH / "search_feedback.sqlite3"
    jobs_path: Path = _RUNTIME_PATH / "ingestion_jobs.sqlite3"
    app_state_path: Path = _RUNTIME_PATH / "app_state.json"
    search_cache_path: Path = _RUNTIME_PATH / "search_cache.sqlite3"
    matrix_path: Path = _RUNTIME_PATH / "legal_matrix.sqlite3"
    query_interpretations_path: Path = (
        _RUNTIME_PATH / "query_interpretations.sqlite3"
    )
    precedent_path: Path = _RUNTIME_PATH / "precedents.sqlite3"
    strategy_path: Path = _RUNTIME_PATH / "case_strategy.sqlite3"
    drafting_path: Path = _RUNTIME_PATH / "drafting_workspace.sqlite3"

    # AutoSync
    autosync_enabled: bool = True
    autosync_on_startup: bool = True
    autosync_debounce_seconds: int = 8
    autosync_scan_interval_seconds: int = 0
    autosync_startup_mode: str = "watch_only"
    autosync_state_path: Path = _RUNTIME_PATH / "autosync_state.json"
    synchronization_mode: str = "automatic"
    reconciliation_schedule_time: str = "03:00"
    reconciliation_config_path: Path = (
        _RUNTIME_PATH / "reconciliation_config.json"
    )

    # Qdrant
    qdrant_mode: str = str(
        _setting(
            "qdrant_mode",
            "local" if sys.platform == "darwin" else "server",
        )
    ).strip().lower()
    qdrant_url: str = str(
        _setting("qdrant_url", "http://127.0.0.1:6333")
    ).strip()
    qdrant_timeout_seconds: int = 120
    qdrant_upsert_batch_size: int = 256
    qdrant_upsert_retries: int = 3
    vector_document_batch_size: int = 8

    # Se conserva por compatibilidad con VectorStore,
    # aunque en modo server no se utiliza.
    vector_path: Path = _RUNTIME_PATH / "qdrant_local"
    collection_name: str = "lexia_fragments_platform_2_3_dev"

    # Fragmentación
    chunk_size: int = 1800
    chunk_overlap: int = 250

    # Embeddings
    embedding_batch_size: int = 32
    preferred_embedding_models: tuple[str, ...] = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "intfloat/multilingual-e5-small",
    )

    # Búsqueda
    knowledge_sync_before_search: bool = False
    context_builder_max_candidates: int = 42
    context_builder_runtime_max_sources: int = 14
    search_candidates_per_variant: int = 48
    search_min_candidates: int = 24
    search_max_query_variants: int = 3
    interpreted_per_query_limit: int = 24
    interpreted_max_queries: int = 5
    semantic_candidates: int = 70
    lexical_candidates: int = 70
    default_limit: int = 10
    max_results_per_document: int = 2
    search_history_limit: int = 200
    fuzzy_match_threshold: float = 0.86
    exact_phrase_bonus: float = 0.22
    metadata_bonus: float = 0.10
    feedback_max_bonus: float = 0.12
    search_cache_ttl_seconds: int = 3600
    search_cache_max_entries: int = 500

    # Metadatos e intérprete
    metadata_preview_chars: int = 12000
    interpreter_max_subtopics: int = 8
    interpreter_max_queries: int = 10

    # LM Studio / AI Engine
    lm_studio_base_url: str = "http://127.0.0.1:1234/v1"
    lm_studio_model: str = "mistral-7b-instruct-v0.3"
    lm_studio_timeout_seconds: int = 180

    # Mistral está cargado con una ventana de 4096 tokens.
    ai_context_window_tokens: int = 4096
    ai_reserved_output_tokens: int = 700
    ai_prompt_safety_tokens: int = 350
    ai_chars_per_token_estimate: float = 3.4

    ai_temperature: float = 0.15
    ai_max_tokens: int = 700
    ai_max_sources: int = 6
    ai_max_chars_per_source: int = 900
    ai_max_context_chars: int = 7200
    ai_require_citations: bool = True

    # Prompt Bridge / ChatGPT Plus
    prompt_bridge_max_sources: int = 14
    prompt_bridge_max_chars_per_source: int = 2400
    prompt_bridge_max_total_chars: int = 42000
    prompt_bridge_upload_max_chars: int = 80000
    prompt_exports_path: Path = _EXPORTS_PATH / "prompts"

    # Context Builder / ChatGPT Plus
    context_builder_max_sources: int = 30
    context_builder_max_chars_per_source: int = 2600
    context_builder_max_total_chars: int = 52000
    context_builder_upload_max_chars: int = 95000
    context_builder_exports_path: Path = _EXPORTS_PATH / "context_packages"

    # Knowledge Engine determinista
    knowledge_path: Path = _RUNTIME_PATH / "knowledge.sqlite3"
    knowledge_candidate_multiplier: int = 3
    knowledge_max_search_queries: int = 5
    knowledge_sync_on_context_build: bool = True

    # Cola OCR manual
    ocr_queue_path: Path = _RUNTIME_PATH / "ocr_queue.sqlite3"
    ocr_auto_process: bool = False

    # OCR
    ocr_enabled: bool = True
    ocr_dpi: int = 170
    ocr_page_timeout_seconds: int = 120
    ocr_min_chars_per_page: int = 40
    ocr_max_pages_per_document: int = 800

    # Procesamiento
    checkpoint_every_documents: int = 5
    backup_retention: int = 10

    # Ranking
    category_weights: tuple[tuple[str, float], ...] = (
        ("Leyes", 1.30),
        ("Legislación", 1.30),
        ("Jurisprudencia", 1.22),
        ("Escritos", 1.12),
        ("Doctrina", 1.08),
        ("Sin categoría", 1.00),
    )

    # Análisis de jurisprudencia
    judgment_max_pages: int = 1200
    judgment_chunk_chars: int = 12000
    judgment_chunk_overlap: int = 1200

    # Checkpoint
    checkpoint_enabled: bool = True
    checkpoint_path: Path = _RUNTIME_PATH / "checkpoints"


SETTINGS = Settings()

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    # Directorios
    library_path: Path = Path(r"D:\LexIA_2.3_DEV\data_test")
    runtime_path: Path = Path(r"D:\LexIA_2.3_DEV\runtime")
    logs_path: Path = Path(r"D:\LexIA_2.3_DEV\logs")
    exports_path: Path = Path(r"D:\LexIA_2.3_DEV\exports")
    backups_path: Path = Path(r"D:\LexIA_2.3_DEV\backups")

    # Documentos rechazados
    rejected_documents_enabled: bool = True
    rejected_documents_path: Path = Path(
        r"D:\LexIA_2.3_DEV\Rejected Documents"
    )

    # Bases internas
    catalog_path: Path = Path("runtime/lexia_catalog.sqlite3")
    cases_path: Path = Path("runtime/cases.sqlite3")
    feedback_path: Path = Path("runtime/search_feedback.sqlite3")
    jobs_path: Path = Path("runtime/ingestion_jobs.sqlite3")
    app_state_path: Path = Path("runtime/app_state.json")
    search_cache_path: Path = Path("runtime/search_cache.sqlite3")
    matrix_path: Path = Path("runtime/legal_matrix.sqlite3")
    query_interpretations_path: Path = Path(
        "runtime/query_interpretations.sqlite3"
    )
    precedent_path: Path = Path("runtime/precedents.sqlite3")
    strategy_path: Path = Path("runtime/case_strategy.sqlite3")
    drafting_path: Path = Path("runtime/drafting_workspace.sqlite3")

    # AutoSync
    autosync_enabled: bool = True
    autosync_on_startup: bool = True
    autosync_debounce_seconds: int = 8
    autosync_scan_interval_seconds: int = 0
    autosync_startup_mode: str = "watch_only"
    autosync_state_path: Path = Path("runtime/autosync_state.json")
    synchronization_mode: str = "automatic"
    reconciliation_schedule_time: str = "03:00"
    reconciliation_config_path: Path = Path(
        "runtime/reconciliation_config.json"
    )

    # Qdrant
    qdrant_mode: str = "server"
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_timeout_seconds: int = 120
    qdrant_upsert_batch_size: int = 256
    qdrant_upsert_retries: int = 3
    vector_document_batch_size: int = 8

    # Se conserva por compatibilidad con VectorStore,
    # aunque en modo server no se utiliza.
    vector_path: Path = Path(
        r"D:\LexIA_2.3_DEV\runtime\qdrant_local_unused"
    )
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
    prompt_exports_path: Path = Path("exports/prompts")

    # Context Builder / ChatGPT Plus
    context_builder_max_sources: int = 30
    context_builder_max_chars_per_source: int = 2600
    context_builder_max_total_chars: int = 52000
    context_builder_upload_max_chars: int = 95000
    context_builder_exports_path: Path = Path("exports/context_packages")

    # Knowledge Engine determinista
    knowledge_path: Path = Path("runtime/knowledge.sqlite3")
    knowledge_candidate_multiplier: int = 3
    knowledge_max_search_queries: int = 5
    knowledge_sync_on_context_build: bool = True

    # Cola OCR manual
    ocr_queue_path: Path = Path("runtime/ocr_queue.sqlite3")
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
    checkpoint_path: Path = Path(
        "runtime/checkpoints"
    )


SETTINGS = Settings()

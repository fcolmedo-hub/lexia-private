PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documents (
    document_id INTEGER PRIMARY KEY,
    source_key TEXT NOT NULL UNIQUE,
    document_name TEXT NOT NULL,
    document_path TEXT,
    pilot_id INTEGER,
    court TEXT,
    judgment_date TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_pilot_id ON documents(pilot_id);
CREATE INDEX IF NOT EXISTS idx_documents_court ON documents(court);
CREATE INDEX IF NOT EXISTS idx_documents_judgment_date ON documents(judgment_date);

CREATE TABLE IF NOT EXISTS extraction_runs (
    run_id TEXT PRIMARY KEY,
    extractor_version TEXT NOT NULL,
    model TEXT,
    reasoning_effort TEXT,
    source_dir TEXT,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS standards (
    standard_uid TEXT PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    run_id TEXT REFERENCES extraction_runs(run_id) ON DELETE SET NULL,
    local_identifier TEXT,
    statement TEXT NOT NULL,
    speaker TEXT NOT NULL,
    source_speaker TEXT NOT NULL,
    treatment TEXT NOT NULL,
    conditions_json TEXT NOT NULL DEFAULT '[]',
    consequence TEXT,
    exceptions_json TEXT NOT NULL DEFAULT '[]',
    source_fingerprint TEXT NOT NULL,
    review_status TEXT NOT NULL CHECK(review_status IN ('validated','needs_review','rejected')),
    publication_status TEXT NOT NULL CHECK(publication_status IN ('ready','blocked','published','hidden')),
    canonical_uid TEXT REFERENCES standards(standard_uid) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, source_fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_standards_document ON standards(document_id);
CREATE INDEX IF NOT EXISTS idx_standards_review ON standards(review_status);
CREATE INDEX IF NOT EXISTS idx_standards_publication ON standards(publication_status);
CREATE INDEX IF NOT EXISTS idx_standards_speaker ON standards(speaker);
CREATE INDEX IF NOT EXISTS idx_standards_treatment ON standards(treatment);
CREATE INDEX IF NOT EXISTS idx_standards_canonical ON standards(canonical_uid);

CREATE TABLE IF NOT EXISTS quotes (
    quote_id INTEGER PRIMARY KEY,
    standard_uid TEXT NOT NULL REFERENCES standards(standard_uid) ON DELETE CASCADE,
    evidence_index INTEGER NOT NULL,
    chunk_id TEXT,
    page_start INTEGER,
    page_end INTEGER,
    unit_ids_json TEXT NOT NULL DEFAULT '[]',
    quote_text TEXT NOT NULL,
    validation TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(standard_uid, evidence_index)
);

CREATE INDEX IF NOT EXISTS idx_quotes_standard ON quotes(standard_uid);
CREATE INDEX IF NOT EXISTS idx_quotes_pages ON quotes(page_start, page_end);

CREATE TABLE IF NOT EXISTS relations (
    relation_id INTEGER PRIMARY KEY,
    from_standard_uid TEXT NOT NULL REFERENCES standards(standard_uid) ON DELETE CASCADE,
    to_standard_uid TEXT NOT NULL REFERENCES standards(standard_uid) ON DELETE CASCADE,
    relation_type TEXT NOT NULL CHECK(relation_type IN ('duplicate_of','specializes','generalizes','exception_to','related_to','supports','contradicts')),
    status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed','confirmed','rejected')),
    rationale TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_standard_uid, to_standard_uid, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_relations_from ON relations(from_standard_uid);
CREATE INDEX IF NOT EXISTS idx_relations_to ON relations(to_standard_uid);
CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(relation_type);

CREATE TABLE IF NOT EXISTS tags (
    tag_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS standard_tags (
    standard_uid TEXT NOT NULL REFERENCES standards(standard_uid) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(tag_id) ON DELETE CASCADE,
    PRIMARY KEY (standard_uid, tag_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS standards_fts USING fts5(
    standard_uid UNINDEXED,
    statement,
    conditions,
    consequence,
    exceptions,
    tokenize='unicode61 remove_diacritics 2'
);

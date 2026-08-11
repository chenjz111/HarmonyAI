-- Sprint 4 SQLite bootstrap migration.
-- Existing databases should use apply_sprint4_migrations(engine), which
-- detects missing columns before ALTER TABLE and never drops Sprint 3 data.

CREATE TABLE IF NOT EXISTS ai_call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id VARCHAR(64) NOT NULL UNIQUE,
    session_id VARCHAR(64) NOT NULL,
    agent_id VARCHAR(32) NOT NULL,
    source_type VARCHAR(32),
    text_length INTEGER,
    provider VARCHAR(32) NOT NULL,
    model VARCHAR(64),
    prompt_version VARCHAR(64),
    call_type VARCHAR(32),
    status VARCHAR(16) DEFAULT 'success',
    input_summary TEXT,
    output_summary TEXT,
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_code VARCHAR(64),
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assessment_evidences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(64) NOT NULL,
    evidence_id VARCHAR(64) UNIQUE NOT NULL,
    source VARCHAR(32) NOT NULL,
    category VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    label VARCHAR(64),
    display_name VARCHAR(128),
    value JSON,
    polarity VARCHAR(16),
    severity VARCHAR(16),
    severity_display VARCHAR(64),
    time_window VARCHAR(64),
    source_type VARCHAR(32),
    source_ref VARCHAR(128),
    quote TEXT,
    extraction_confidence FLOAT,
    confirmed BOOLEAN NOT NULL DEFAULT 0,
    dimension_score INTEGER,
    used_in_diagnosis INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assessment_followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(64) NOT NULL,
    assessment_id VARCHAR(64),
    followup_id VARCHAR(64) UNIQUE NOT NULL,
    question_id VARCHAR(64),
    question TEXT NOT NULL,
    category VARCHAR(32) NOT NULL,
    priority INTEGER DEFAULT 1,
    status VARCHAR(16) DEFAULT 'pending',
    answer TEXT,
    answer_value JSON,
    source_type VARCHAR(32),
    revision_submitted INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assessment_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(64) NOT NULL,
    revision_id VARCHAR(64) UNIQUE NOT NULL,
    assessment_id VARCHAR(64),
    field_changed VARCHAR(64) NOT NULL,
    revision INTEGER,
    previous_revision INTEGER,
    change_summary TEXT,
    changes JSON,
    assessment_snapshot JSON,
    confirmation_level VARCHAR(32),
    old_value TEXT,
    new_value TEXT NOT NULL,
    source VARCHAR(32) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (assessment_id, revision)
);

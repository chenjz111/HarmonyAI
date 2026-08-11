-- Sprint 4 Incremental Migration
-- Run against harmonyai database. Does NOT drop existing tables.
USE harmonyai;

CREATE TABLE IF NOT EXISTS ai_call_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    request_id VARCHAR(64) NOT NULL UNIQUE,
    session_id VARCHAR(64) NOT NULL,
    agent_id VARCHAR(32) NOT NULL,
    source_type VARCHAR(32) NULL,
    text_length INT NULL,
    provider VARCHAR(32) NOT NULL,
    model VARCHAR(64) NULL,
    prompt_version VARCHAR(64) NULL,
    call_type VARCHAR(32) NULL,
    status VARCHAR(16) DEFAULT 'success',
    input_summary TEXT NULL,
    output_summary TEXT NULL,
    latency_ms INT NULL,
    input_tokens INT NULL,
    output_tokens INT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    error_code VARCHAR(64) NULL,
    error TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_acl_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS assessment_evidences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    evidence_id VARCHAR(64) UNIQUE NOT NULL,
    source VARCHAR(32) NOT NULL,
    category VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    label VARCHAR(64) NULL,
    display_name VARCHAR(128) NULL,
    value JSON NULL,
    polarity VARCHAR(16) NULL,
    severity VARCHAR(16) NULL,
    severity_display VARCHAR(64) NULL,
    time_window VARCHAR(64) NULL,
    source_type VARCHAR(32) NULL,
    source_ref VARCHAR(128) NULL,
    quote TEXT NULL,
    extraction_confidence FLOAT NULL,
    confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    dimension_score INT NULL,
    used_in_diagnosis INT DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ae_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Existing Sprint 3 document rows are retained. For repeatable column
-- detection/addition on MySQL 8 and SQLite, run:
-- backend.app.core.sprint4_migrations.apply_sprint4_migrations(engine)

CREATE TABLE IF NOT EXISTS assessment_followups (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    assessment_id VARCHAR(64) NULL,
    followup_id VARCHAR(64) UNIQUE NOT NULL,
    question_id VARCHAR(64) NULL,
    question TEXT NOT NULL,
    category VARCHAR(32) NOT NULL,
    priority INT DEFAULT 1,
    status VARCHAR(16) DEFAULT 'pending',
    answer TEXT NULL,
    answer_value JSON NULL,
    source_type VARCHAR(32) NULL,
    revision_submitted INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_af_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS assessment_revisions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    revision_id VARCHAR(64) UNIQUE NOT NULL,
    assessment_id VARCHAR(64) NULL,
    field_changed VARCHAR(64) NOT NULL,
    revision INT NULL,
    previous_revision INT NULL,
    change_summary TEXT NULL,
    changes JSON NULL,
    assessment_snapshot JSON NULL,
    confirmation_level VARCHAR(32) NULL,
    old_value TEXT NULL,
    new_value TEXT NOT NULL,
    source VARCHAR(32) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_assessment_revision (assessment_id, revision),
    INDEX idx_ar_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Rollback:
-- DROP TABLE IF EXISTS assessment_revisions, assessment_followups, assessment_evidences, ai_call_logs;

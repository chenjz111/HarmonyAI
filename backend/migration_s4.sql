-- Sprint 4 Incremental Migration
-- Run against harmonyai database. Does NOT drop existing tables.
USE harmonyai;

CREATE TABLE IF NOT EXISTS ai_call_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    provider VARCHAR(32) NOT NULL,
    call_type VARCHAR(32) NOT NULL,
    status VARCHAR(16) DEFAULT 'success',
    input_summary TEXT NULL,
    output_summary TEXT NULL,
    latency_ms INT NULL,
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
    used_in_diagnosis INT DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ae_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS assessment_followups (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    followup_id VARCHAR(64) UNIQUE NOT NULL,
    question TEXT NOT NULL,
    category VARCHAR(32) NOT NULL,
    priority INT DEFAULT 1,
    status VARCHAR(16) DEFAULT 'pending',
    answer TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_af_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS assessment_revisions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    revision_id VARCHAR(64) UNIQUE NOT NULL,
    field_changed VARCHAR(64) NOT NULL,
    old_value TEXT NULL,
    new_value TEXT NOT NULL,
    source VARCHAR(32) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ar_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Rollback:
-- DROP TABLE IF EXISTS assessment_revisions, assessment_followups, assessment_evidences, ai_call_logs;

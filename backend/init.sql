-- ============================================================================
-- HarmonyAI Database Schema — Sprint 3
-- MySQL 8.0
--
-- 7 tables with FOREIGN KEY constraints:
--   users / sessions / emotion_assessments / syndrome_diagnoses / prescriptions / feedbacks
-- ============================================================================

CREATE DATABASE IF NOT EXISTS harmonyai
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE harmonyai;

-- Drop old tables (order matters due to FK)
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS feedbacks;
DROP TABLE IF EXISTS generations;
DROP TABLE IF EXISTS prescriptions;
DROP TABLE IF EXISTS syndrome_diagnoses;
DROP TABLE IF EXISTS emotion_assessments;
DROP TABLE IF EXISTS syndromes;
DROP TABLE IF EXISTS assessments;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS users;

-- ---------------------------------------------------------------------------
-- 1. users
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    openid          VARCHAR(128)    NOT NULL UNIQUE COMMENT '微信OpenID',
    nickname        VARCHAR(64)     NULL,
    avatar_url      TEXT            NULL,
    phone           VARCHAR(20)     NULL,
    preferred_instruments  TEXT     NULL COMMENT '偏好乐器 JSON',
    preferred_bpm_min      INT      NULL,
    preferred_bpm_max      INT      NULL,
    preferred_session      VARCHAR(32) NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_openid (openid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- 2. sessions  (FK → users.id)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    user_id         INT             NOT NULL,
    session_id      VARCHAR(64)     NOT NULL UNIQUE COMMENT 'sess_YYYYMMDD_NNN',
    status          VARCHAR(16)     DEFAULT 'active' COMMENT 'active/completed/abandoned',
    current_agent   VARCHAR(32)     NULL COMMENT '当前所在Agent',
    metadata_json   TEXT            NULL COMMENT '会话元数据 JSON',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_sessions_user (user_id),
    UNIQUE INDEX idx_sessions_id (session_id),
    CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- 3. emotion_assessments — Agent 1 output  (FK → users.id + sessions.session_id)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS emotion_assessments (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    user_id         INT             NOT NULL,
    session_id      VARCHAR(64)     NOT NULL,
    agent_id        VARCHAR(64)     DEFAULT 'evaluation_agent',
    agent_version   VARCHAR(16)     DEFAULT '1.0.0',
    input_channel   VARCHAR(32)     NOT NULL COMMENT 'questionnaire',

    raw_input       TEXT            NULL,

    -- emotion_scores
    emotion_anxiety     FLOAT       NULL COMMENT '焦虑 0-100',
    emotion_depression  FLOAT       NULL COMMENT '抑郁 0-100',
    emotion_anger       FLOAT       NULL COMMENT '愤怒 0-100',
    emotion_fear        FLOAT       NULL COMMENT '恐惧 0-100',
    emotion_overthinking FLOAT      NULL COMMENT '思虑 0-100',

    -- body_indicators
    body_sleep_quality  FLOAT       NULL,
    body_appetite       FLOAT       NULL,
    body_energy         FLOAT       NULL,
    body_palpitation    FLOAT       NULL,
    body_digestion      FLOAT       NULL,

    -- questionnaire_scores
    questionnaire_total     FLOAT   NULL,
    questionnaire_emotion   FLOAT   NULL,
    questionnaire_sleep     FLOAT   NULL,
    questionnaire_body      FLOAT   NULL,

    term_mapping    TEXT            NULL COMMENT '术语映射 JSON',
    confidence      FLOAT           NOT NULL,
    reason          TEXT            NULL,
    processing_time_ms INT          NULL,
    timestamp       DATETIME        DEFAULT CURRENT_TIMESTAMP,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_ea_user (user_id),
    INDEX idx_ea_session (session_id),
    CONSTRAINT fk_ea_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_ea_session FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- 4. syndrome_diagnoses — Agent 2 output  (FK → users.id + sessions.session_id)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS syndrome_diagnoses (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    user_id         INT             NOT NULL,
    session_id      VARCHAR(64)     NOT NULL,
    agent_id        VARCHAR(64)     DEFAULT 'diagnosis_agent',
    agent_version   VARCHAR(16)     DEFAULT '1.0.0',

    primary_name            VARCHAR(64)  NOT NULL,
    primary_element         VARCHAR(8)   NULL,
    primary_organ           VARCHAR(8)   NULL,
    primary_emotion         VARCHAR(8)   NULL,
    primary_severity_level  INT          NULL,
    primary_severity_name   VARCHAR(16)  NULL,

    secondary_syndromes     TEXT         NULL,

    confidence_overall      FLOAT        NOT NULL,
    confidence_rule_engine  FLOAT        NULL,
    confidence_llm          FLOAT        NULL,
    confidence_literature   FLOAT        NULL,

    evidence            TEXT    NULL,
    search_keywords     TEXT    NULL,

    warn_low_confidence         BOOLEAN DEFAULT FALSE,
    warn_conflicting            BOOLEAN DEFAULT FALSE,
    warn_recommend_professional BOOLEAN DEFAULT FALSE,

    confidence      FLOAT           NOT NULL,
    reason          TEXT            NULL,
    processing_time_ms INT          NULL,
    timestamp       DATETIME        DEFAULT CURRENT_TIMESTAMP,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_sd_user (user_id),
    INDEX idx_sd_session (session_id),
    CONSTRAINT fk_sd_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_sd_session FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- 5. prescriptions — Agent 3 + 4 merged  (FK → users.id + sessions.session_id)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prescriptions (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    user_id         INT             NOT NULL,
    session_id      VARCHAR(64)     NOT NULL,
    agent_id        VARCHAR(64)     DEFAULT 'prescription_agent',
    agent_version   VARCHAR(16)     DEFAULT '1.0.0',
    prescription_id VARCHAR(64)     NOT NULL UNIQUE COMMENT 'rx_YYYYMMDD_NNN',

    daily_plan              TEXT    NOT NULL COMMENT '每日处方 JSON',
    prompt_template_id      VARCHAR(32) NULL,
    prompt_template_version VARCHAR(16) NULL,
    prompt_parameters       TEXT    NULL,

    explanation_summary     TEXT    NULL,
    explanation_user_facing TEXT    NULL,
    explanation_warnings    TEXT    NULL,

    -- Agent 4: Audio
    audio_url               TEXT    NULL,
    audio_duration_seconds  INT     NULL,
    audio_file_size_bytes   INT     NULL,
    audio_format            VARCHAR(8)  DEFAULT 'mp3',
    audio_bitrate_kbps      INT     NULL,
    actual_bpm              INT     NULL,
    actual_instruments      TEXT    NULL,
    actual_prompt_sent      TEXT    NULL,
    provider_name           VARCHAR(32) NULL,
    provider_cost_cny       FLOAT   NULL,

    confidence      FLOAT           NOT NULL,
    reason          TEXT            NULL,
    processing_time_ms INT          NULL,
    timestamp       DATETIME        DEFAULT CURRENT_TIMESTAMP,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_rx_user (user_id),
    INDEX idx_rx_session (session_id),
    UNIQUE INDEX idx_rx_id (prescription_id),
    CONSTRAINT fk_rx_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_rx_session FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- 6. feedbacks — Agent 5 output  (FK → users.id + sessions.session_id)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedbacks (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    user_id         INT             NOT NULL,
    session_id      VARCHAR(64)     NOT NULL,
    agent_id        VARCHAR(64)     DEFAULT 'feedback_agent',
    agent_version   VARCHAR(16)     DEFAULT '1.0.0',
    feedback_id     VARCHAR(64)     NOT NULL UNIQUE COMMENT 'fb_YYYYMMDD_NNN',

    subjective_satisfaction INT     NULL,
    subjective_emotion_match INT    NULL,
    subjective_relaxation   INT     NULL,
    subjective_sleep        INT     NULL,
    subjective_stress       INT     NULL,
    subjective_text         TEXT    NULL,

    behavioral_completion_rate   FLOAT      NULL,
    behavioral_replay_count      INT        NULL,
    behavioral_pause_count       INT        NULL,
    behavioral_skip_count        INT        NULL,
    behavioral_listen_session    VARCHAR(16) NULL,
    behavioral_avg_volume        FLOAT      NULL,

    wearable_data   TEXT    NULL,

    decision_action     VARCHAR(64)  NOT NULL,
    decision_detail     TEXT         NULL,
    decision_next_step  VARCHAR(64)  NULL,
    decision_adjustments TEXT        NULL,

    profile_update  TEXT    NULL,

    -- Feedback 2.0 fields (Sprint 3)
    schema_version      VARCHAR(8)  DEFAULT '2.0',
    prescription_id     VARCHAR(64) NULL,
    track_id            VARCHAR(64) NULL,
    mood_before         INT         NULL COMMENT '听前心情 1-5',
    mood_after          INT         NULL COMMENT '听后心情 1-5',
    relaxation_before   INT         NULL COMMENT '听前放松度 1-5',
    relaxation_after    INT         NULL COMMENT '听后放松度 1-5',
    music_match         INT         NULL COMMENT '音乐匹配度 1-5',
    will_continue       INT         NULL COMMENT '是否继续 0/1',
    is_favorite         INT         NULL COMMENT '是否收藏 0/1',
    disliked_features   TEXT        NULL COMMENT '不喜欢的音乐特征 JSON',
    global_rules_modified INT       DEFAULT 0 COMMENT '固定为0，反馈不修改全局规则',

    confidence      FLOAT           NOT NULL,
    reason          TEXT            NULL,
    processing_time_ms INT          NULL,
    timestamp       DATETIME        DEFAULT CURRENT_TIMESTAMP,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_fb_user (user_id),
    INDEX idx_fb_session (session_id),
    UNIQUE INDEX idx_fb_id (feedback_id),
    CONSTRAINT fk_fb_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_fb_session FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- 7. documents (Sprint 3 Issue #36 — 病例材料)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    user_id         INT             NOT NULL,
    session_id      VARCHAR(64)     NOT NULL,

    document_id         VARCHAR(64) NOT NULL UNIQUE COMMENT 'doc_YYYYMMDD_HHMMSS',
    original_filename   VARCHAR(256) NOT NULL,
    file_type           VARCHAR(16) NOT NULL COMMENT 'jpg/png/pdf',
    file_size_bytes     INT         NOT NULL,
    page_count          INT         DEFAULT 1,

    storage_path        VARCHAR(512) NOT NULL COMMENT '相对/云端路径',

    status          VARCHAR(16) DEFAULT 'uploaded' COMMENT 'uploaded/confirmed/skipped/deleted/ocr_failed',
    ocr_text        TEXT        NULL COMMENT 'OCR识别文本',
    ocr_confidence  VARCHAR(16) NULL COMMENT 'high/medium/low',
    ocr_confirmed   BOOLEAN     DEFAULT FALSE,

    created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_doc_user (user_id),
    INDEX idx_doc_session (session_id),
    UNIQUE INDEX idx_doc_id (document_id),
    CONSTRAINT fk_doc_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_doc_session FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- Test data
-- ============================================================================
INSERT INTO users (openid, nickname) VALUES ('test_openid_001', '测试用户');

-- ============================================================================
-- HarmonyAI Sprint 3 Incremental Migration
-- Run ONCE against existing harmonyai database.
-- Does NOT drop tables or data. Safe to rollback.
-- ============================================================================

USE harmonyai;

-- ---------------------------------------------------------------------------
-- 1. Feedback 2.0 columns (Add if not exists)
-- ---------------------------------------------------------------------------
ALTER TABLE feedbacks
  ADD COLUMN IF NOT EXISTS schema_version VARCHAR(8) DEFAULT '1.0',
  ADD COLUMN IF NOT EXISTS prescription_id VARCHAR(64) NULL,
  ADD COLUMN IF NOT EXISTS track_id VARCHAR(64) NULL,
  ADD COLUMN IF NOT EXISTS mood_before INT NULL COMMENT '听前心情 1-5 / 0-10',
  ADD COLUMN IF NOT EXISTS mood_after INT NULL COMMENT '听后心情 1-5 / 0-10',
  ADD COLUMN IF NOT EXISTS relaxation_before INT NULL,
  ADD COLUMN IF NOT EXISTS relaxation_after INT NULL,
  ADD COLUMN IF NOT EXISTS music_match INT NULL COMMENT '音乐匹配度',
  ADD COLUMN IF NOT EXISTS will_continue INT NULL COMMENT '是否继续 0/1',
  ADD COLUMN IF NOT EXISTS is_favorite INT NULL COMMENT '是否收藏 0/1',
  ADD COLUMN IF NOT EXISTS disliked_features TEXT NULL,
  ADD COLUMN IF NOT EXISTS global_rules_modified INT DEFAULT 0;

-- Widen decision_action for V2 values
ALTER TABLE feedbacks
  MODIFY COLUMN decision_action VARCHAR(64);

-- ---------------------------------------------------------------------------
-- 2. Documents table (Create if not exists)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    user_id         INT             NOT NULL,
    session_id      VARCHAR(64)     NOT NULL,
    document_id     VARCHAR(64)     NOT NULL UNIQUE COMMENT 'doc_YYYYMMDD_HHMMSS_uuid',
    original_filename VARCHAR(256)  NOT NULL,
    file_type       VARCHAR(16)     NOT NULL COMMENT 'jpg/png/pdf',
    file_size_bytes INT             NOT NULL,
    page_count      INT             DEFAULT 1,
    storage_path    VARCHAR(512)    NOT NULL COMMENT '相对路径',
    status          VARCHAR(16)     DEFAULT 'uploaded',
    ocr_text        TEXT            NULL,
    ocr_confidence  VARCHAR(16)     NULL,
    ocr_confirmed   BOOLEAN         DEFAULT FALSE,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_doc_user (user_id),
    INDEX idx_doc_session (session_id),
    UNIQUE INDEX idx_doc_id (document_id),
    CONSTRAINT fk_doc_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_doc_session FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- Rollback script (run only if migration must be reversed)
-- ============================================================================
-- ALTER TABLE feedbacks
--   MODIFY COLUMN decision_action VARCHAR(16),
--   DROP COLUMN IF EXISTS global_rules_modified,
--   DROP COLUMN IF EXISTS disliked_features,
--   DROP COLUMN IF EXISTS is_favorite,
--   DROP COLUMN IF EXISTS will_continue,
--   DROP COLUMN IF EXISTS music_match,
--   DROP COLUMN IF EXISTS relaxation_after,
--   DROP COLUMN IF EXISTS relaxation_before,
--   DROP COLUMN IF EXISTS mood_after,
--   DROP COLUMN IF EXISTS mood_before,
--   DROP COLUMN IF EXISTS track_id,
--   DROP COLUMN IF EXISTS prescription_id,
--   DROP COLUMN IF EXISTS schema_version;
-- DROP TABLE IF EXISTS documents;

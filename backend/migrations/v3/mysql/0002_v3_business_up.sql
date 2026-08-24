-- ============================================================
-- 0002_v3_business — V3 business persistence tables (MySQL 8)
-- Mirrors harmonyai-v3-persistence-contract.md sections 4-8.
-- All timestamps are UTC (DATETIME(6)); JSON columns are MySQL
-- JSON validated by the application-layer Pydantic schemas.
-- ============================================================

-- ------------------------------------------------------------
-- 4. Information Understanding Tables
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS understanding_runs (
    understanding_id VARCHAR(64) PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    current_revision INTEGER NOT NULL,
    status VARCHAR(24) NOT NULL,
    safety_status VARCHAR(32) NOT NULL,
    degradation_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_understanding_runs_user
        FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_understanding_runs_session
        FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    CONSTRAINT ck_understanding_runs_revision
        CHECK (current_revision >= 1),
    CONSTRAINT ck_understanding_runs_status
        CHECK (status IN ('queued', 'processing', 'needs_confirmation',
            'confirmed', 'degraded', 'failed')),
    CONSTRAINT uq_understanding_runs_user
        UNIQUE (understanding_id, internal_user_pk)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_understanding_runs_session
    ON understanding_runs(session_row_id);
CREATE INDEX ix_understanding_runs_user_status
    ON understanding_runs(internal_user_pk, status);

CREATE TABLE IF NOT EXISTS understanding_sources (
    source_id VARCHAR(64) PRIMARY KEY,
    understanding_id VARCHAR(64) NOT NULL,
    source_type VARCHAR(24) NOT NULL,
    processing_status VARCHAR(24) NOT NULL,
    document_id VARCHAR(64) NULL,
    audio_id VARCHAR(64) NULL,
    questionnaire_submission_id VARCHAR(64) NULL,
    text_ciphertext TEXT NULL,
    text_hash VARCHAR(96) NULL,
    captured_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_understanding_sources_run
        FOREIGN KEY (understanding_id)
        REFERENCES understanding_runs(understanding_id) ON DELETE CASCADE,
    CONSTRAINT ck_understanding_sources_type
        CHECK (source_type IN ('document', 'case_summary', 'narrative',
            'voice_transcript', 'questionnaire', 'user_correction')),
    CONSTRAINT ck_understanding_sources_status
        CHECK (processing_status IN ('uploading', 'processing',
            'needs_confirmation', 'ready', 'degraded', 'failed', 'skipped')),
    CONSTRAINT ck_understanding_sources_single
        CHECK (
            (CASE WHEN document_id IS NOT NULL THEN 1 ELSE 0 END)
            + (CASE WHEN audio_id IS NOT NULL THEN 1 ELSE 0 END)
            + (CASE WHEN questionnaire_submission_id IS NOT NULL THEN 1 ELSE 0 END)
            <= 1
        )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_understanding_sources_understanding_type
    ON understanding_sources(understanding_id, source_type);

CREATE TABLE IF NOT EXISTS understanding_revisions (
    understanding_id VARCHAR(64) NOT NULL,
    revision INTEGER NOT NULL,
    previous_revision INTEGER NULL,
    status VARCHAR(24) NOT NULL,
    case_summary_json JSON NULL,
    presentation_json JSON NOT NULL,
    confirmation_decision VARCHAR(32) NULL,
    confirmed_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (understanding_id, revision),
    CONSTRAINT fk_understanding_revisions_run
        FOREIGN KEY (understanding_id)
        REFERENCES understanding_runs(understanding_id) ON DELETE CASCADE,
    CONSTRAINT ck_understanding_revisions_revision
        CHECK (revision >= 1),
    CONSTRAINT ck_understanding_revisions_status
        CHECK (status IN ('needs_confirmation', 'confirmed', 'degraded')),
    CONSTRAINT ck_understanding_revisions_decision
        CHECK (
            confirmation_decision IS NULL
            OR confirmation_decision IN ('confirm', 'confirm_with_changes',
                'reject_source', 'cannot_confirm')
        ),
    CONSTRAINT ck_understanding_revisions_confirmed
        CHECK (confirmed_at IS NULL OR confirmation_decision IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS questionnaire_submissions_v3 (
    questionnaire_submission_id VARCHAR(64) PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    schema_id VARCHAR(32) NOT NULL,
    schema_version VARCHAR(32) NOT NULL,
    manifest_version VARCHAR(32) NOT NULL,
    content_checksum VARCHAR(96) NOT NULL,
    time_window_days INTEGER NOT NULL,
    answers_json JSON NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    submitted_at DATETIME(6) NOT NULL,
    CONSTRAINT fk_questionnaire_submissions_user
        FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_questionnaire_submissions_session
        FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    CONSTRAINT ck_questionnaire_submissions_schema
        CHECK (schema_id = 'questionnaire_v3'),
    CONSTRAINT ck_questionnaire_submissions_checksum
        CHECK (content_checksum LIKE 'sha256:%'),
    CONSTRAINT ck_questionnaire_submissions_window
        CHECK (time_window_days = 7),
    CONSTRAINT uq_questionnaire_submissions_idem
        UNIQUE (internal_user_pk, idempotency_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_questionnaire_submissions_session_time
    ON questionnaire_submissions_v3(session_row_id, submitted_at);

CREATE TABLE IF NOT EXISTS normalized_facts (
    fact_row_id VARCHAR(64) PRIMARY KEY,
    fact_id VARCHAR(64) NOT NULL,
    owner_type VARCHAR(16) NOT NULL,
    understanding_id VARCHAR(64) NULL,
    understanding_revision INTEGER NULL,
    questionnaire_submission_id VARCHAR(64) NULL,
    fact_code VARCHAR(64) NOT NULL,
    category VARCHAR(32) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    value_json JSON NOT NULL,
    time_window VARCHAR(16) NOT NULL,
    negated TINYINT NOT NULL,
    subject VARCHAR(16) NOT NULL,
    confirmation_status VARCHAR(16) NOT NULL,
    extraction_method VARCHAR(32) NOT NULL,
    extraction_confidence DECIMAL(6,5) NULL,
    supersedes_fact_row_id VARCHAR(64) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_normalized_facts_revision
        FOREIGN KEY (understanding_id, understanding_revision)
        REFERENCES understanding_revisions(understanding_id, revision),
    CONSTRAINT fk_normalized_facts_questionnaire
        FOREIGN KEY (questionnaire_submission_id)
        REFERENCES questionnaire_submissions_v3(questionnaire_submission_id),
    CONSTRAINT ck_normalized_facts_owner
        CHECK (owner_type IN ('understanding', 'questionnaire')),
    CONSTRAINT ck_normalized_facts_owner_exclusive
        CHECK (
            (owner_type = 'understanding' AND understanding_id IS NOT NULL
                AND understanding_revision IS NOT NULL
                AND questionnaire_submission_id IS NULL)
            OR
            (owner_type = 'questionnaire' AND questionnaire_submission_id IS NOT NULL
                AND understanding_id IS NULL AND understanding_revision IS NULL)
        ),
    CONSTRAINT ck_normalized_facts_negated
        CHECK (negated IN (0, 1)),
    CONSTRAINT ck_normalized_facts_subject
        CHECK (subject IN ('self', 'other', 'unknown')),
    CONSTRAINT ck_normalized_facts_confirmation
        CHECK (confirmation_status IN ('confirmed', 'unconfirmed', 'rejected')),
    CONSTRAINT ck_normalized_facts_method
        CHECK (extraction_method IN ('qwen', 'rule', 'user_correction',
            'deterministic_questionnaire_mapping')),
    CONSTRAINT ck_normalized_facts_confidence
        CHECK (
            extraction_confidence IS NULL
            OR (extraction_confidence >= 0 AND extraction_confidence <= 1)
        ),
    CONSTRAINT uq_normalized_facts_understanding
        UNIQUE (understanding_id, understanding_revision, fact_id),
    CONSTRAINT uq_normalized_facts_questionnaire
        UNIQUE (questionnaire_submission_id, fact_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_normalized_facts_understanding_confirmation
    ON normalized_facts(understanding_id, understanding_revision, confirmation_status);
CREATE INDEX ix_normalized_facts_questionnaire
    ON normalized_facts(questionnaire_submission_id);

CREATE TABLE IF NOT EXISTS fact_source_refs (
    fact_row_id VARCHAR(64) NOT NULL,
    source_type VARCHAR(24) NOT NULL,
    source_id VARCHAR(64) NOT NULL,
    span_ref VARCHAR(255) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (fact_row_id, source_type, source_id),
    CONSTRAINT fk_fact_source_refs_fact
        FOREIGN KEY (fact_row_id)
        REFERENCES normalized_facts(fact_row_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- 5. Assessment Tables
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assessment_v3 (
    assessment_id VARCHAR(64) PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    understanding_id VARCHAR(64) NOT NULL,
    understanding_revision INTEGER NOT NULL,
    questionnaire_submission_id VARCHAR(64) NULL,
    current_revision INTEGER NOT NULL,
    status VARCHAR(24) NOT NULL,
    safety_status VARCHAR(32) NOT NULL,
    user_goal_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_assessment_v3_user
        FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_assessment_v3_session
        FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    CONSTRAINT fk_assessment_v3_understanding
        FOREIGN KEY (understanding_id, understanding_revision)
        REFERENCES understanding_revisions(understanding_id, revision),
    CONSTRAINT fk_assessment_v3_questionnaire
        FOREIGN KEY (questionnaire_submission_id)
        REFERENCES questionnaire_submissions_v3(questionnaire_submission_id),
    CONSTRAINT ck_assessment_v3_revision
        CHECK (current_revision >= 1),
    CONSTRAINT ck_assessment_v3_status
        CHECK (status IN ('needs_confirmation', 'confirmed', 'degraded', 'withheld')),
    CONSTRAINT uq_assessment_v3_session
        UNIQUE (session_row_id, assessment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_assessment_v3_user_created
    ON assessment_v3(internal_user_pk, created_at DESC);
CREATE INDEX ix_assessment_v3_session_status
    ON assessment_v3(session_row_id, status);

CREATE TABLE IF NOT EXISTS assessment_revisions_v3 (
    assessment_id VARCHAR(64) NOT NULL,
    revision INTEGER NOT NULL,
    previous_revision INTEGER NULL,
    understanding_revision INTEGER NOT NULL,
    status VARCHAR(24) NOT NULL,
    confirmation_status VARCHAR(16) NOT NULL,
    state_summary TEXT NOT NULL,
    recent_context_summary TEXT NULL,
    organ_profile_json JSON NOT NULL,
    evidence_coverage DECIMAL(6,5) NOT NULL,
    source_diversity INTEGER NOT NULL,
    conflicts_json JSON NOT NULL,
    missing_information_json JSON NOT NULL,
    degradation_json JSON NOT NULL,
    presentation_json JSON NOT NULL,
    confirmed_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (assessment_id, revision),
    CONSTRAINT fk_assessment_revisions_assessment
        FOREIGN KEY (assessment_id)
        REFERENCES assessment_v3(assessment_id) ON DELETE CASCADE,
    CONSTRAINT ck_assessment_revisions_revision
        CHECK (revision >= 1),
    CONSTRAINT ck_assessment_revisions_evidence
        CHECK (evidence_coverage >= 0 AND evidence_coverage <= 1),
    CONSTRAINT ck_assessment_revisions_diversity
        CHECK (source_diversity >= 0),
    CONSTRAINT ck_assessment_revisions_confirmed
        CHECK (confirmed_at IS NULL OR confirmation_status = 'confirmed')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fact_evidence (
    fact_evidence_row_id VARCHAR(64) PRIMARY KEY,
    fact_evidence_id VARCHAR(64) NOT NULL,
    assessment_id VARCHAR(64) NOT NULL,
    assessment_revision INTEGER NOT NULL,
    normalized_fact_row_id VARCHAR(64) NOT NULL,
    claim_code VARCHAR(64) NOT NULL,
    category VARCHAR(32) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    value_json JSON NOT NULL,
    time_window VARCHAR(16) NOT NULL,
    direction VARCHAR(16) NOT NULL,
    reliability DECIMAL(6,5) NOT NULL,
    confirmation_status VARCHAR(16) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_fact_evidence_revision
        FOREIGN KEY (assessment_id, assessment_revision)
        REFERENCES assessment_revisions_v3(assessment_id, revision),
    CONSTRAINT fk_fact_evidence_normalized_fact
        FOREIGN KEY (normalized_fact_row_id) REFERENCES normalized_facts(fact_row_id),
    CONSTRAINT ck_fact_evidence_direction
        CHECK (direction IN ('supporting', 'contradicting')),
    CONSTRAINT ck_fact_evidence_reliability
        CHECK (reliability >= 0 AND reliability <= 1),
    CONSTRAINT ck_fact_evidence_confirmation
        CHECK (confirmation_status IN ('confirmed', 'unconfirmed', 'rejected')),
    CONSTRAINT uq_fact_evidence_id
        UNIQUE (assessment_id, assessment_revision, fact_evidence_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_fact_evidence_normalized_fact
    ON fact_evidence(normalized_fact_row_id);

CREATE TABLE IF NOT EXISTS organ_evidence (
    organ_evidence_link_id VARCHAR(64) PRIMARY KEY,
    fact_evidence_row_id VARCHAR(64) NOT NULL,
    organ VARCHAR(16) NOT NULL,
    element VARCHAR(16) NOT NULL,
    direction VARCHAR(16) NOT NULL,
    link_strength DECIMAL(6,5) NOT NULL,
    mapping_rule_id VARCHAR(64) NOT NULL,
    mapping_version VARCHAR(32) NOT NULL,
    explanation_summary TEXT NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_organ_evidence_fact_evidence
        FOREIGN KEY (fact_evidence_row_id)
        REFERENCES fact_evidence(fact_evidence_row_id) ON DELETE CASCADE,
    CONSTRAINT ck_organ_evidence_organ
        CHECK (organ IN ('liver', 'heart', 'spleen', 'lung', 'kidney')),
    CONSTRAINT ck_organ_evidence_element
        CHECK (element IN ('wood', 'fire', 'earth', 'metal', 'water')),
    CONSTRAINT ck_organ_evidence_direction
        CHECK (direction IN ('supporting', 'contradicting')),
    CONSTRAINT ck_organ_evidence_strength
        CHECK (link_strength >= 0 AND link_strength <= 1),
    CONSTRAINT uq_organ_evidence_link
        UNIQUE (fact_evidence_row_id, organ, mapping_rule_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_organ_evidence_organ_mapping
    ON organ_evidence(organ, mapping_version);

-- ------------------------------------------------------------
-- 6. Diagnosis / RAG Tables
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS diagnosis_runs (
    diagnosis_id VARCHAR(64) PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    assessment_id VARCHAR(64) NOT NULL,
    assessment_revision INTEGER NOT NULL,
    status VARCHAR(16) NOT NULL,
    abstained TINYINT NOT NULL,
    abstain_reason VARCHAR(255) NULL,
    primary_tendency_id VARCHAR(64) NULL,
    element_profile_json JSON NULL,
    degradation_json JSON NOT NULL,
    presentation_json JSON NOT NULL,
    provider_run_id VARCHAR(64) NULL,
    rag_run_id VARCHAR(64) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_diagnosis_runs_user
        FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_diagnosis_runs_session
        FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    CONSTRAINT fk_diagnosis_runs_assessment
        FOREIGN KEY (assessment_id, assessment_revision)
        REFERENCES assessment_revisions_v3(assessment_id, revision),
    CONSTRAINT ck_diagnosis_runs_status
        CHECK (status IN ('running', 'success', 'degraded', 'abstained',
            'withheld', 'failed')),
    CONSTRAINT ck_diagnosis_runs_abstained
        CHECK (abstained IN (0, 1)),
    CONSTRAINT ck_diagnosis_runs_abstain_reason
        CHECK (abstained = 1 OR abstain_reason IS NULL),
    CONSTRAINT uq_diagnosis_runs_assessment
        UNIQUE (assessment_id, assessment_revision, diagnosis_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_diagnosis_runs_session_created
    ON diagnosis_runs(session_row_id, created_at);
CREATE INDEX ix_diagnosis_runs_status
    ON diagnosis_runs(status);

CREATE TABLE IF NOT EXISTS diagnosis_candidates (
    candidate_id VARCHAR(64) PRIMARY KEY,
    diagnosis_id VARCHAR(64) NOT NULL,
    syndrome_code VARCHAR(64) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    relative_support DECIMAL(6,5) NOT NULL,
    reasoning_summary TEXT NOT NULL,
    rank INTEGER NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_diagnosis_candidates_run
        FOREIGN KEY (diagnosis_id)
        REFERENCES diagnosis_runs(diagnosis_id) ON DELETE CASCADE,
    CONSTRAINT ck_diagnosis_candidates_support
        CHECK (relative_support >= 0 AND relative_support <= 1),
    CONSTRAINT ck_diagnosis_candidates_rank
        CHECK (rank >= 1),
    CONSTRAINT uq_diagnosis_candidates_syndrome
        UNIQUE (diagnosis_id, syndrome_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS diagnosis_candidate_evidence (
    candidate_id VARCHAR(64) NOT NULL,
    fact_evidence_row_id VARCHAR(64) NOT NULL,
    direction VARCHAR(16) NOT NULL,
    PRIMARY KEY (candidate_id, fact_evidence_row_id),
    CONSTRAINT fk_diagnosis_candidate_evidence_candidate
        FOREIGN KEY (candidate_id)
        REFERENCES diagnosis_candidates(candidate_id) ON DELETE CASCADE,
    CONSTRAINT fk_diagnosis_candidate_evidence_fact
        FOREIGN KEY (fact_evidence_row_id) REFERENCES fact_evidence(fact_evidence_row_id),
    CONSTRAINT ck_diagnosis_candidate_evidence_direction
        CHECK (direction IN ('supporting', 'contradicting'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS knowledge_manifests (
    knowledge_manifest_id VARCHAR(64) PRIMARY KEY,
    knowledge_version VARCHAR(64) NOT NULL,
    embedding_provider VARCHAR(64) NOT NULL,
    embedding_model VARCHAR(64) NOT NULL,
    embedding_version VARCHAR(64) NOT NULL,
    distance_metric VARCHAR(16) NOT NULL,
    score_semantics VARCHAR(64) NOT NULL,
    minimum_score DECIMAL(6,5) NOT NULL,
    chunk_count INTEGER NOT NULL,
    manifest_checksum VARCHAR(96) NOT NULL,
    review_status VARCHAR(16) NOT NULL,
    medical_review_version VARCHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uq_knowledge_manifests_version
        UNIQUE (knowledge_version),
    CONSTRAINT uq_knowledge_manifests_checksum
        UNIQUE (manifest_checksum),
    CONSTRAINT ck_knowledge_manifests_minimum_score
        CHECK (minimum_score >= 0 AND minimum_score <= 1),
    CONSTRAINT ck_knowledge_manifests_chunk_count
        CHECK (chunk_count >= 0),
    CONSTRAINT ck_knowledge_manifests_review
        CHECK (review_status IN ('approved', 'pending', 'rejected'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS knowledge_chunks_v3 (
    chunk_row_id VARCHAR(64) PRIMARY KEY,
    knowledge_manifest_id VARCHAR(64) NOT NULL,
    chunk_id VARCHAR(64) NOT NULL,
    source_id VARCHAR(64) NOT NULL,
    source_title VARCHAR(255) NOT NULL,
    section VARCHAR(64) NOT NULL,
    text_ciphertext TEXT NOT NULL,
    display_summary TEXT NOT NULL,
    claim_codes_json JSON NOT NULL,
    organ_codes_json JSON NOT NULL,
    content_checksum VARCHAR(96) NOT NULL,
    review_status VARCHAR(16) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_knowledge_chunks_manifest
        FOREIGN KEY (knowledge_manifest_id)
        REFERENCES knowledge_manifests(knowledge_manifest_id) ON DELETE CASCADE,
    CONSTRAINT uq_knowledge_chunks_id
        UNIQUE (knowledge_manifest_id, chunk_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_knowledge_chunks_manifest_review
    ON knowledge_chunks_v3(knowledge_manifest_id, review_status);

CREATE TABLE IF NOT EXISTS rag_retrieval_runs (
    rag_run_id VARCHAR(64) PRIMARY KEY,
    diagnosis_id VARCHAR(64) NOT NULL,
    query_hash VARCHAR(96) NOT NULL,
    query_builder_version VARCHAR(32) NOT NULL,
    knowledge_manifest_id VARCHAR(64) NOT NULL,
    knowledge_version VARCHAR(64) NOT NULL,
    manifest_checksum VARCHAR(96) NOT NULL,
    embedding_version VARCHAR(64) NOT NULL,
    distance_metric VARCHAR(16) NOT NULL,
    score_semantics VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL,
    top_k INTEGER NOT NULL,
    minimum_score DECIMAL(6,5) NOT NULL,
    degradation_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_rag_retrieval_runs_diagnosis
        FOREIGN KEY (diagnosis_id)
        REFERENCES diagnosis_runs(diagnosis_id) ON DELETE CASCADE,
    CONSTRAINT fk_rag_retrieval_runs_manifest
        FOREIGN KEY (knowledge_manifest_id) REFERENCES knowledge_manifests(knowledge_manifest_id),
    CONSTRAINT ck_rag_retrieval_runs_status
        CHECK (status IN ('success', 'degraded', 'failed', 'empty')),
    CONSTRAINT ck_rag_retrieval_runs_top_k
        CHECK (top_k >= 1),
    CONSTRAINT ck_rag_retrieval_runs_minimum_score
        CHECK (minimum_score >= 0 AND minimum_score <= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS rag_retrieval_hits (
    rag_run_id VARCHAR(64) NOT NULL,
    chunk_id VARCHAR(64) NOT NULL,
    source_id VARCHAR(64) NOT NULL,
    source_title VARCHAR(255) NOT NULL,
    section VARCHAR(64) NOT NULL,
    retrieval_score DECIMAL(6,5) NOT NULL,
    display_summary TEXT NOT NULL,
    text_ciphertext TEXT NOT NULL,
    review_status VARCHAR(16) NOT NULL,
    knowledge_version VARCHAR(64) NOT NULL,
    chunk_content_checksum VARCHAR(96) NOT NULL,
    PRIMARY KEY (rag_run_id, chunk_id),
    CONSTRAINT fk_rag_retrieval_hits_run
        FOREIGN KEY (rag_run_id)
        REFERENCES rag_retrieval_runs(rag_run_id) ON DELETE CASCADE,
    CONSTRAINT ck_rag_retrieval_hits_score
        CHECK (retrieval_score >= 0 AND retrieval_score <= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ai_provider_runs (
    provider_run_id VARCHAR(64) PRIMARY KEY,
    purpose VARCHAR(16) NOT NULL,
    resource_id VARCHAR(64) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    model VARCHAR(64) NULL,
    prompt_version VARCHAR(32) NOT NULL,
    response_schema_version VARCHAR(32) NOT NULL,
    status VARCHAR(16) NOT NULL,
    error_code VARCHAR(32) NULL,
    attempts INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    input_tokens INTEGER NULL,
    output_tokens INTEGER NULL,
    request_hash VARCHAR(96) NULL,
    response_hash VARCHAR(96) NULL,
    knowledge_version VARCHAR(64) NULL,
    mapping_version VARCHAR(32) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT ck_ai_provider_runs_purpose
        CHECK (purpose IN ('understanding', 'diagnosis', 'schema_repair')),
    CONSTRAINT ck_ai_provider_runs_attempts
        CHECK (attempts >= 1),
    CONSTRAINT ck_ai_provider_runs_latency
        CHECK (latency_ms >= 0),
    CONSTRAINT ck_ai_provider_runs_input_tokens
        CHECK (input_tokens IS NULL OR input_tokens >= 0),
    CONSTRAINT ck_ai_provider_runs_output_tokens
        CHECK (output_tokens IS NULL OR output_tokens >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_ai_provider_runs_resource
    ON ai_provider_runs(resource_id, created_at);

-- ------------------------------------------------------------
-- 7. Prescription / Music Tables
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prescription_v3 (
    prescription_id VARCHAR(64) PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    diagnosis_id VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL,
    prescription_mode VARCHAR(24) NULL,
    tone_profile_json JSON NULL,
    generation_spec_json JSON NULL,
    preference_profile_id VARCHAR(64) NULL,
    preference_version_id VARCHAR(64) NULL,
    personalization_json JSON NOT NULL,
    presentation_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_prescription_v3_user
        FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_prescription_v3_session
        FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    CONSTRAINT fk_prescription_v3_diagnosis
        FOREIGN KEY (diagnosis_id) REFERENCES diagnosis_runs(diagnosis_id),
    CONSTRAINT ck_prescription_v3_status
        CHECK (status IN ('success', 'degraded', 'withheld')),
    CONSTRAINT ck_prescription_v3_mode
        CHECK (prescription_mode IS NULL OR prescription_mode IN (
            'syndrome_based', 'conservative_fallback')),
    CONSTRAINT ck_prescription_v3_spec
        CHECK (
            (status = 'withheld' AND generation_spec_json IS NULL)
            OR (status IN ('success', 'degraded') AND generation_spec_json IS NOT NULL)
        )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_prescription_v3_user_created
    ON prescription_v3(internal_user_pk, created_at DESC);
CREATE INDEX ix_prescription_v3_diagnosis
    ON prescription_v3(diagnosis_id);

-- music_assets is created BEFORE generation_tasks so that the
-- generation_tasks.music_asset_id FK has a target. The reverse FK
-- (music_assets.generation_task_id) is added via ALTER after
-- generation_tasks exists to break the creation-cycle.
CREATE TABLE IF NOT EXISTS music_assets (
    music_asset_id VARCHAR(64) PRIMARY KEY,
    owner_internal_user_pk INTEGER NULL,
    generation_task_id VARCHAR(64) NULL,
    source_type VARCHAR(16) NOT NULL,
    catalog_track_id VARCHAR(64) NULL,
    title VARCHAR(255) NOT NULL,
    storage_key VARCHAR(255) NOT NULL,
    format VARCHAR(8) NOT NULL,
    duration_seconds INTEGER NOT NULL,
    checksum VARCHAR(96) NOT NULL,
    tone_profile_json JSON NULL,
    bpm INTEGER NULL,
    instruments_json JSON NULL,
    playable_status VARCHAR(16) NOT NULL,
    retention_expires_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_music_assets_owner
        FOREIGN KEY (owner_internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT ck_music_assets_source_type
        CHECK (source_type IN ('generated', 'matched', 'comfort_audio')),
    CONSTRAINT ck_music_assets_format
        CHECK (format IN ('mp3', 'wav', 'm4a')),
    CONSTRAINT ck_music_assets_duration
        CHECK (duration_seconds > 0),
    CONSTRAINT ck_music_assets_checksum
        CHECK (checksum LIKE 'sha256:%'),
    CONSTRAINT ck_music_assets_bpm
        CHECK (bpm IS NULL OR (bpm >= 40 AND bpm <= 120)),
    CONSTRAINT ck_music_assets_playable
        CHECK (playable_status IN ('ready', 'expired', 'quarantined', 'deleted')),
    CONSTRAINT ck_music_assets_generated_source
        CHECK (
            (source_type = 'generated' AND generation_task_id IS NOT NULL)
            OR (source_type != 'generated')
        ),
    CONSTRAINT uq_music_assets_checksum_owner
        UNIQUE (checksum, owner_internal_user_pk)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS generation_tasks (
    task_id VARCHAR(64) PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    prescription_id VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    status VARCHAR(24) NOT NULL,
    provider VARCHAR(64) NULL,
    provider_task_id VARCHAR(64) NULL,
    progress_value INTEGER NULL,
    progress_indeterminate TINYINT NOT NULL,
    message_code VARCHAR(64) NOT NULL,
    fallback_applied TINYINT NOT NULL,
    fallback_reason_code VARCHAR(64) NULL,
    error_code VARCHAR(64) NULL,
    music_asset_id VARCHAR(64) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    completed_at DATETIME(6) NULL,
    CONSTRAINT fk_generation_tasks_user
        FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_generation_tasks_session
        FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    CONSTRAINT fk_generation_tasks_prescription
        FOREIGN KEY (prescription_id) REFERENCES prescription_v3(prescription_id),
    CONSTRAINT fk_generation_tasks_music_asset
        FOREIGN KEY (music_asset_id) REFERENCES music_assets(music_asset_id),
    CONSTRAINT ck_generation_tasks_status
        CHECK (status IN ('queued', 'running', 'succeeded', 'matched_fallback',
            'failed', 'cancelled')),
    CONSTRAINT ck_generation_tasks_progress
        CHECK (progress_value IS NULL OR (progress_value >= 0 AND progress_value <= 100)),
    CONSTRAINT ck_generation_tasks_indeterminate
        CHECK (progress_indeterminate IN (0, 1)),
    CONSTRAINT ck_generation_tasks_fallback
        CHECK (fallback_applied IN (0, 1)),
    CONSTRAINT ck_generation_tasks_asset_consistency
        CHECK (
            (status = 'succeeded' AND music_asset_id IS NOT NULL AND fallback_applied = 0)
            OR
            (status = 'matched_fallback' AND music_asset_id IS NOT NULL AND fallback_applied = 1)
            OR
            (status IN ('queued', 'running', 'failed', 'cancelled') AND music_asset_id IS NULL)
        ),
    CONSTRAINT uq_generation_tasks_idem
        UNIQUE (internal_user_pk, idempotency_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_generation_tasks_status_updated
    ON generation_tasks(status, updated_at);
CREATE INDEX ix_generation_tasks_prescription
    ON generation_tasks(prescription_id);

-- Close the music_assets <-> generation_tasks cycle.
ALTER TABLE music_assets
    ADD CONSTRAINT fk_music_assets_generation_task
    FOREIGN KEY (generation_task_id) REFERENCES generation_tasks(task_id);

-- ------------------------------------------------------------
-- 8. Feedback / Preference / Favorite Tables
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback_v3 (
    feedback_id VARCHAR(64) PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    music_asset_id VARCHAR(64) NOT NULL,
    change_label VARCHAR(16) NOT NULL,
    pre_state_snapshot_json JSON NULL,
    post_state_json JSON NULL,
    experience_json JSON NULL,
    continue_use VARCHAR(8) NULL,
    liked_features_json JSON NOT NULL,
    adjustment_preferences_json JSON NOT NULL,
    comment_ciphertext TEXT NULL,
    playback_json JSON NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    preference_update_status VARCHAR(16) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_feedback_v3_user
        FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_feedback_v3_session
        FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    CONSTRAINT fk_feedback_v3_music_asset
        FOREIGN KEY (music_asset_id) REFERENCES music_assets(music_asset_id),
    CONSTRAINT ck_feedback_v3_change_label
        CHECK (change_label IN ('much_better', 'slightly_better', 'no_change', 'worse')),
    CONSTRAINT ck_feedback_v3_continue_use
        CHECK (continue_use IS NULL OR continue_use IN ('yes', 'maybe', 'no')),
    CONSTRAINT ck_feedback_v3_preference_status
        CHECK (preference_update_status IN ('pending', 'applied', 'failed', 'skipped')),
    CONSTRAINT uq_feedback_v3_idem
        UNIQUE (internal_user_pk, idempotency_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_feedback_v3_user_created
    ON feedback_v3(internal_user_pk, created_at DESC);
CREATE INDEX ix_feedback_v3_music_asset
    ON feedback_v3(music_asset_id);

CREATE TABLE IF NOT EXISTS user_music_preferences (
    profile_id VARCHAR(64) PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    current_version_id VARCHAR(64) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_user_music_preferences_user
        FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_user_music_preferences_user
        UNIQUE (internal_user_pk)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS user_music_preference_versions (
    preference_version_id VARCHAR(64) PRIMARY KEY,
    profile_id VARCHAR(64) NOT NULL,
    version INTEGER NOT NULL,
    preferred_bpm_min INTEGER NULL,
    preferred_bpm_max INTEGER NULL,
    bpm_weight DECIMAL(6,5) NULL,
    preferred_duration_seconds INTEGER NULL,
    duration_weight DECIMAL(6,5) NULL,
    feedback_count INTEGER NOT NULL,
    minimum_samples_for_application INTEGER NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_user_music_preference_versions_profile
        FOREIGN KEY (profile_id)
        REFERENCES user_music_preferences(profile_id) ON DELETE CASCADE,
    CONSTRAINT ck_preference_versions_version
        CHECK (version >= 1),
    CONSTRAINT ck_preference_versions_bpm_min
        CHECK (preferred_bpm_min IS NULL OR (preferred_bpm_min >= 40 AND preferred_bpm_min <= 120)),
    CONSTRAINT ck_preference_versions_bpm_max
        CHECK (preferred_bpm_max IS NULL OR (preferred_bpm_max >= 40 AND preferred_bpm_max <= 120)),
    CONSTRAINT ck_preference_versions_bpm_range
        CHECK (
            (preferred_bpm_min IS NULL AND preferred_bpm_max IS NULL)
            OR (preferred_bpm_min IS NOT NULL AND preferred_bpm_max IS NOT NULL
                AND preferred_bpm_min <= preferred_bpm_max)
        ),
    CONSTRAINT ck_preference_versions_bpm_weight
        CHECK (bpm_weight IS NULL OR (bpm_weight >= 0 AND bpm_weight <= 1)),
    CONSTRAINT ck_preference_versions_duration
        CHECK (preferred_duration_seconds IS NULL OR preferred_duration_seconds > 0),
    CONSTRAINT ck_preference_versions_duration_weight
        CHECK (duration_weight IS NULL OR (duration_weight >= 0 AND duration_weight <= 1)),
    CONSTRAINT ck_preference_versions_feedback_count
        CHECK (feedback_count >= 0),
    CONSTRAINT ck_preference_versions_min_samples
        CHECK (minimum_samples_for_application >= 1),
    CONSTRAINT uq_preference_versions_profile_version
        UNIQUE (profile_id, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS user_preference_items (
    preference_version_id VARCHAR(64) NOT NULL,
    category VARCHAR(16) NOT NULL,
    code VARCHAR(64) NOT NULL,
    polarity VARCHAR(16) NOT NULL,
    weight DECIMAL(6,5) NOT NULL,
    sample_count INTEGER NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (preference_version_id, category, code, polarity),
    CONSTRAINT fk_user_preference_items_version
        FOREIGN KEY (preference_version_id)
        REFERENCES user_music_preference_versions(preference_version_id) ON DELETE CASCADE,
    CONSTRAINT ck_preference_items_category
        CHECK (category IN ('instrument', 'feature', 'ambient')),
    CONSTRAINT ck_preference_items_polarity
        CHECK (polarity IN ('preferred', 'disliked')),
    CONSTRAINT ck_preference_items_weight
        CHECK (weight >= 0 AND weight <= 1),
    CONSTRAINT ck_preference_items_sample_count
        CHECK (sample_count >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS preference_events (
    event_id VARCHAR(64) PRIMARY KEY,
    profile_id VARCHAR(64) NOT NULL,
    feedback_id VARCHAR(64) NULL,
    previous_version_id VARCHAR(64) NULL,
    new_version_id VARCHAR(64) NULL,
    patch_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_preference_events_profile
        FOREIGN KEY (profile_id)
        REFERENCES user_music_preferences(profile_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS favorites (
    favorite_id VARCHAR(64) PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    music_asset_id VARCHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_favorites_user
        FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_favorites_music_asset
        FOREIGN KEY (music_asset_id) REFERENCES music_assets(music_asset_id),
    CONSTRAINT uq_favorites_user_asset
        UNIQUE (internal_user_pk, music_asset_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

PRAGMA foreign_keys=OFF;
BEGIN IMMEDIATE;

-- ============================================================
-- 0002_v3_business — V3 business persistence tables (SQLite)
-- Mirrors harmonyai-v3-persistence-contract.md sections 4-8.
-- All timestamps are UTC; JSON columns are TEXT validated by the
-- application-layer Pydantic schemas.
-- ============================================================

-- ------------------------------------------------------------
-- 4. Information Understanding Tables
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS understanding_runs (
    understanding_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    current_revision INTEGER NOT NULL CHECK (current_revision >= 1),
    status TEXT NOT NULL CHECK (status IN (
        'queued', 'processing', 'needs_confirmation',
        'confirmed', 'degraded', 'failed'
    )),
    safety_status TEXT NOT NULL,
    degradation_json TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    UNIQUE (understanding_id, internal_user_pk)
);
CREATE INDEX IF NOT EXISTS ix_understanding_runs_session
    ON understanding_runs(session_row_id);
CREATE INDEX IF NOT EXISTS ix_understanding_runs_user_status
    ON understanding_runs(internal_user_pk, status);

CREATE TABLE IF NOT EXISTS understanding_sources (
    source_id TEXT PRIMARY KEY,
    understanding_id TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN (
        'document', 'case_summary', 'narrative',
        'voice_transcript', 'questionnaire', 'user_correction'
    )),
    processing_status TEXT NOT NULL CHECK (processing_status IN (
        'uploading', 'processing', 'needs_confirmation',
        'ready', 'degraded', 'failed', 'skipped'
    )),
    document_id TEXT,
    audio_id TEXT,
    questionnaire_submission_id TEXT,
    text_ciphertext TEXT,
    text_hash TEXT,
    captured_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (understanding_id) REFERENCES understanding_runs(understanding_id) ON DELETE CASCADE,
    CHECK (
        (CASE WHEN document_id IS NOT NULL THEN 1 ELSE 0 END)
        + (CASE WHEN audio_id IS NOT NULL THEN 1 ELSE 0 END)
        + (CASE WHEN questionnaire_submission_id IS NOT NULL THEN 1 ELSE 0 END)
        <= 1
    )
);
CREATE INDEX IF NOT EXISTS ix_understanding_sources_understanding_type
    ON understanding_sources(understanding_id, source_type);

CREATE TABLE IF NOT EXISTS understanding_revisions (
    understanding_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    previous_revision INTEGER,
    status TEXT NOT NULL CHECK (status IN (
        'needs_confirmation', 'confirmed', 'degraded'
    )),
    case_summary_json TEXT,
    presentation_json TEXT NOT NULL,
    confirmation_decision TEXT,
    confirmed_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (understanding_id, revision),
    FOREIGN KEY (understanding_id) REFERENCES understanding_runs(understanding_id) ON DELETE CASCADE,
    CHECK (
        (confirmation_decision IS NULL) OR
        (confirmation_decision IN ('confirm', 'confirm_with_changes', 'reject_source', 'cannot_confirm'))
    ),
    CHECK (
        (confirmed_at IS NULL) OR (confirmation_decision IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS questionnaire_submissions_v3 (
    questionnaire_submission_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    schema_id TEXT NOT NULL CHECK (schema_id = 'questionnaire_v3'),
    schema_version TEXT NOT NULL,
    manifest_version TEXT NOT NULL,
    content_checksum TEXT NOT NULL CHECK (content_checksum LIKE 'sha256:%'),
    time_window_days INTEGER NOT NULL CHECK (time_window_days = 7),
    answers_json TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    submitted_at DATETIME NOT NULL,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    UNIQUE (internal_user_pk, idempotency_key)
);
CREATE INDEX IF NOT EXISTS ix_questionnaire_submissions_session_time
    ON questionnaire_submissions_v3(session_row_id, submitted_at);

CREATE TABLE IF NOT EXISTS normalized_facts (
    fact_row_id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL,
    owner_type TEXT NOT NULL CHECK (owner_type IN ('understanding', 'questionnaire')),
    understanding_id TEXT,
    understanding_revision INTEGER,
    questionnaire_submission_id TEXT,
    fact_code TEXT NOT NULL,
    category TEXT NOT NULL,
    display_name TEXT NOT NULL,
    value_json TEXT NOT NULL,
    time_window TEXT NOT NULL,
    negated INTEGER NOT NULL CHECK (negated IN (0, 1)),
    subject TEXT NOT NULL CHECK (subject IN ('self', 'other', 'unknown')),
    confirmation_status TEXT NOT NULL CHECK (confirmation_status IN (
        'confirmed', 'unconfirmed', 'rejected'
    )),
    extraction_method TEXT NOT NULL CHECK (extraction_method IN (
        'qwen', 'rule', 'user_correction', 'deterministic_questionnaire_mapping'
    )),
    extraction_confidence REAL CHECK (
        extraction_confidence IS NULL OR (extraction_confidence >= 0 AND extraction_confidence <= 1)
    ),
    supersedes_fact_row_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (understanding_id, understanding_revision)
        REFERENCES understanding_revisions(understanding_id, revision),
    FOREIGN KEY (questionnaire_submission_id)
        REFERENCES questionnaire_submissions_v3(questionnaire_submission_id),
    CHECK (
        (owner_type = 'understanding' AND understanding_id IS NOT NULL
            AND understanding_revision IS NOT NULL
            AND questionnaire_submission_id IS NULL)
        OR
        (owner_type = 'questionnaire' AND questionnaire_submission_id IS NOT NULL
            AND understanding_id IS NULL AND understanding_revision IS NULL)
    ),
    UNIQUE (understanding_id, understanding_revision, fact_id),
    UNIQUE (questionnaire_submission_id, fact_id)
);
CREATE INDEX IF NOT EXISTS ix_normalized_facts_understanding_confirmation
    ON normalized_facts(understanding_id, understanding_revision, confirmation_status);
CREATE INDEX IF NOT EXISTS ix_normalized_facts_questionnaire
    ON normalized_facts(questionnaire_submission_id);

CREATE TABLE IF NOT EXISTS fact_source_refs (
    fact_row_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    span_ref TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (fact_row_id, source_type, source_id),
    FOREIGN KEY (fact_row_id) REFERENCES normalized_facts(fact_row_id) ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- 5. Assessment Tables
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assessment_v3 (
    assessment_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    understanding_id TEXT NOT NULL,
    understanding_revision INTEGER NOT NULL,
    questionnaire_submission_id TEXT,
    current_revision INTEGER NOT NULL CHECK (current_revision >= 1),
    status TEXT NOT NULL CHECK (status IN (
        'needs_confirmation', 'confirmed', 'degraded', 'withheld'
    )),
    safety_status TEXT NOT NULL,
    user_goal_json TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    FOREIGN KEY (understanding_id, understanding_revision)
        REFERENCES understanding_revisions(understanding_id, revision),
    FOREIGN KEY (questionnaire_submission_id)
        REFERENCES questionnaire_submissions_v3(questionnaire_submission_id),
    UNIQUE (session_row_id, assessment_id)
);
CREATE INDEX IF NOT EXISTS ix_assessment_v3_user_created
    ON assessment_v3(internal_user_pk, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_assessment_v3_session_status
    ON assessment_v3(session_row_id, status);

CREATE TABLE IF NOT EXISTS assessment_revisions_v3 (
    assessment_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    previous_revision INTEGER,
    understanding_revision INTEGER NOT NULL,
    status TEXT NOT NULL,
    confirmation_status TEXT NOT NULL,
    state_summary TEXT NOT NULL,
    recent_context_summary TEXT,
    organ_profile_json TEXT NOT NULL,
    evidence_coverage REAL NOT NULL CHECK (evidence_coverage >= 0 AND evidence_coverage <= 1),
    source_diversity INTEGER NOT NULL CHECK (source_diversity >= 0),
    conflicts_json TEXT NOT NULL,
    missing_information_json TEXT NOT NULL,
    degradation_json TEXT NOT NULL,
    presentation_json TEXT NOT NULL,
    confirmed_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (assessment_id, revision),
    FOREIGN KEY (assessment_id) REFERENCES assessment_v3(assessment_id) ON DELETE CASCADE,
    CHECK (
        (confirmed_at IS NULL) OR (confirmation_status = 'confirmed')
    )
);

CREATE TABLE IF NOT EXISTS fact_evidence (
    fact_evidence_row_id TEXT PRIMARY KEY,
    fact_evidence_id TEXT NOT NULL,
    assessment_id TEXT NOT NULL,
    assessment_revision INTEGER NOT NULL,
    normalized_fact_row_id TEXT NOT NULL,
    claim_code TEXT NOT NULL,
    category TEXT NOT NULL,
    display_name TEXT NOT NULL,
    value_json TEXT NOT NULL,
    time_window TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('supporting', 'contradicting')),
    reliability REAL NOT NULL CHECK (reliability >= 0 AND reliability <= 1),
    confirmation_status TEXT NOT NULL CHECK (confirmation_status IN (
        'confirmed', 'unconfirmed', 'rejected'
    )),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assessment_id, assessment_revision)
        REFERENCES assessment_revisions_v3(assessment_id, revision),
    FOREIGN KEY (normalized_fact_row_id) REFERENCES normalized_facts(fact_row_id),
    UNIQUE (assessment_id, assessment_revision, fact_evidence_id)
);
CREATE INDEX IF NOT EXISTS ix_fact_evidence_normalized_fact
    ON fact_evidence(normalized_fact_row_id);

CREATE TABLE IF NOT EXISTS organ_evidence (
    organ_evidence_link_id TEXT PRIMARY KEY,
    fact_evidence_row_id TEXT NOT NULL,
    organ TEXT NOT NULL CHECK (organ IN ('liver', 'heart', 'spleen', 'lung', 'kidney')),
    element TEXT NOT NULL CHECK (element IN ('wood', 'fire', 'earth', 'metal', 'water')),
    direction TEXT NOT NULL CHECK (direction IN ('supporting', 'contradicting')),
    link_strength REAL NOT NULL CHECK (link_strength >= 0 AND link_strength <= 1),
    mapping_rule_id TEXT NOT NULL,
    mapping_version TEXT NOT NULL,
    explanation_summary TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (fact_evidence_row_id) REFERENCES fact_evidence(fact_evidence_row_id) ON DELETE CASCADE,
    UNIQUE (fact_evidence_row_id, organ, mapping_rule_id)
);
CREATE INDEX IF NOT EXISTS ix_organ_evidence_organ_mapping
    ON organ_evidence(organ, mapping_version);

-- ------------------------------------------------------------
-- 6. Diagnosis / RAG Tables
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS diagnosis_runs (
    diagnosis_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    assessment_id TEXT NOT NULL,
    assessment_revision INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'running', 'success', 'degraded', 'abstained', 'withheld', 'failed'
    )),
    abstained INTEGER NOT NULL CHECK (abstained IN (0, 1)),
    abstain_reason TEXT,
    primary_tendency_id TEXT,
    element_profile_json TEXT,
    degradation_json TEXT NOT NULL,
    presentation_json TEXT NOT NULL,
    provider_run_id TEXT,
    rag_run_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    FOREIGN KEY (assessment_id, assessment_revision)
        REFERENCES assessment_revisions_v3(assessment_id, revision),
    CHECK (
        (abstained = 1) OR (abstain_reason IS NULL)
    ),
    UNIQUE (assessment_id, assessment_revision, diagnosis_id)
);
CREATE INDEX IF NOT EXISTS ix_diagnosis_runs_session_created
    ON diagnosis_runs(session_row_id, created_at);
CREATE INDEX IF NOT EXISTS ix_diagnosis_runs_status
    ON diagnosis_runs(status);

CREATE TABLE IF NOT EXISTS diagnosis_candidates (
    candidate_id TEXT PRIMARY KEY,
    diagnosis_id TEXT NOT NULL,
    syndrome_code TEXT NOT NULL,
    display_name TEXT NOT NULL,
    relative_support REAL NOT NULL CHECK (relative_support >= 0 AND relative_support <= 1),
    reasoning_summary TEXT NOT NULL,
    rank INTEGER NOT NULL CHECK (rank >= 1),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (diagnosis_id) REFERENCES diagnosis_runs(diagnosis_id) ON DELETE CASCADE,
    UNIQUE (diagnosis_id, syndrome_code)
);

CREATE TABLE IF NOT EXISTS diagnosis_candidate_evidence (
    candidate_id TEXT NOT NULL,
    fact_evidence_row_id TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('supporting', 'contradicting')),
    PRIMARY KEY (candidate_id, fact_evidence_row_id),
    FOREIGN KEY (candidate_id) REFERENCES diagnosis_candidates(candidate_id) ON DELETE CASCADE,
    FOREIGN KEY (fact_evidence_row_id) REFERENCES fact_evidence(fact_evidence_row_id)
);

CREATE TABLE IF NOT EXISTS knowledge_manifests (
    knowledge_manifest_id TEXT PRIMARY KEY,
    knowledge_version TEXT NOT NULL UNIQUE,
    embedding_provider TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_version TEXT NOT NULL,
    distance_metric TEXT NOT NULL,
    score_semantics TEXT NOT NULL,
    minimum_score REAL NOT NULL CHECK (minimum_score >= 0 AND minimum_score <= 1),
    chunk_count INTEGER NOT NULL CHECK (chunk_count >= 0),
    manifest_checksum TEXT NOT NULL UNIQUE,
    review_status TEXT NOT NULL CHECK (review_status IN ('approved', 'pending', 'rejected')),
    medical_review_version TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_chunks_v3 (
    chunk_row_id TEXT PRIMARY KEY,
    knowledge_manifest_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_title TEXT NOT NULL,
    section TEXT NOT NULL,
    text_ciphertext TEXT NOT NULL,
    display_summary TEXT NOT NULL,
    claim_codes_json TEXT NOT NULL,
    organ_codes_json TEXT NOT NULL,
    content_checksum TEXT NOT NULL,
    review_status TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (knowledge_manifest_id) REFERENCES knowledge_manifests(knowledge_manifest_id) ON DELETE CASCADE,
    UNIQUE (knowledge_manifest_id, chunk_id)
);
CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_manifest_review
    ON knowledge_chunks_v3(knowledge_manifest_id, review_status);

CREATE TABLE IF NOT EXISTS rag_retrieval_runs (
    rag_run_id TEXT PRIMARY KEY,
    diagnosis_id TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    query_builder_version TEXT NOT NULL,
    knowledge_manifest_id TEXT NOT NULL,
    knowledge_version TEXT NOT NULL,
    manifest_checksum TEXT NOT NULL,
    embedding_version TEXT NOT NULL,
    distance_metric TEXT NOT NULL,
    score_semantics TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'degraded', 'failed', 'empty')),
    top_k INTEGER NOT NULL CHECK (top_k >= 1),
    minimum_score REAL NOT NULL CHECK (minimum_score >= 0 AND minimum_score <= 1),
    degradation_json TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (diagnosis_id) REFERENCES diagnosis_runs(diagnosis_id) ON DELETE CASCADE,
    FOREIGN KEY (knowledge_manifest_id) REFERENCES knowledge_manifests(knowledge_manifest_id),
    CHECK (
        (status = 'success') OR (status IN ('degraded', 'failed', 'empty'))
    )
);

CREATE TABLE IF NOT EXISTS rag_retrieval_hits (
    rag_run_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_title TEXT NOT NULL,
    section TEXT NOT NULL,
    retrieval_score REAL NOT NULL CHECK (retrieval_score >= 0 AND retrieval_score <= 1),
    display_summary TEXT NOT NULL,
    text_ciphertext TEXT NOT NULL,
    review_status TEXT NOT NULL,
    knowledge_version TEXT NOT NULL,
    chunk_content_checksum TEXT NOT NULL,
    PRIMARY KEY (rag_run_id, chunk_id),
    FOREIGN KEY (rag_run_id) REFERENCES rag_retrieval_runs(rag_run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_provider_runs (
    provider_run_id TEXT PRIMARY KEY,
    purpose TEXT NOT NULL CHECK (purpose IN ('understanding', 'diagnosis', 'schema_repair')),
    resource_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT,
    prompt_version TEXT NOT NULL,
    response_schema_version TEXT NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT,
    attempts INTEGER NOT NULL CHECK (attempts >= 1),
    latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
    input_tokens INTEGER CHECK (input_tokens IS NULL OR input_tokens >= 0),
    output_tokens INTEGER CHECK (output_tokens IS NULL OR output_tokens >= 0),
    request_hash TEXT,
    response_hash TEXT,
    knowledge_version TEXT,
    mapping_version TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_ai_provider_runs_resource
    ON ai_provider_runs(resource_id, created_at);

-- ------------------------------------------------------------
-- 7. Prescription / Music Tables
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prescription_v3 (
    prescription_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    diagnosis_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'degraded', 'withheld')),
    prescription_mode TEXT CHECK (prescription_mode IN (
        'syndrome_based', 'conservative_fallback'
    )),
    tone_profile_json TEXT,
    generation_spec_json TEXT,
    preference_profile_id TEXT,
    preference_version_id TEXT,
    personalization_json TEXT NOT NULL,
    presentation_json TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    FOREIGN KEY (diagnosis_id) REFERENCES diagnosis_runs(diagnosis_id),
    CHECK (
        (status = 'withheld' AND generation_spec_json IS NULL)
        OR (status IN ('success', 'degraded') AND generation_spec_json IS NOT NULL)
    )
);
CREATE INDEX IF NOT EXISTS ix_prescription_v3_user_created
    ON prescription_v3(internal_user_pk, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_prescription_v3_diagnosis
    ON prescription_v3(diagnosis_id);

CREATE TABLE IF NOT EXISTS music_assets (
    music_asset_id TEXT PRIMARY KEY,
    owner_internal_user_pk INTEGER,
    generation_task_id TEXT,
    source_type TEXT NOT NULL CHECK (source_type IN ('generated', 'matched', 'comfort_audio')),
    catalog_track_id TEXT,
    title TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    format TEXT NOT NULL CHECK (format IN ('mp3', 'wav', 'm4a')),
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds > 0),
    checksum TEXT NOT NULL CHECK (checksum LIKE 'sha256:%'),
    tone_profile_json TEXT,
    bpm INTEGER CHECK (bpm IS NULL OR (bpm >= 40 AND bpm <= 120)),
    instruments_json TEXT,
    playable_status TEXT NOT NULL CHECK (playable_status IN (
        'ready', 'expired', 'quarantined', 'deleted'
    )),
    retention_expires_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CHECK (
        (source_type = 'generated' AND generation_task_id IS NOT NULL)
        OR (source_type != 'generated')
    ),
    UNIQUE (checksum, owner_internal_user_pk)
);

CREATE TABLE IF NOT EXISTS generation_tasks (
    task_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    prescription_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'queued', 'running', 'succeeded', 'matched_fallback', 'failed', 'cancelled'
    )),
    provider TEXT,
    provider_task_id TEXT,
    progress_value INTEGER CHECK (progress_value IS NULL OR (progress_value >= 0 AND progress_value <= 100)),
    progress_indeterminate INTEGER NOT NULL CHECK (progress_indeterminate IN (0, 1)),
    message_code TEXT NOT NULL,
    fallback_applied INTEGER NOT NULL CHECK (fallback_applied IN (0, 1)),
    fallback_reason_code TEXT,
    error_code TEXT,
    music_asset_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    FOREIGN KEY (prescription_id) REFERENCES prescription_v3(prescription_id),
    FOREIGN KEY (music_asset_id) REFERENCES music_assets(music_asset_id),
    UNIQUE (internal_user_pk, idempotency_key),
    CHECK (
        (status = 'succeeded' AND music_asset_id IS NOT NULL AND fallback_applied = 0)
        OR
        (status = 'matched_fallback' AND music_asset_id IS NOT NULL AND fallback_applied = 1)
        OR
        (status IN ('queued', 'running', 'failed', 'cancelled') AND music_asset_id IS NULL)
    )
);
CREATE INDEX IF NOT EXISTS ix_generation_tasks_status_updated
    ON generation_tasks(status, updated_at);
CREATE INDEX IF NOT EXISTS ix_generation_tasks_prescription
    ON generation_tasks(prescription_id);

-- ------------------------------------------------------------
-- 8. Feedback / Preference / Favorite Tables
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback_v3 (
    feedback_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    music_asset_id TEXT NOT NULL,
    change_label TEXT NOT NULL CHECK (change_label IN (
        'much_better', 'slightly_better', 'no_change', 'worse'
    )),
    pre_state_snapshot_json TEXT,
    post_state_json TEXT,
    experience_json TEXT,
    continue_use TEXT CHECK (continue_use IN ('yes', 'maybe', 'no')),
    liked_features_json TEXT NOT NULL,
    adjustment_preferences_json TEXT NOT NULL,
    comment_ciphertext TEXT,
    playback_json TEXT,
    idempotency_key TEXT NOT NULL,
    preference_update_status TEXT NOT NULL CHECK (preference_update_status IN (
        'pending', 'applied', 'failed', 'skipped'
    )),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    FOREIGN KEY (music_asset_id) REFERENCES music_assets(music_asset_id),
    UNIQUE (internal_user_pk, idempotency_key)
);
CREATE INDEX IF NOT EXISTS ix_feedback_v3_user_created
    ON feedback_v3(internal_user_pk, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_feedback_v3_music_asset
    ON feedback_v3(music_asset_id);

CREATE TABLE IF NOT EXISTS user_music_preferences (
    profile_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL UNIQUE,
    current_version_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_music_preference_versions (
    preference_version_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    preferred_bpm_min INTEGER CHECK (preferred_bpm_min IS NULL OR (preferred_bpm_min >= 40 AND preferred_bpm_min <= 120)),
    preferred_bpm_max INTEGER CHECK (preferred_bpm_max IS NULL OR (preferred_bpm_max >= 40 AND preferred_bpm_max <= 120)),
    bpm_weight REAL CHECK (bpm_weight IS NULL OR (bpm_weight >= 0 AND bpm_weight <= 1)),
    preferred_duration_seconds INTEGER CHECK (preferred_duration_seconds IS NULL OR preferred_duration_seconds > 0),
    duration_weight REAL CHECK (duration_weight IS NULL OR (duration_weight >= 0 AND duration_weight <= 1)),
    feedback_count INTEGER NOT NULL DEFAULT 0 CHECK (feedback_count >= 0),
    minimum_samples_for_application INTEGER NOT NULL DEFAULT 3 CHECK (minimum_samples_for_application >= 1),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES user_music_preferences(profile_id) ON DELETE CASCADE,
    UNIQUE (profile_id, version),
    CHECK (
        (preferred_bpm_min IS NULL AND preferred_bpm_max IS NULL)
        OR (preferred_bpm_min IS NOT NULL AND preferred_bpm_max IS NOT NULL AND preferred_bpm_min <= preferred_bpm_max)
    )
);

CREATE TABLE IF NOT EXISTS user_preference_items (
    preference_version_id TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('instrument', 'feature', 'ambient')),
    code TEXT NOT NULL,
    polarity TEXT NOT NULL CHECK (polarity IN ('preferred', 'disliked')),
    weight REAL NOT NULL CHECK (weight >= 0 AND weight <= 1),
    sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (preference_version_id, category, code, polarity),
    FOREIGN KEY (preference_version_id)
        REFERENCES user_music_preference_versions(preference_version_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS preference_events (
    event_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    feedback_id TEXT,
    previous_version_id TEXT,
    new_version_id TEXT,
    patch_json TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES user_music_preferences(profile_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS favorites (
    favorite_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    music_asset_id TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (music_asset_id) REFERENCES music_assets(music_asset_id),
    UNIQUE (internal_user_pk, music_asset_id)
);

COMMIT;
PRAGMA foreign_keys=ON;

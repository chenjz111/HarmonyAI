"""V3 business-table migration semantics (SQLite, file-backed)."""

import pytest
from sqlalchemy import create_engine, inspect, text

from backend.app.core.v3_migrations import apply_v3_migrations


BUSINESS_TABLES = {
    # 4. information understanding
    "understanding_runs",
    "understanding_sources",
    "understanding_revisions",
    "questionnaire_submissions_v3",
    "normalized_facts",
    "fact_source_refs",
    # 5. assessment
    "assessment_v3",
    "assessment_revisions_v3",
    "fact_evidence",
    "organ_evidence",
    # 6. diagnosis / rag
    "diagnosis_runs",
    "diagnosis_candidates",
    "diagnosis_candidate_evidence",
    "knowledge_manifests",
    "knowledge_chunks_v3",
    "rag_retrieval_runs",
    "rag_retrieval_hits",
    "ai_provider_runs",
    # 7. prescription / music
    "prescription_v3",
    "generation_tasks",
    "music_assets",
    # 8. feedback / preference / favorite
    "feedback_v3",
    "user_music_preferences",
    "user_music_preference_versions",
    "user_preference_items",
    "preference_events",
    "favorites",
    # 0003 owner flow amendment (session activity audit)
    "session_input_revisions",
    # 0004 multi-document (document set)
    "document_sets",
    "document_set_items",
    # 0005 document relevance
    "document_relevances",
}


def _create_foundation(engine):
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "openid VARCHAR(128) NOT NULL UNIQUE, nickname VARCHAR(64), "
                "avatar_url TEXT, phone VARCHAR(20), "
                "preferred_instruments TEXT, preferred_bpm_min INTEGER, "
                "preferred_bpm_max INTEGER, preferred_session VARCHAR(32), "
                "effective_syndrome_data TEXT, created_at DATETIME, updated_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE sessions ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
                "session_id VARCHAR(64) NOT NULL UNIQUE, status VARCHAR(16), "
                "current_agent VARCHAR(32), metadata_json TEXT, "
                "created_at DATETIME, updated_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE documents ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
                "session_id VARCHAR(64) NOT NULL, "
                "document_id VARCHAR(64) NOT NULL UNIQUE, "
                "original_filename VARCHAR(256) NOT NULL, "
                "file_type VARCHAR(16) NOT NULL, "
                "file_size_bytes INTEGER NOT NULL, "
                "storage_path VARCHAR(512) NOT NULL, "
                "status VARCHAR(16) DEFAULT 'uploaded', "
                "created_at DATETIME, updated_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users (id, openid) VALUES (1, 'seed:user'), (2, 'seed:user2')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO sessions (id, user_id, session_id, status) "
                "VALUES (1, 1, 'sess_a', 'active'), (2, 1, 'sess_b', 'active')"
            )
        )


def _insert_understanding_run(connection, run_id, user_pk, session_row_id, **overrides):
    values = {
        "understanding_id": run_id,
        "internal_user_pk": user_pk,
        "session_row_id": session_row_id,
        "current_revision": 1,
        "status": "needs_confirmation",
        "safety_status": "pending",
        "degradation_json": "{}",
        **overrides,
    }
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    connection.execute(
        text(f"INSERT INTO understanding_runs ({columns}) VALUES ({placeholders})"),
        values,
    )


def _engine(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'business.db'}")


def test_sqlite_business_migration_is_idempotent_and_registers_all_tables(tmp_path):
    engine = _engine(tmp_path)
    _create_foundation(engine)

    first = apply_v3_migrations(engine)
    second = apply_v3_migrations(engine)

    assert first["applied_versions"] == [
        "0001_v3_foundation",
        "0002_v3_business",
        "0003_v3_owner_flow",
        "0004_v3_multidoc",
        "0005_v3_relevance",
        "0006_v3_doc_fk",
        "0007_v3_prescription_mode",
    ]
    assert second["applied_versions"] == []
    assert second["current_version"] == "0007_v3_prescription_mode"

    tables = set(inspect(engine).get_table_names())
    assert BUSINESS_TABLES <= tables
    with engine.connect() as connection:
        versions = {
            row[0]
            for row in connection.execute(
                text("SELECT version FROM schema_migrations")
            )
        }
    assert versions == {
        "0001_v3_foundation",
        "0002_v3_business",
        "0003_v3_owner_flow",
        "0004_v3_multidoc",
        "0005_v3_relevance",
        "0006_v3_doc_fk",
        "0007_v3_prescription_mode",
    }


def test_understanding_run_cascades_when_user_is_deleted(tmp_path):
    engine = _engine(tmp_path)
    _create_foundation(engine)
    apply_v3_migrations(engine)

    # User 2 owns no sessions (both sessions belong to user 1), so deleting
    # user 2 only exercises the users -> understanding_runs ON DELETE CASCADE.
    with engine.begin() as connection:
        _insert_understanding_run(connection, "und_1", 2, 1)
        connection.execute(
            text(
                "INSERT INTO understanding_sources (source_id, understanding_id, "
                "source_type, processing_status, captured_at) "
                "VALUES ('src_1', 'und_1', 'document', 'ready', '2026-01-01 00:00:00')"
            )
        )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM users WHERE id = 2"))
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM understanding_runs WHERE understanding_id = 'und_1'")
        ).scalar_one() == 0
        assert connection.execute(
            text("SELECT COUNT(*) FROM understanding_sources WHERE understanding_id = 'und_1'")
        ).scalar_one() == 0


def test_normalized_fact_owner_exclusive_check_is_enforced(tmp_path):
    engine = _engine(tmp_path)
    _create_foundation(engine)
    apply_v3_migrations(engine)

    with engine.begin() as connection:
        _insert_understanding_run(connection, "und_1", 1, 1)
        connection.execute(
            text(
                "INSERT INTO understanding_revisions (understanding_id, revision, "
                "status, presentation_json) "
                "VALUES ('und_1', 1, 'needs_confirmation', '{}')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO questionnaire_submissions_v3 ("
                "questionnaire_submission_id, internal_user_pk, session_row_id, "
                "schema_id, schema_version, manifest_version, content_checksum, "
                "time_window_days, answers_json, idempotency_key, submitted_at) "
                "VALUES ('q_1', 1, 1, 'questionnaire_v3', '1.0', 'm1', "
                "'sha256:abc', 7, '{}', 'idem-q1', '2026-01-01 00:00:00')"
            )
        )

    # owner_type=questionnaire but understanding pointers also set -> violation.
    with pytest.raises(Exception):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO normalized_facts (fact_row_id, fact_id, owner_type, "
                    "understanding_id, understanding_revision, "
                    "questionnaire_submission_id, fact_code, category, display_name, "
                    "value_json, time_window, negated, subject, confirmation_status, "
                    "extraction_method, extraction_confidence) "
                    "VALUES ('f1', 'fact_1', 'questionnaire', 'und_1', 1, 'q_1', "
                    "'code', 'sleep', 'F1', '{}', '7d', 0, 'self', 'confirmed', "
                    "'deterministic_questionnaire_mapping', 1.0)"
                )
            )


def _build_diagnosis_chain(connection):
    """Insert the FK chain needed before a generation_task row exists."""
    connection.execute(
        text(
            "INSERT INTO understanding_revisions (understanding_id, revision, "
            "status, presentation_json) "
            "VALUES ('und_1', 1, 'confirmed', '{}')"
        )
    )
    connection.execute(
        text(
            "INSERT INTO assessment_v3 (assessment_id, internal_user_pk, "
            "session_row_id, understanding_id, understanding_revision, "
            "current_revision, status, safety_status, user_goal_json) "
            "VALUES ('a1', 1, 1, 'und_1', 1, 1, 'confirmed', 'passed', '{}')"
        )
    )
    connection.execute(
        text(
            "INSERT INTO assessment_revisions_v3 (assessment_id, revision, "
            "understanding_revision, status, confirmation_status, "
            "state_summary, organ_profile_json, evidence_coverage, "
            "source_diversity, conflicts_json, missing_information_json, "
            "degradation_json, presentation_json) "
            "VALUES ('a1', 1, 1, 'confirmed', 'confirmed', 's', "
            "'{}', 0.8, 2, '[]', '[]', '{}', '{}')"
        )
    )
    connection.execute(
        text(
            "INSERT INTO diagnosis_runs (diagnosis_id, internal_user_pk, "
            "session_row_id, assessment_id, assessment_revision, status, "
            "abstained, degradation_json, presentation_json) "
            "VALUES ('d1', 1, 1, 'a1', 1, 'success', 0, '{}', '{}')"
        )
    )


def test_generation_task_terminal_asset_consistency_is_enforced(tmp_path):
    engine = _engine(tmp_path)
    _create_foundation(engine)
    apply_v3_migrations(engine)

    with engine.begin() as connection:
        _insert_understanding_run(connection, "und_1", 1, 1)
        _build_diagnosis_chain(connection)
        connection.execute(
            text(
                "INSERT INTO prescription_v3 (prescription_id, internal_user_pk, "
                "session_row_id, diagnosis_id, status, generation_spec_json, "
                "personalization_json, presentation_json) "
                "VALUES ('p1', 1, 1, 'd1', 'success', '{}', '{}', '{}')"
            )
        )

    # succeeded without a music_asset violates the terminal consistency check.
    with pytest.raises(Exception):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO generation_tasks (task_id, internal_user_pk, "
                    "session_row_id, prescription_id, idempotency_key, status, "
                    "progress_indeterminate, message_code, fallback_applied) "
                    "VALUES ('t1', 1, 1, 'p1', 'idem-t1', 'succeeded', 0, "
                    "'gen.done', 0)"
                )
            )


def test_music_asset_checksum_and_score01_checks_are_enforced(tmp_path):
    engine = _engine(tmp_path)
    _create_foundation(engine)
    apply_v3_migrations(engine)

    # checksum must be sha256-prefixed.
    with pytest.raises(Exception):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO music_assets (music_asset_id, source_type, title, "
                    "storage_key, format, duration_seconds, checksum, playable_status) "
                    "VALUES ('m1', 'matched', 'T', 'k', 'mp3', 60, 'plainhash', 'ready')"
                )
            )

    # evidence_coverage must be within [0, 1].
    with engine.begin() as connection:
        _insert_understanding_run(connection, "und_1", 1, 1)
        connection.execute(
            text(
                "INSERT INTO understanding_revisions (understanding_id, revision, "
                "status, presentation_json) "
                "VALUES ('und_1', 1, 'needs_confirmation', '{}')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO assessment_v3 (assessment_id, internal_user_pk, "
                "session_row_id, understanding_id, understanding_revision, "
                "current_revision, status, safety_status, user_goal_json) "
                "VALUES ('a1', 1, 1, 'und_1', 1, 1, 'needs_confirmation', "
                "'pending', '{}')"
            )
        )
    with pytest.raises(Exception):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO assessment_revisions_v3 (assessment_id, revision, "
                    "understanding_revision, status, confirmation_status, "
                    "state_summary, organ_profile_json, evidence_coverage, "
                    "source_diversity, conflicts_json, missing_information_json, "
                    "degradation_json, presentation_json) "
                    "VALUES ('a1', 1, 1, 'needs_confirmation', 'unconfirmed', 's', "
                    "'{}', 1.5, 0, '[]', '[]', '{}', '{}')"
                )
            )


def test_owner_flow_null_relaxation_allows_new_flow_rows(tmp_path):
    """0003 relaxes NOT NULL on safety/goal/understanding refs so new
    v3-owner-flow-1 rows may store NULL (deferred_v3 safety, no goal,
    pure-questionnaire) without faking values."""
    engine = _engine(tmp_path)
    _create_foundation(engine)
    apply_v3_migrations(engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO understanding_runs (understanding_id, internal_user_pk, "
                "session_row_id, current_revision, status, safety_status, "
                "flow_contract_version, input_revision, safety_policy, "
                "safety_evaluation_status, degradation_json) "
                "VALUES ('und_null', 1, 1, 1, 'needs_confirmation', NULL, "
                "'v3-owner-flow-1', 2, 'deferred_v3', 'not_run', '{}')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO understanding_revisions (understanding_id, revision, "
                "status, presentation_json) "
                "VALUES ('und_null', 1, 'confirmed', '{}')"
            )
        )
        # New-flow assessment: NULL understanding_id/goal/safety, pure questionnaire.
        connection.execute(
            text(
                "INSERT INTO questionnaire_submissions_v3 ("
                "questionnaire_submission_id, internal_user_pk, session_row_id, "
                "schema_id, schema_version, manifest_version, content_checksum, "
                "time_window_days, answers_json, idempotency_key, submitted_at) "
                "VALUES ('qsub_null', 1, 1, 'questionnaire_v3', '3.0.0', 'm1', "
                "'sha256:null', 7, '[]', 'idem-null', '2026-01-01 00:00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO assessment_v3 (assessment_id, internal_user_pk, "
                "session_row_id, understanding_id, understanding_revision, "
                "questionnaire_submission_id, current_revision, status, "
                "safety_status, user_goal_json, flow_contract_version, "
                "input_revision, input_mode, safety_policy, safety_evaluation_status) "
                "VALUES ('asmt_null', 1, 1, NULL, NULL, 'qsub_null', 1, "
                "'needs_confirmation', NULL, NULL, 'v3-owner-flow-1', 2, "
                "'without_document', 'deferred_v3', 'not_run')"
            )
        )

    # The session_input_revisions audit table is present and enforces its action CHECK.
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO session_input_revisions (session_row_id, input_revision, "
                "input_mode, action) VALUES (1, 3, 'without_document', 'discard_document')"
            )
        )
    with pytest.raises(Exception):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO session_input_revisions (session_row_id, input_revision, "
                    "input_mode, action) VALUES (1, 4, 'with_document', 'bogus_action')"
                )
            )


def test_understanding_run_global_id_uniqueness_across_users(tmp_path):
    engine = _engine(tmp_path)
    _create_foundation(engine)
    apply_v3_migrations(engine)

    with engine.begin() as connection:
        _insert_understanding_run(connection, "und_1", 1, 1)
    with pytest.raises(Exception):
        with engine.begin() as connection:
            _insert_understanding_run(connection, "und_1", 2, 2)

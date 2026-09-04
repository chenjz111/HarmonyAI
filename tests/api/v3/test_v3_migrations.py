from pathlib import Path
import shutil

import pytest
from sqlalchemy import create_engine, inspect, text

from backend.app.core.v3_migrations import (
    MigrationChecksumMismatch,
    V3_MIGRATION_VERSIONS,
    apply_v3_migrations,
    mysql_migration_sql,
    v3_migration_status,
)


def _create_legacy_foundation(engine):
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
                "INSERT INTO sessions (user_id, session_id, status) "
                "VALUES (7, 'sess_legacy', 'active')"
            )
        )


def test_sqlite_v3_migration_is_versioned_idempotent_and_preserves_sessions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'v3.db'}")
    _create_legacy_foundation(engine)

    first = apply_v3_migrations(engine)
    second = apply_v3_migrations(engine)

    assert first["applied_versions"] == [
        "0001_v3_foundation",
        "0002_v3_business",
        "0003_v3_owner_flow",
        "0005_v3_multidoc",
        "0006_v3_relevance",
        "0007_v3_doc_fk",
        "0008_v3_prescription_mode",
    ]
    assert second["applied_versions"] == []
    status = v3_migration_status(engine)
    assert status["applied"] is True
    assert status["foreign_keys_enabled"] is True
    assert status["sessions_user_fk"] is True
    assert status["missing_tables"] == []
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT user_id, session_id, flow_version FROM sessions")
        ).one()
        legacy_demo_user = connection.execute(
            text("SELECT openid FROM users WHERE id = 1")
        ).scalar_one()
    assert row == (7, "sess_legacy", None)
    assert legacy_demo_user == "legacy:demo:v2-default"
    session_indexes = inspect(engine).get_indexes("sessions")
    assert any(
        index["column_names"] == ["user_id", "created_at"]
        for index in session_indexes
    )


def test_owner_goal_migration_is_not_registered_or_present():
    assert "0004_v3_owner_goal" not in V3_MIGRATION_VERSIONS
    migration_root = Path(__file__).parents[3] / "backend" / "migrations" / "v3"
    for dialect in ("sqlite", "mysql"):
        assert not (migration_root / dialect / "0004_v3_owner_goal_up.sql").exists()
        assert not (migration_root / dialect / "0004_v3_owner_goal_down.sql").exists()


def test_applied_v3_migration_checksum_cannot_change(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'checksum.db'}")
    _create_legacy_foundation(engine)
    apply_v3_migrations(engine)

    source = Path(__file__).parents[3] / "backend" / "migrations" / "v3"
    changed = tmp_path / "changed-migrations"
    shutil.copytree(source, changed)
    up = changed / "sqlite" / "0001_v3_foundation_up.sql"
    up.write_text(up.read_text(encoding="utf-8") + "\n-- changed\n", encoding="utf-8")

    with pytest.raises(MigrationChecksumMismatch):
        apply_v3_migrations(engine, migrations_root=changed)


def test_mysql_v3_migration_scripts_have_equivalent_foundation_constraints():
    up, down = mysql_migration_sql()

    assert "CREATE TABLE IF NOT EXISTS user_identities" in up
    assert "CREATE TABLE IF NOT EXISTS user_profiles" in up
    assert "CREATE TABLE IF NOT EXISTS idempotency_records" in up
    assert "FOREIGN KEY (user_id) REFERENCES users(id)" in up
    assert "ADD COLUMN flow_version" in up
    assert "ON sessions(user_id, created_at DESC)" in up
    assert "ENGINE=InnoDB" in up
    assert "DEFAULT CHARSET=utf8mb4" in up
    assert "DROP TABLE" not in up.upper()
    assert "DROP TABLE IF EXISTS user_identities" in down
    assert "DROP INDEX ix_sessions_user_created ON sessions" in down

    # 0002_v3_business tables and constraints are present and ordered.
    for table in (
        "understanding_runs",
        "understanding_sources",
        "understanding_revisions",
        "normalized_facts",
        "fact_source_refs",
        "questionnaire_submissions_v3",
        "assessment_v3",
        "assessment_revisions_v3",
        "fact_evidence",
        "organ_evidence",
        "diagnosis_runs",
        "diagnosis_candidates",
        "diagnosis_candidate_evidence",
        "knowledge_manifests",
        "knowledge_chunks_v3",
        "rag_retrieval_runs",
        "rag_retrieval_hits",
        "ai_provider_runs",
        "prescription_v3",
        "music_assets",
        "generation_tasks",
        "feedback_v3",
        "user_music_preferences",
        "user_music_preference_versions",
        "user_preference_items",
        "preference_events",
        "favorites",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in up
        assert f"DROP TABLE IF EXISTS {table}" in down
    assert up.index("CREATE TABLE IF NOT EXISTS music_assets") < up.index(
        "CREATE TABLE IF NOT EXISTS generation_tasks"
    )
    assert up.index("CREATE TABLE IF NOT EXISTS generation_tasks") < up.index(
        "CREATE TABLE IF NOT EXISTS feedback_v3"
    )
    # Score01 columns use MySQL DECIMAL(6,5).
    assert "evidence_coverage DECIMAL(6,5) NOT NULL" in up
    assert "link_strength DECIMAL(6,5) NOT NULL" in up
    assert "retrieval_score DECIMAL(6,5) NOT NULL" in up
    # Circular music_assets <-> generation_tasks FK is closed via ALTER.
    assert "fk_music_assets_generation_task" in up
    assert "REFERENCES generation_tasks(task_id)" in up

    # 0003_v3_owner_flow: session activity columns, nullable relaxation and
    # the session_input_revisions audit table are present.
    assert "CREATE TABLE IF NOT EXISTS session_input_revisions" in up
    assert "DROP TABLE IF EXISTS session_input_revisions" in down
    assert "ADD COLUMN flow_contract_version" in up
    assert "MODIFY COLUMN user_goal_json JSON NULL" in up
    assert "MODIFY COLUMN safety_status VARCHAR(32) NULL" in up
    assert "MODIFY COLUMN understanding_revision INTEGER NULL" in up


def test_sqlite_foreign_key_enforcement_rejects_new_orphan_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fk.db'}")
    _create_legacy_foundation(engine)
    apply_v3_migrations(engine)

    with pytest.raises(Exception):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO sessions (user_id, session_id, status, flow_version) "
                    "VALUES (999, 'sess_orphan', 'active', 'v3')"
                )
            )

    assert inspect(engine).get_foreign_keys("sessions")


def test_sqlite_v3_identity_constraints_and_cascade_are_enforced(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'constraints.db'}")
    _create_legacy_foundation(engine)
    apply_v3_migrations(engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, openid) "
                "VALUES (20, 'guest:constraint-owner')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO user_identities ("
                "internal_user_pk, public_user_id, auth_type, guest_expires_at"
                ") VALUES (20, 'u_guest_constraint', 'guest', "
                "'2030-01-01 00:00:00')"
            )
        )

    with pytest.raises(Exception):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO user_identities ("
                    "internal_user_pk, public_user_id, auth_type, guest_expires_at"
                    ") VALUES (1, 'u_invalid_registered', 'registered', "
                    "'2030-01-01 00:00:00')"
                )
            )

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM users WHERE id = 20"))
    with engine.connect() as connection:
        remaining = connection.execute(
            text(
                "SELECT COUNT(*) FROM user_identities "
                "WHERE public_user_id = 'u_guest_constraint'"
            )
        ).scalar_one()
    assert remaining == 0

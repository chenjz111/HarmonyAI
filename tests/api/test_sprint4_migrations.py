from sqlalchemy import create_engine, text

from backend.app.core.sprint4_migrations import (
    apply_sprint4_migrations,
    compile_mysql_migrations,
    sprint4_migration_status,
)


def test_sqlite_migration_is_incremental_and_idempotent(tmp_path):
    database = tmp_path / "migration.db"
    engine = create_engine(f"sqlite:///{database}")

    first = apply_sprint4_migrations(engine)
    second = apply_sprint4_migrations(engine)

    assert first["applied"] is True
    assert second["applied"] is True
    assert sprint4_migration_status(engine)["missing_tables"] == []


def test_sqlite_migration_upgrades_partial_schema_without_data_loss(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE ai_call_logs ("
                "id INTEGER PRIMARY KEY, session_id VARCHAR(64) NOT NULL, "
                "provider VARCHAR(32) NOT NULL, call_type VARCHAR(32) NOT NULL, "
                "status VARCHAR(16), input_summary TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO ai_call_logs "
                "(id, session_id, provider, call_type, status, input_summary) "
                "VALUES (1, 'sess_legacy', 'qwen', 'llm_completion', "
                "'success', 'legacy-row')"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE documents ("
                "id INTEGER PRIMARY KEY, document_id VARCHAR(64))"
            )
        )

    result = apply_sprint4_migrations(engine)
    with engine.connect() as connection:
        preserved = connection.execute(
            text("SELECT session_id, input_summary FROM ai_call_logs WHERE id = 1")
        ).one()

    assert result["applied"] is True
    assert preserved == ("sess_legacy", "legacy-row")


def test_mysql_migration_compiles_without_drop_statements():
    ddl = compile_mysql_migrations()
    assert "CREATE TABLE" in ddl
    assert "ai_call_logs" in ddl
    assert "assessment_evidences" in ddl
    assert "DROP TABLE" not in ddl.upper()

"""Versioned Sprint 5 V3 migrations with immutable checksums."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from sqlalchemy import event, inspect
from sqlalchemy.engine import Engine


V3_FOUNDATION_VERSION = "0001_v3_foundation"
V3_MIGRATION_VERSIONS = [
    "0001_v3_foundation",
    "0002_v3_business",
]

_REQUIRED_TABLES = {
    # 0001 foundation
    "user_identities",
    "user_profiles",
    "idempotency_records",
    # 0002 business (information understanding)
    "understanding_runs",
    "understanding_sources",
    "understanding_revisions",
    "normalized_facts",
    "fact_source_refs",
    "questionnaire_submissions_v3",
    # 0002 business (assessment)
    "assessment_v3",
    "assessment_revisions_v3",
    "fact_evidence",
    "organ_evidence",
    # 0002 business (diagnosis / rag)
    "diagnosis_runs",
    "diagnosis_candidates",
    "diagnosis_candidate_evidence",
    "knowledge_manifests",
    "knowledge_chunks_v3",
    "rag_retrieval_runs",
    "rag_retrieval_hits",
    "ai_provider_runs",
    # 0002 business (prescription / music)
    "prescription_v3",
    "generation_tasks",
    "music_assets",
    # 0002 business (feedback / preference / favorite)
    "feedback_v3",
    "user_music_preferences",
    "user_music_preference_versions",
    "user_preference_items",
    "preference_events",
    "favorites",
}


class MigrationChecksumMismatch(RuntimeError):
    """Raised when an already-applied migration file was changed."""


def _default_migrations_root() -> Path:
    return Path(__file__).resolve().parents[2] / "migrations" / "v3"


def _read_migration(
    dialect: str,
    version: str,
    direction: str,
    migrations_root: Path | None = None,
) -> str:
    root = migrations_root or _default_migrations_root()
    path = root / dialect / f"{version}_{direction}.sql"
    return path.read_text(encoding="utf-8")


def _checksum(sql: str) -> str:
    return f"sha256:{sha256(sql.encode('utf-8')).hexdigest()}"


def _remove_marked_block(sql: str, marker: str) -> str:
    begin = f"-- {marker}_BEGIN"
    end = f"-- {marker}_END"
    if sql.count(begin) != 1 or sql.count(end) != 1:
        raise RuntimeError(f"invalid migration marker: {marker}")
    before, remainder = sql.split(begin, 1)
    _, after = remainder.split(end, 1)
    return before + after


def _session_contract(engine: Engine) -> tuple[bool, bool]:
    inspector = inspect(engine)
    if "sessions" not in inspector.get_table_names():
        return False, False
    has_flow_version = "flow_version" in {
        column["name"] for column in inspector.get_columns("sessions")
    }
    has_user_fk = any(
        foreign_key.get("referred_table") == "users"
        and foreign_key.get("constrained_columns") == ["user_id"]
        for foreign_key in inspector.get_foreign_keys("sessions")
    )
    return has_flow_version, has_user_fk


def _has_session_owner_created_index(engine: Engine) -> bool:
    inspector = inspect(engine)
    if "sessions" not in inspector.get_table_names():
        return False
    return any(
        index.get("column_names") == ["user_id", "created_at"]
        for index in inspector.get_indexes("sessions")
    )


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    if getattr(engine, "_harmonyai_v3_fk_listener", False):
        return

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    setattr(engine, "_harmonyai_v3_fk_listener", True)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def _apply_sqlite_migration(
    engine: Engine,
    version: str,
    sql: str,
    checksum: str,
    *,
    session_upgrade: bool,
) -> bool:
    _enable_sqlite_foreign_keys(engine)
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version VARCHAR(64) PRIMARY KEY, "
            "checksum VARCHAR(96) NOT NULL, "
            "applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        row = cursor.execute(
            "SELECT checksum FROM schema_migrations WHERE version = ?",
            (version,),
        ).fetchone()
        if row is not None:
            if row[0] != checksum:
                raise MigrationChecksumMismatch(
                    f"applied migration {version} checksum changed"
                )
            cursor.execute("PRAGMA foreign_keys=ON")
            raw.commit()
            return False

        rendered = sql
        if session_upgrade:
            has_flow_version, has_user_fk = _session_contract(engine)
            rendered = rendered.replace(
                "{{FLOW_VERSION_SELECT}}",
                "flow_version" if has_flow_version else "NULL",
            )
            if has_flow_version and has_user_fk:
                rendered = _remove_marked_block(rendered, "V3_SESSION_UPGRADE")
        raw.executescript(rendered)
        cursor.execute(
            "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)",
            (version, checksum),
        )
        cursor.execute("PRAGMA foreign_keys=ON")
        raw.commit()
        return True
    except Exception:
        raw.rollback()
        try:
            raw.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass
        raise
    finally:
        raw.close()


def _apply_mysql_migration(
    engine: Engine,
    version: str,
    sql: str,
    checksum: str,
    *,
    session_upgrade: bool,
) -> bool:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version VARCHAR(64) PRIMARY KEY, "
            "checksum VARCHAR(96) NOT NULL, "
            "applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6))"
        )
        row = connection.exec_driver_sql(
            "SELECT checksum FROM schema_migrations WHERE version = %s",
            (version,),
        ).first()
        if row is not None:
            if row[0] != checksum:
                raise MigrationChecksumMismatch(
                    f"applied migration {version} checksum changed"
                )
            return False

        rendered = sql
        if session_upgrade:
            has_flow_version, has_user_fk = _session_contract(engine)
            if has_flow_version:
                rendered = _remove_marked_block(rendered, "V3_SESSION_FLOW")
            if has_user_fk:
                rendered = _remove_marked_block(rendered, "V3_SESSION_FK")
            if _has_session_owner_created_index(engine):
                rendered = _remove_marked_block(rendered, "V3_SESSION_OWNER_INDEX")
        statements = [item.strip() for item in rendered.split(";") if item.strip()]
        for statement in statements:
            connection.exec_driver_sql(statement)
        connection.exec_driver_sql(
            "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
            (version, checksum),
        )
        return True


def apply_v3_migrations(
    engine: Engine,
    *,
    migrations_root: Path | None = None,
) -> dict[str, object]:
    """Apply all pending V3 migrations in order and reject changed applied SQL."""

    dialect = engine.dialect.name
    if dialect not in {"sqlite", "mysql"}:
        raise RuntimeError(f"unsupported V3 migration dialect: {dialect}")
    applied: list[str] = []
    last_checksum = ""
    for version in V3_MIGRATION_VERSIONS:
        sql = _read_migration(dialect, version, "up", migrations_root)
        checksum = _checksum(sql)
        last_checksum = checksum
        session_upgrade = version == V3_FOUNDATION_VERSION
        if dialect == "sqlite":
            applied_version = _apply_sqlite_migration(
                engine,
                version,
                sql,
                checksum,
                session_upgrade=session_upgrade,
            )
        else:
            applied_version = _apply_mysql_migration(
                engine,
                version,
                sql,
                checksum,
                session_upgrade=session_upgrade,
            )
        if applied_version:
            applied.append(version)
    return {
        "applied_versions": applied,
        "current_version": V3_MIGRATION_VERSIONS[-1],
        "checksum": last_checksum,
    }


def v3_migration_status(engine: Engine) -> dict[str, object]:
    """Return structural status without exposing connection details."""

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    missing_tables = sorted(_REQUIRED_TABLES - tables)
    has_flow_version, has_user_fk = _session_contract(engine)
    foreign_keys_enabled = True
    if engine.dialect.name == "sqlite":
        with engine.connect() as connection:
            foreign_keys_enabled = bool(
                connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
            )
    return {
        "applied": (
            not missing_tables
            and has_flow_version
            and has_user_fk
            and foreign_keys_enabled
        ),
        "missing_tables": missing_tables,
        "sessions_flow_version": has_flow_version,
        "sessions_user_fk": has_user_fk,
        "foreign_keys_enabled": foreign_keys_enabled,
    }


def mysql_migration_sql(
    migrations_root: Path | None = None,
) -> tuple[str, str]:
    """Expose the concatenated MySQL SQL for credential-free structural validation."""

    up = "\n".join(
        _read_migration("mysql", version, "up", migrations_root)
        for version in V3_MIGRATION_VERSIONS
    )
    down = "\n".join(
        _read_migration("mysql", version, "down", migrations_root)
        for version in reversed(V3_MIGRATION_VERSIONS)
    )
    return up, down

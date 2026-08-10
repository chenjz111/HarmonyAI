"""Incremental, idempotent Sprint 4 database migration helpers."""
from __future__ import annotations

from sqlalchemy import Column, inspect, text
from sqlalchemy.dialects import mysql
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateColumn, CreateTable

from backend.app.models.ai_call_log import AICallLog
from backend.app.models.assessment_evidence import AssessmentEvidence
from backend.app.models.assessment_followup import AssessmentFollowUp
from backend.app.models.assessment_revision import AssessmentRevision
from backend.app.models.document import Document


SPRINT4_TABLES = (
    AICallLog.__table__,
    AssessmentEvidence.__table__,
    AssessmentFollowUp.__table__,
    AssessmentRevision.__table__,
)
DOCUMENT_EXTENSION_COLUMNS = (
    "ocr_provider",
    "ocr_error_code",
    "ocr_result_json",
    "ocr_processing_time_ms",
)


def _required_columns() -> dict[str, set[str]]:
    required = {
        table.name: set(table.columns.keys())
        for table in SPRINT4_TABLES
    }
    required[Document.__tablename__] = set(DOCUMENT_EXTENSION_COLUMNS)
    return required


def sprint4_migration_status(engine: Engine) -> dict[str, object]:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing_tables = [
        table.name for table in SPRINT4_TABLES
        if table.name not in existing_tables
    ]
    missing_columns: dict[str, list[str]] = {}
    for table_name, required in _required_columns().items():
        if table_name not in existing_tables:
            continue
        existing = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        missing = sorted(required - existing)
        if missing:
            missing_columns[table_name] = missing
    return {
        "applied": not missing_tables and not missing_columns,
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
    }


def _portable_add_column(column: Column, dialect) -> str:
    migration_column = Column(column.name, column.type, nullable=True)
    return str(CreateColumn(migration_column).compile(dialect=dialect))


def apply_sprint4_migrations(engine: Engine) -> dict[str, object]:
    """Create missing tables/columns without deleting Sprint 3 data."""
    with engine.begin() as connection:
        existing = set(inspect(connection).get_table_names())
        for table in SPRINT4_TABLES:
            if table.name not in existing:
                table.create(connection, checkfirst=True)

        inspector = inspect(connection)
        existing = set(inspector.get_table_names())
        table_by_name = {
            table.name: table
            for table in (*SPRINT4_TABLES, Document.__table__)
        }
        for table_name, required in _required_columns().items():
            if table_name not in existing:
                if table_name == Document.__tablename__:
                    Document.__table__.create(connection, checkfirst=True)
                continue
            present = {
                column["name"]
                for column in inspector.get_columns(table_name)
            }
            for column_name in sorted(required - present):
                column = table_by_name[table_name].columns[column_name]
                ddl = _portable_add_column(column, connection.dialect)
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}")
                )

    return sprint4_migration_status(engine)


def compile_mysql_migrations() -> str:
    """Compile the same models for MySQL 8 without connecting to a server."""
    dialect = mysql.dialect()
    return "\n\n".join(
        str(CreateTable(table, if_not_exists=True).compile(dialect=dialect))
        for table in SPRINT4_TABLES
    )

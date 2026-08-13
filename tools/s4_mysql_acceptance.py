"""Non-destructive MySQL acceptance probe for the isolated Sprint 4 database."""
from __future__ import annotations

import json
import os
import sys
import uuid

from sqlalchemy.engine import URL, make_url


ACCEPTANCE_DATABASE = "harmonyai_s4_acceptance"


def validate_acceptance_database_url(value: str) -> URL:
    """Accept only a MySQL URL targeting the explicitly isolated test database."""
    try:
        parsed = make_url(value)
    except Exception as exc:
        raise ValueError("DATABASE_URL must be a valid MySQL URL") from exc
    if parsed.get_backend_name() != "mysql":
        raise ValueError("DATABASE_URL must use MySQL")
    if parsed.database != ACCEPTANCE_DATABASE:
        raise ValueError(
            f"DATABASE_URL must target the isolated {ACCEPTANCE_DATABASE} database"
        )
    return parsed


def run_acceptance(database_url: URL) -> dict[str, object]:
    """Verify migrations, persistence, privacy hooks, and scoped cleanup."""
    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import sessionmaker

    from backend.app.core.database import Base
    from backend.app.core.sprint4_migrations import (
        apply_sprint4_migrations,
        sprint4_migration_status,
    )
    from backend.app.models import (
        AICallLog,
        AssessmentEvidence,
        AssessmentFollowUp,
        AssessmentRevision,
        Feedback,
        Session,
    )

    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    first_migration = apply_sprint4_migrations(engine)
    second_migration = apply_sprint4_migrations(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    tracked = (
        Session,
        AssessmentRevision,
        AssessmentEvidence,
        AssessmentFollowUp,
        Feedback,
        AICallLog,
    )
    with session_factory() as db:
        baseline = {
            model.__tablename__: db.scalar(select(func.count()).select_from(model))
            for model in tracked
        }

    token = uuid.uuid4().hex
    session_id = f"s4_acceptance_{token}"
    ids = {
        "revision": f"rev_{token}",
        "evidence": f"evi_{token}",
        "followup": f"fu_{token}",
        "feedback": f"fb_{token}",
        "request": f"req_{token}",
    }
    inserted = False
    try:
        with session_factory() as db:
            db.add_all(
                [
                    Session(user_id=0, session_id=session_id, status="active"),
                    AssessmentRevision(
                        session_id=session_id,
                        assessment_id=f"asmt_{token}",
                        revision_id=ids["revision"],
                        revision=1,
                        field_changed="acceptance_probe",
                        new_value="verified",
                        source="user_confirmation",
                    ),
                    AssessmentEvidence(
                        session_id=session_id,
                        evidence_id=ids["evidence"],
                        source="questionnaire",
                        category="emotion",
                        content="acceptance probe",
                        confidence=1.0,
                        source_type="questionnaire",
                        confirmed=True,
                    ),
                    AssessmentFollowUp(
                        session_id=session_id,
                        assessment_id=f"asmt_{token}",
                        followup_id=ids["followup"],
                        question="acceptance probe",
                        category="clarification",
                        status="answered",
                        answer="verified",
                        revision_submitted=1,
                    ),
                    Feedback(
                        user_id=0,
                        session_id=session_id,
                        feedback_id=ids["feedback"],
                        decision_action="continue",
                        confidence=1.0,
                        global_rules_modified=0,
                    ),
                    AICallLog(
                        request_id=ids["request"],
                        session_id=session_id,
                        agent_id="acceptance_probe",
                        provider="manual",
                        status="success",
                        input_summary="must be cleared",
                        output_summary="must be cleared",
                        error="must be cleared",
                    ),
                ]
            )
            db.commit()
            inserted = True

        engine.dispose()
        engine = create_engine(database_url, pool_pre_ping=True)
        session_factory.configure(bind=engine)
        with session_factory() as db:
            persisted = all(
                db.scalar(
                    select(func.count()).select_from(model).where(
                        model.session_id == session_id
                    )
                )
                == 1
                for model in tracked
            )
            log_row = db.scalar(
                select(AICallLog).where(AICallLog.request_id == ids["request"])
            )
            privacy_ok = bool(
                log_row
                and log_row.input_summary is None
                and log_row.output_summary is None
                and log_row.error is None
            )
            migration_ok = bool(sprint4_migration_status(engine)["applied"])
    finally:
        if inserted:
            with session_factory() as db:
                for model in reversed(tracked):
                    rows = db.scalars(
                        select(model).where(model.session_id == session_id)
                    ).all()
                    for row in rows:
                        db.delete(row)
                db.commit()

    with session_factory() as db:
        cleanup_ok = all(
            db.scalar(select(func.count()).select_from(model))
            == baseline[model.__tablename__]
            for model in tracked
        )
    engine.dispose()
    return {
        "database": ACCEPTANCE_DATABASE,
        "migration_first_applied": bool(first_migration["applied"]),
        "migration_idempotent": bool(second_migration["applied"]),
        "persistence": persisted,
        "privacy_log": privacy_ok,
        "cleanup": cleanup_ok,
        "pass": all((migration_ok, persisted, privacy_ok, cleanup_ok)),
    }


def main() -> int:
    raw_url = os.environ.get("DATABASE_URL", "")
    if not raw_url:
        print("MYSQL_ACCEPTANCE: USER_CREDENTIAL_REQUIRED")
        print("Set DATABASE_URL locally; do not paste credentials into chat or Git.")
        return 2
    try:
        database_url = validate_acceptance_database_url(raw_url)
    except ValueError as exc:
        print(f"MYSQL_ACCEPTANCE: REFUSED - {exc}")
        return 2
    try:
        result = run_acceptance(database_url)
    except Exception as exc:
        print(f"MYSQL_ACCEPTANCE: FAIL ({type(exc).__name__})")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

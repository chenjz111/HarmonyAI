from backend.app.core.logging_config import sanitize_log
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.models.ai_call_log import AICallLog


def test_ai_call_log_exposes_all_frozen_metadata_fields():
    assert {
        "id",
        "request_id",
        "session_id",
        "agent_id",
        "source_type",
        "text_length",
        "provider",
        "model",
        "prompt_version",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "retry_count",
        "status",
        "error_code",
        "created_at",
    }.issubset(AICallLog.__table__.columns.keys())


def test_legacy_log_fields_cannot_persist_user_text():
    engine = create_engine("sqlite://")
    AICallLog.__table__.create(engine)
    with Session(engine) as session:
        session.add(
            AICallLog(
                request_id="req_private",
                session_id="sess_private",
                agent_id="assessment_agent",
                provider="qwen",
                status="failed",
                input_summary="病例输入原文",
                output_summary="模型输出原文",
                error="provider echoed user text",
                error_code="INVALID_RESPONSE",
            )
        )
        session.commit()

    with Session(engine) as session:
        stored = session.scalar(select(AICallLog))
        assert stored.input_summary is None
        assert stored.output_summary is None
        assert stored.error is None
        assert stored.error_code == "INVALID_RESPONSE"


def test_log_sanitizer_never_returns_raw_string_or_nested_user_text():
    assert sanitize_log("病例原文") == "[REDACTED]"
    sanitized = sanitize_log(
        {
            "session_id": "sess_safe",
            "narrative_text": "我最近睡不着",
            "nested": {"document_text": "医生记录原文"},
        }
    )
    assert "我最近睡不着" not in sanitized
    assert "医生记录原文" not in sanitized
    assert "sess_safe" in sanitized

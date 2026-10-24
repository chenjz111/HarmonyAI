"""AI call log — Sprint 4: records every LLM/OCR/Provider call for audit."""
import re

from sqlalchemy import Column, DateTime, Integer, String, Text, event
from sqlalchemy.sql import func
from backend.app.core.database import Base


class AICallLog(Base):
    __tablename__ = "ai_call_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), nullable=False, unique=True)
    session_id = Column(String(64), nullable=False, index=True)
    agent_id = Column(String(32), nullable=False)
    source_type = Column(String(32), nullable=True)
    text_length = Column(Integer, nullable=True)
    provider = Column(String(32), nullable=False, comment="qwen/paddleocr/skymusic")
    model = Column(String(64), nullable=True)
    prompt_version = Column(String(64), nullable=True)
    call_type = Column(
        String(32),
        nullable=True,
        comment="Legacy metadata; use agent_id/source_type for Sprint 4",
    )
    status = Column(String(16), default="success", comment="success/degraded/failed")
    # Retained only so an incremental migration can clear old rows safely.
    # ORM hooks below guarantee these columns cannot receive new user text.
    input_summary = Column(Text, nullable=True, comment="Sanitzed input (no full text)")
    output_summary = Column(Text, nullable=True, comment="Sanitized output summary")
    latency_ms = Column(Integer, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    error_code = Column(String(64), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


_SAFE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


@event.listens_for(AICallLog, "before_insert")
@event.listens_for(AICallLog, "before_update")
def _strip_user_text_from_ordinary_log(_mapper, _connection, target):
    target.input_summary = None
    target.output_summary = None
    target.error = None
    if target.error_code and not _SAFE_ERROR_CODE.fullmatch(target.error_code):
        target.error_code = "PROVIDER_ERROR"

"""AI call log — Sprint 4: records every LLM/OCR/Provider call for audit."""
from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from sqlalchemy.sql import func
from backend.app.core.database import Base


class AICallLog(Base):
    __tablename__ = "ai_call_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    provider = Column(String(32), nullable=False, comment="qwen/paddleocr/skymusic")
    call_type = Column(String(32), nullable=False, comment="llm_completion/ocr/image_generation")
    status = Column(String(16), default="success", comment="success/degraded/failed")
    input_summary = Column(Text, nullable=True, comment="Sanitzed input (no full text)")
    output_summary = Column(Text, nullable=True, comment="Sanitized output summary")
    latency_ms = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

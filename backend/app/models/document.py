"""Document model — stores uploaded case materials (JPG/PNG/PDF).

Sprint 3 Issue #36: file metadata only, not the file content.
"""
from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.sql import func

from backend.app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)

    # File info
    document_id = Column(String(64), unique=True, nullable=False, comment="doc_YYYYMMDD_NNN")
    original_filename = Column(String(256), nullable=False, comment="用户上传的原始文件名")
    file_type = Column(String(16), nullable=False, comment="jpg / png / pdf")
    file_size_bytes = Column(Integer, nullable=False, comment="文件大小(字节)")
    page_count = Column(Integer, nullable=True, default=1, comment="PDF页数(仅PDF)")

    # Storage (relative or cloud path — NEVER local absolute path)
    storage_path = Column(String(512), nullable=False, comment="存储路径(相对/云端)")

    # Processing status
    status = Column(String(16), default="uploaded", comment="uploaded/confirmed/skipped/deleted/ocr_failed")
    ocr_text = Column(Text, nullable=True, comment="OCR识别文本(未确认前不可靠)")
    ocr_confidence = Column(String(16), nullable=True, comment="OCR置信度: high/medium/low (always string, never float)")
    ocr_provider = Column(String(32), nullable=True)
    ocr_error_code = Column(String(64), nullable=True)
    ocr_result_json = Column(JSON, nullable=True)
    ocr_processing_time_ms = Column(Integer, nullable=True)
    ocr_confirmed = Column(Boolean, default=False, comment="用户是否确认OCR文本")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Document(id={self.id}, doc_id={self.document_id}, status={self.status})>"

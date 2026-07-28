"""Document upload schemas — Sprint 3 Issue #36."""
from __future__ import annotations
from typing import Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator


ALLOWED_TYPES = {"image/jpeg", "image/png", "application/pdf"}
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}
MAX_FILE_SIZE_MB = 10
MAX_PDF_PAGES = 50


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    CONFIRMED = "confirmed"
    SKIPPED = "skipped"
    DELETED = "deleted"
    OCR_FAILED = "ocr_failed"


class DocumentUploadRequest(BaseModel):
    """Request to upload a document (metadata only — file handled by frontend/CDN)."""
    session_id: str = Field(..., description="会话ID")
    user_id: str = Field(default="u_001")
    original_filename: str = Field(..., description="原始文件名")
    file_type: str = Field(..., description="jpg / png / pdf")
    file_size_bytes: int = Field(..., gt=0)
    page_count: int = Field(default=1, ge=1, le=50)
    storage_path: str = Field(..., description="云存储路径(相对路径)")

    @field_validator("file_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ALLOWED_EXTENSIONS:
            raise ValueError(f"不支持的文件类型: {v}。允许: {ALLOWED_EXTENSIONS}")
        return v

    @field_validator("file_size_bytes")
    @classmethod
    def validate_size(cls, v: int) -> int:
        if v > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"文件太大，最大 {MAX_FILE_SIZE_MB}MB")
        return v


class DocumentResponse(BaseModel):
    """Response after document upload/query."""
    document_id: str
    session_id: str
    original_filename: str
    file_type: str
    file_size_bytes: int
    page_count: int = 1
    status: DocumentStatus = DocumentStatus.UPLOADED
    ocr_text: Optional[str] = None
    ocr_confidence: Optional[str] = None
    ocr_confirmed: bool = False
    created_at: Optional[datetime] = None


class DocumentConfirmRequest(BaseModel):
    """Confirm or skip a document."""
    session_id: str
    document_id: str
    action: str = Field(..., description="confirm / skip / delete")
    ocr_text: Optional[str] = None  # user manually corrected OCR text


class DocumentListResponse(BaseModel):
    """All documents for a session."""
    session_id: str
    documents: list[DocumentResponse]
    total: int

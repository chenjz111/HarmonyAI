"""Document Router V2 — Sprint 3 per api-contract-v2.md.

POST   /api/v2/documents                          — multipart upload
PATCH  /api/v2/documents/{document_id}/confirmation — confirm/skip
DELETE /api/v2/documents/{document_id}             — delete
GET    /api/v2/documents/{session_id}              — list by session
"""
from datetime import datetime, timezone
from dataclasses import asdict
import io
import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pypdf import PdfReader
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.document import Document
from backend.app.models.session import Session as SessionModel
from backend.app.schemas.v2 import DocumentConfirmationRequest
from backend.app.schemas.v2 import v2_ok, v2_err

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_MIME = {"image/jpeg", "image/png", "application/pdf"}
ALLOWED_SIGNATURES = {
    "jpg": b"\xff\xd8\xff",
    "jpeg": b"\xff\xd8\xff",
    "png": b"\x89PNG\r\n\x1a\n",
    "pdf": b"%PDF",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_PDF_PAGES = 3
UPLOAD_DIR = "uploads"


def _ensure_session(session_id: str, db: Session):
    existing = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
    if not existing:
        db.add(SessionModel(user_id=1, session_id=session_id, status="active",
                           current_agent="document_upload"))
        db.commit()


def _check_file_signature(content: bytes, ext: str) -> bool:
    """Verify file header matches extension. Fixes Review issue #4."""
    expected = ALLOWED_SIGNATURES.get(ext)
    if not expected:
        return False
    return content[:len(expected)] == expected


def _inspect_pdf(content: bytes) -> tuple[int, bool]:
    """Return page count and encryption status using a real PDF parser."""
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
        if reader.is_encrypted:
            return 0, True
        return len(reader.pages), False
    except Exception as exc:
        raise ValueError("invalid PDF") from exc


@router.post("/documents", summary="V2 — 上传病例材料 (multipart/form-data)")
async def upload_document(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    document_type: str = Form(default="other"),
    consent_confirmed: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    req_id = f"req_{datetime.now(timezone.utc).strftime('%H%M%S')}_{uuid.uuid4().hex[:4]}"

    if not consent_confirmed:
        return v2_err("CONSENT_REQUIRED", "请先确认隐私授权后再上传", req_id, retryable=False,
                       next_actions=["confirm_consent"])

    ext = (file.filename or "").split(".")[-1].lower()
    if ext not in {"jpg", "jpeg", "png", "pdf"}:
        return v2_err("INVALID_EXTENSION", f"不允许: .{ext}", req_id, retryable=False)

    if file.content_type not in ALLOWED_MIME:
        return v2_err("INVALID_FILE_TYPE", f"不支持: {file.content_type}", req_id, retryable=False,
                       next_actions=["retry_with_valid_file"])

    try:
        content = await file.read()
    except Exception:
        return v2_err("FILE_READ_ERROR", "无法读取文件", req_id, retryable=False)

    file_size = len(content)
    if file_size > MAX_FILE_SIZE:
        return v2_err("FILE_TOO_LARGE", f"最大10MB，当前{file_size}bytes", req_id, retryable=False)

    # File signature check (fixes Review issue #4)
    if not _check_file_signature(content, ext):
        return v2_err("INVALID_SIGNATURE", "文件签名不匹配，可能为伪造文件", req_id, retryable=False)

    # PDF page count (fixes Review issue #3)
    page_count = 1
    if ext == "pdf":
        try:
            page_count, encrypted = _inspect_pdf(content)
        except ValueError:
            return v2_err(
                "INVALID_PDF",
                "PDF 文件损坏或格式无效",
                req_id,
                retryable=False,
            )
        if encrypted:
            return v2_err(
                "ENCRYPTED_PDF",
                "PDF 已加密，请上传未加密文件",
                req_id,
                retryable=False,
                next_actions=["retry_with_unencrypted_file", "skip_document"],
            )
        if page_count > MAX_PDF_PAGES:
            return v2_err("PDF_TOO_LONG", f"PDF最多{MAX_PDF_PAGES}页，当前{page_count}页", req_id, retryable=False)

    # Save file to disk (fixes Review issue #2)
    doc_id = f"doc_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}.{ext}")
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        _ensure_session(session_id, db)

        # Real OCR (Sprint 4)
        from backend.app.core.ocr import OCRProvider
        ocr = OCRProvider()
        ocr_result = ocr.process(file_path, ext)

        # OCR failure → degraded, not fake success
        ocr_status = "confirmed" if ocr_result.confidence in ("high", "medium") else (
            "needs_confirmation" if ocr_result.confidence == "low" else "degraded"
        )
        if ocr_result.degraded or ocr_result.confidence == "failed":
            ocr_status = (
                "degraded"
                if ocr_result.error_code == "OCR_ENGINE_UNAVAILABLE"
                else "failed"
            )

        doc = Document(
            user_id=1, session_id=session_id, document_id=doc_id,
            original_filename=file.filename or "unknown",
            file_type=ext, file_size_bytes=file_size,
            page_count=page_count,
            storage_path=file_path,
            status="uploaded",
            ocr_text=ocr_result.text or None,
            ocr_confidence=ocr_result.confidence,
            ocr_provider=ocr_result.provider,
            ocr_error_code=ocr_result.error_code,
            ocr_result_json={
                "page_results": [
                    asdict(page) for page in ocr_result.page_results
                ],
                "average_confidence": ocr_result.average_confidence,
                "engine_version": ocr_result.engine_version,
            },
            ocr_processing_time_ms=ocr_result.processing_time_ms,
            ocr_confirmed=False,
        )
        db.add(doc)
        db.commit()

        warnings = []
        if ocr_result.degraded:
            warnings.append(f"OCR降级: {ocr_result.error or 'paddleocr_not_available'}")
        if ocr_result.encrypted:
            warnings.append("PDF已加密，无法提取文本")
        if ocr_status == "needs_confirmation":
            warnings.append("请确认识别文本")

        return v2_ok({
            "document_id": doc_id,
            "session_id": session_id,
            "file": {"name": file.filename, "media_type": file.content_type,
                     "size_bytes": file_size, "page_count": page_count,
                     "encrypted": ocr_result.encrypted},
            "ocr_status": ocr_status,
            "ocr_confidence": ocr_result.confidence,
            "ocr_provider": ocr_result.provider,
            "extracted_text": ocr_result.text or None,
            "page_confidences": ocr_result.page_confidences,
            "page_results": [
                asdict(page) for page in ocr_result.page_results
            ],
            "average_confidence": ocr_result.average_confidence,
            "engine_version": ocr_result.engine_version,
            "processing_time_ms": ocr_result.processing_time_ms,
            "warnings": warnings,
            "degradation": {
                "triggered": ocr_result.degraded,
                "reason_code": ocr_result.error_code,
                "message": ocr_result.user_message,
                "fallback": "manual_or_skip" if ocr_result.degraded else None,
            },
            "next_actions": list(ocr_result.next_actions),
            "retention": "temporary",
            "document_type": document_type,
        }, req_id)

    except Exception:
        db.rollback()
        # Clean up file on DB failure
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.exception(
            "document upload failed",
            extra={"session_id": session_id, "document_id": doc_id},
        )
        return v2_err(
            "UPLOAD_FAILED",
            "材料上传失败，请稍后重试",
            req_id,
            retryable=True,
            next_actions=["retry_upload", "skip_document"],
        )


@router.patch("/documents/{document_id}/confirmation", summary="V2 — 确认/跳过文档")
async def confirm_document(
    document_id: str,
    body: DocumentConfirmationRequest,
    db: Session = Depends(get_db),
):
    req_id = f"req_{datetime.now(timezone.utc).strftime('%H%M%S')}_{uuid.uuid4().hex[:4]}"
    doc = db.query(Document).filter(
        Document.document_id == document_id,
        Document.session_id == body.session_id,
    ).first()
    if not doc:
        return v2_err("NOT_FOUND", f"文档{document_id}不存在", req_id, retryable=False)

    try:
        confirmed_at = None
        if body.confirmed:
            doc.status = "confirmed"
            doc.ocr_confirmed = True
            doc.ocr_text = body.document_text
            confirmed_at = datetime.now(timezone.utc)
            doc.updated_at = confirmed_at
        else:
            doc.status = "skipped"
            doc.ocr_confirmed = False
        db.commit()
        return v2_ok({"document_id": document_id, "ocr_status": doc.status,
                       "document_text": doc.ocr_text,
                       "confirmed_at": confirmed_at.isoformat() if confirmed_at else None}, req_id)
    except Exception:
        db.rollback()
        logger.exception(
            "document confirmation failed",
            extra={"document_id": document_id},
        )
        return v2_err(
            "CONFIRM_FAILED",
            "材料确认失败，请稍后重试",
            req_id,
            retryable=True,
            next_actions=["retry_confirmation", "skip_document"],
        )


@router.delete("/documents/{document_id}", summary="V2 — 删除文档")
async def delete_document(document_id: str, db: Session = Depends(get_db)):
    req_id = f"req_{datetime.now(timezone.utc).strftime('%H%M%S')}_{uuid.uuid4().hex[:4]}"
    doc = db.query(Document).filter(Document.document_id == document_id).first()
    if not doc:
        return v2_err("NOT_FOUND", f"文档{document_id}不存在", req_id, retryable=False)
    try:
        doc.status = "deleted"
        # Clean up file
        if doc.storage_path and os.path.exists(doc.storage_path):
            os.remove(doc.storage_path)
        db.commit()
        return v2_ok({"document_id": document_id, "status": "deleted"}, req_id)
    except Exception:
        db.rollback()
        logger.exception(
            "document deletion failed",
            extra={"document_id": document_id},
        )
        return v2_err(
            "DELETE_FAILED",
            "材料删除失败，请稍后重试",
            req_id,
            retryable=True,
            next_actions=["retry_delete"],
        )


@router.get("/documents/{session_id}", summary="V2 — 查询Session文档")
async def list_documents(session_id: str, db: Session = Depends(get_db)):
    req_id = f"req_{datetime.now(timezone.utc).strftime('%H%M%S')}_{uuid.uuid4().hex[:4]}"
    docs = db.query(Document).filter(
        Document.session_id == session_id, Document.status != "deleted"
    ).all()
    items = [{
        "document_id": d.document_id, "filename": d.original_filename,
        "file_type": d.file_type, "status": d.status,
        "ocr_confirmed": d.ocr_confirmed,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    } for d in docs]
    return v2_ok({"session_id": session_id, "documents": items, "total": len(items)}, req_id)

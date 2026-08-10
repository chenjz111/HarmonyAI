"""Document Router V2 — Sprint 3 per api-contract-v2.md.

POST   /api/v2/documents                          — multipart upload
PATCH  /api/v2/documents/{document_id}/confirmation — confirm/skip
DELETE /api/v2/documents/{document_id}             — delete
GET    /api/v2/documents/{session_id}              — list by session
"""
from datetime import datetime, timezone
import os
import uuid
import traceback

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.document import Document
from backend.app.models.session import Session as SessionModel
from backend.app.schemas.v2 import v2_ok, v2_err

router = APIRouter()

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


def _count_pdf_pages(content: bytes) -> int:
    """Count PDF pages by scanning for page objects. Stub fallback: returns 1."""
    try:
        text = content.decode("latin-1", errors="ignore")
        return max(1, text.count("/Type /Page") - text.count("/Type /Pages"))
    except Exception:
        return 1


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
    page_count = _count_pdf_pages(content) if ext == "pdf" else 1
    if ext == "pdf" and page_count > MAX_PDF_PAGES:
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
            ocr_status = "degraded"

        doc = Document(
            user_id=1, session_id=session_id, document_id=doc_id,
            original_filename=file.filename or "unknown",
            file_type=ext, file_size_bytes=file_size,
            page_count=page_count,
            storage_path=file_path,
            status="uploaded",
            ocr_text=ocr_result.text or None,
            ocr_confidence=ocr_result.confidence,
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
            "warnings": warnings,
            "retention": "temporary",
            "document_type": document_type,
        }, req_id)

    except Exception as e:
        db.rollback()
        # Clean up file on DB failure
        if os.path.exists(file_path):
            os.remove(file_path)
        return v2_err("UPLOAD_FAILED", str(e), req_id, retryable=True)


@router.patch("/documents/{document_id}/confirmation", summary="V2 — 确认/跳过文档")
async def confirm_document(
    document_id: str, body: dict, db: Session = Depends(get_db),
):
    req_id = f"req_{datetime.now(timezone.utc).strftime('%H%M%S')}_{uuid.uuid4().hex[:4]}"
    doc = db.query(Document).filter(Document.document_id == document_id).first()
    if not doc:
        return v2_err("NOT_FOUND", f"文档{document_id}不存在", req_id, retryable=False)

    try:
        confirmed = body.get("confirmed", False)
        if confirmed:
            doc.status = "confirmed"
            doc.ocr_confirmed = True
            if body.get("document_text"):
                doc.ocr_text = body["document_text"]
        else:
            doc.status = "skipped"
            doc.ocr_confirmed = False
        db.commit()
        return v2_ok({"document_id": document_id, "ocr_status": doc.status,
                       "document_text": doc.ocr_text}, req_id)
    except Exception as e:
        db.rollback()
        return v2_err("CONFIRM_FAILED", str(e), req_id, retryable=True)


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
    except Exception as e:
        db.rollback()
        return v2_err("DELETE_FAILED", str(e), req_id, retryable=True)


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

"""Document Router V2 — Sprint 3 per api-contract-v2.md.

POST   /api/v2/documents                          — multipart upload
PATCH  /api/v2/documents/{document_id}/confirmation — confirm/skip
GET    /api/v2/documents/{session_id}              — list by session
"""
from datetime import datetime, timezone
import traceback

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.document import Document
from backend.app.models.session import Session as SessionModel
from backend.app.schemas.v2 import v2_ok, v2_err
from backend.app.core.ocr import OCRProvider

router = APIRouter()
ocr = OCRProvider()

ALLOWED_MIME = {"image/jpeg", "image/png", "application/pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_PDF_PAGES = 3


def _ensure_session(session_id: str, db: Session):
    existing = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
    if not existing:
        db.add(SessionModel(user_id=1, session_id=session_id, status="active",
                           current_agent="document_upload"))
        db.commit()


@router.post("/documents", summary="V2 — 上传病例材料 (multipart/form-data)")
async def upload_document(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    document_type: str = Form(default="other"),
    consent_confirmed: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    req_id = f"req_{datetime.now(timezone.utc).strftime('%H%M%S')}"

    # Consent check
    if not consent_confirmed:
        return v2_err("CONSENT_REQUIRED", "请先确认隐私授权后再上传", req_id, retryable=False,
                       next_actions=["confirm_consent"])

    # MIME validation
    if file.content_type not in ALLOWED_MIME:
        return v2_err("INVALID_FILE_TYPE",
                       f"不支持的文件类型: {file.content_type}。仅支持 JPG/PNG/PDF", req_id,
                       retryable=False, next_actions=["retry_with_valid_file"])

    # Read file
    try:
        content = await file.read()
    except Exception:
        return v2_err("FILE_READ_ERROR", "无法读取文件", req_id, retryable=False)

    file_size = len(content)
    if file_size > MAX_FILE_SIZE:
        return v2_err("FILE_TOO_LARGE", f"文件太大({file_size}bytes)，最大10MB", req_id,
                       retryable=False, next_actions=["compress_or_split"])

    file_ext = file.filename.split(".")[-1].lower() if file.filename else "bin"
    if file_ext not in {"jpg", "jpeg", "png", "pdf"}:
        return v2_err("INVALID_EXTENSION", f"不允许的扩展名: .{file_ext}", req_id,
                       retryable=False)

    page_count = 1
    if file_ext == "pdf":
        # Stub: set page_count to 1 (no real PDF parsing)
        page_count = 1
        if page_count > MAX_PDF_PAGES:
            return v2_err("PDF_TOO_LONG", f"PDF最多{MAX_PDF_PAGES}页", req_id,
                           retryable=False, next_actions=["split_pdf"])

    try:
        _ensure_session(session_id, db)

        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        ts = datetime.now(timezone.utc).strftime("%H%M%S")
        doc_id = f"doc_{today_str}_{ts}"

        # OCR processing
        ocr_result = ocr.process(f"uploads/{session_id}/{file.filename}", file_ext)

        doc = Document(
            user_id=1, session_id=session_id,
            document_id=doc_id,
            original_filename=file.filename or "unknown",
            file_type=file_ext,
            file_size_bytes=file_size,
            page_count=page_count,
            storage_path=f"uploads/{session_id}/{doc_id}.{file_ext}",
            status="uploaded",
            ocr_text=ocr_result.text,
            ocr_confidence=ocr_result.confidence,
            ocr_confirmed=False,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        return v2_ok({
            "document_id": doc_id,
            "session_id": session_id,
            "file": {
                "name": file.filename,
                "media_type": file.content_type,
                "size_bytes": file_size,
                "page_count": page_count,
            },
            "ocr_status": "needs_confirmation",
            "extracted_text": ocr_result.text,
            "warnings": ["请确认识别文本，未确认的数据不作为可靠输入。"],
            "retention": "temporary",
        }, req_id)

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        return v2_err("UPLOAD_FAILED", f"上传失败: {e}", req_id, retryable=True,
                       next_actions=["retry"])


@router.patch("/documents/{document_id}/confirmation", summary="V2 — 确认/跳过文档")
async def confirm_document_v2(
    document_id: str,
    body: dict,
    db: Session = Depends(get_db),
):
    req_id = f"req_{datetime.now(timezone.utc).strftime('%H%M%S')}"
    session_id = body.get("session_id", "")
    confirmed = body.get("confirmed", False)
    doc_text = body.get("document_text")

    doc = db.query(Document).filter(
        Document.document_id == document_id).first()

    if not doc:
        return v2_err("NOT_FOUND", f"文档 {document_id} 不存在", req_id, retryable=False)

    try:
        if confirmed:
            doc.status = "confirmed"
            doc.ocr_confirmed = True
            if doc_text:
                doc.ocr_text = doc_text
            status = "confirmed"
        else:
            doc.status = "skipped"
            doc.ocr_confirmed = False
            status = "skipped"
        db.commit()

        return v2_ok({
            "document_id": document_id,
            "document_text": doc.ocr_text,
            "ocr_status": status,
        }, req_id)

    except Exception as e:
        db.rollback()
        return v2_err("CONFIRM_FAILED", str(e), req_id, retryable=True)


@router.get("/documents/{session_id}", summary="V2 — 查询Session文档")
async def list_documents_v2(session_id: str, db: Session = Depends(get_db)):
    req_id = f"req_{datetime.now(timezone.utc).strftime('%H%M%S')}"

    docs = db.query(Document).filter(
        Document.session_id == session_id,
        Document.status != "deleted",
    ).all()

    items = [{
        "document_id": d.document_id,
        "filename": d.original_filename,
        "file_type": d.file_type,
        "status": d.status,
        "ocr_confirmed": d.ocr_confirmed,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    } for d in docs]

    return v2_ok({"session_id": session_id, "documents": items, "total": len(items)}, req_id)

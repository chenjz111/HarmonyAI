"""Document Router — Sprint 3 Issue #36.

POST   /api/v2/documents          — 上传病例材料
GET    /api/v2/documents/{session_id} — 查询Session关联文档
POST   /api/v2/documents/confirm  — 确认/跳过/删除
DELETE /api/v2/documents/{document_id} — 删除单个文档
"""
from datetime import datetime, timezone
import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.document import Document
from backend.app.schemas.document import (
    DocumentUploadRequest, DocumentResponse, DocumentConfirmRequest,
    DocumentListResponse, DocumentStatus, ALLOWED_TYPES,
)
from backend.app.schemas.common import UniversalOutput, AgentStatus, AgentLayer, make_run_id
from backend.app.core.exceptions import build_error_response
from backend.app.core.ocr import OCRProvider

router = APIRouter()
ocr = OCRProvider()


@router.post("/documents", summary="上传病例材料(JPG/PNG/PDF)")
async def upload_document(body: DocumentUploadRequest, db: Session = Depends(get_db)):
    """上传病例图片或PDF。返回 document_id。"""
    session_id = body.session_id
    user_id = body.user_id
    run_id = make_run_id("doc")

    try:
        # Ensure session exists (FK constraint)
        from backend.app.models.session import Session
        existing = db.query(Session).filter(Session.session_id == session_id).first()
        if not existing:
            db.add(Session(user_id=1, session_id=session_id, status="active",
                           current_agent="document_upload"))
            db.commit()

        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        doc_id = f"doc_{today_str}_{datetime.now(timezone.utc).strftime('%H%M%S')}"

        # Run OCR (stub — never fails)
        ocr_result = ocr.process(body.storage_path, body.file_type)

        doc = Document(
            user_id=1, session_id=session_id,
            document_id=doc_id,
            original_filename=body.original_filename,
            file_type=body.file_type,
            file_size_bytes=body.file_size_bytes,
            page_count=body.page_count,
            storage_path=body.storage_path,
            status="uploaded",
            ocr_text=ocr_result.text,
            ocr_confidence=ocr_result.confidence,
            ocr_confirmed=False,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        return DocumentResponse(
            document_id=doc_id,
            session_id=session_id,
            original_filename=body.original_filename,
            file_type=body.file_type,
            file_size_bytes=body.file_size_bytes,
            page_count=body.page_count,
            status=DocumentStatus.UPLOADED,
            ocr_text=ocr_result.text,
            ocr_confidence=ocr_result.confidence,
            ocr_confirmed=False,
            created_at=doc.created_at,
        )

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        return build_error_response(
            agent_id="document_upload", agent_name="文档上传",
            agent_layer=AgentLayer.MEDICAL_ANALYSIS,
            session_id=session_id, user_id=user_id, error=e, run_id=run_id,
        )


@router.get("/documents/{session_id}", summary="查询Session关联文档")
async def list_documents(session_id: str, db: Session = Depends(get_db)):
    """返回指定 session 的所有文档。"""
    docs = db.query(Document).filter(
        Document.session_id == session_id,
        Document.status != "deleted",
    ).all()

    items = [
        DocumentResponse(
            document_id=d.document_id,
            session_id=d.session_id,
            original_filename=d.original_filename,
            file_type=d.file_type,
            file_size_bytes=d.file_size_bytes,
            page_count=d.page_count or 1,
            status=DocumentStatus(d.status),
            ocr_text=d.ocr_text,
            ocr_confidence=d.ocr_confidence,
            ocr_confirmed=d.ocr_confirmed,
            created_at=d.created_at,
        )
        for d in docs
    ]
    return DocumentListResponse(session_id=session_id, documents=items, total=len(items))


@router.post("/documents/confirm", summary="确认/跳过/删除文档")
async def confirm_document(body: DocumentConfirmRequest, db: Session = Depends(get_db)):
    """用户确认OCR文本、跳过、或删除文档。"""
    session_id = body.session_id

    try:
        doc = db.query(Document).filter(
            Document.document_id == body.document_id,
            Document.session_id == session_id,
        ).first()

        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {body.document_id} not found")

        action = body.action.lower()
        if action == "confirm":
            doc.status = "confirmed"
            doc.ocr_confirmed = True
            if body.ocr_text:
                doc.ocr_text = body.ocr_text
        elif action == "skip":
            doc.status = "skipped"
            doc.ocr_confirmed = False
        elif action == "delete":
            doc.status = "deleted"
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

        db.commit()
        db.refresh(doc)

        return DocumentResponse(
            document_id=doc.document_id,
            session_id=doc.session_id,
            original_filename=doc.original_filename,
            file_type=doc.file_type,
            file_size_bytes=doc.file_size_bytes,
            page_count=doc.page_count or 1,
            status=DocumentStatus(doc.status),
            ocr_text=doc.ocr_text,
            ocr_confidence=doc.ocr_confidence,
            ocr_confirmed=doc.ocr_confirmed,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        return build_error_response(
            agent_id="document_confirm", agent_name="文档确认",
            agent_layer=AgentLayer.MEDICAL_ANALYSIS,
            session_id=session_id, user_id="u_001", error=e, run_id=make_run_id("dc"),
        )

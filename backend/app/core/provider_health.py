"""Provider health check — Sprint 4.

Reports status of all external providers: LLM, OCR, DB, Music API.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from typing import Optional


@dataclass
class ProviderStatus:
    name: str
    status: str  # ok / degraded / down / not_configured
    provider_type: str  # llm / ocr / database / music / knowledge
    message: str
    latency_ms: int = 0
    error: Optional[str] = None


def check_all_providers() -> dict[str, dict[str, object]]:
    """Return Frozen Contract health metadata without secrets or user data."""
    checked_at = datetime.now(timezone.utc).isoformat()

    qwen_configured = bool(
        os.getenv("QWEN_BASE_URL", "").strip()
        and os.getenv("QWEN_API_KEY", "").strip()
        and os.getenv("QWEN_MODEL", "").strip()
    )
    qwen = {
        "configured": qwen_configured,
        "reachable": False,
        "model": os.getenv("QWEN_MODEL", "").strip() or None,
        "latency_ms": 0,
        "last_checked": checked_at,
    }

    try:
        from backend.app.core.ocr import OCRProvider

        ocr_provider = OCRProvider()
        available = ocr_provider._init_paddle() is not None
        ocr_version = ocr_provider._engine_version
    except Exception:
        available = False
        ocr_version = "unavailable"
    ocr = {
        "engine": "paddleocr",
        "version": ocr_version,
        "available": available,
        "last_checked": checked_at,
    }

    try:
        import chromadb  # noqa: F401

        chroma_available = True
    except Exception:
        chroma_available = False
    chroma = {
        "available": chroma_available,
        "collection_count": None,
        "chunk_count": None,
        "last_checked": checked_at,
    }

    from backend.app.core.config import settings

    database_type = (
        "sqlite" if settings.DATABASE_URL.startswith("sqlite") else "mysql"
    )
    try:
        from backend.app.core.database import engine

        started = datetime.now(timezone.utc)
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        database_reachable = True
        database_latency = int(
            (datetime.now(timezone.utc) - started).total_seconds() * 1000
        )
    except Exception:
        database_reachable = False
        database_latency = 0
    database = {
        "type": database_type,
        "reachable": database_reachable,
        "latency_ms": database_latency,
        "last_checked": checked_at,
    }

    return {
        "qwen": qwen,
        "ocr": ocr,
        "chroma": chroma,
        "database": database,
    }

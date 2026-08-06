"""Provider health check — Sprint 4.

Reports status of all external providers: LLM, OCR, DB, Music API.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ProviderStatus:
    name: str
    status: str  # ok / degraded / down / not_configured
    provider_type: str  # llm / ocr / database / music / knowledge
    message: str
    latency_ms: int = 0
    error: Optional[str] = None


def check_all_providers() -> list[ProviderStatus]:
    results = []

    # LLM (Qwen)
    try:
        from backend.app.core.agent_config import use_real_agents
        if use_real_agents():
            results.append(ProviderStatus(name="qwen", status="ok", provider_type="llm",
                                          message="Qwen configured", latency_ms=0))
        else:
            results.append(ProviderStatus(name="qwen", status="degraded", provider_type="llm",
                                          message="Qwen not configured, using stubs"))
    except Exception as e:
        results.append(ProviderStatus(name="qwen", status="down", provider_type="llm",
                                       message=str(e), error=str(e)))

    # OCR (PaddleOCR)
    try:
        from backend.app.core.ocr import OCRProvider
        ocr = OCRProvider()
        ocr._init_paddle()
        if ocr._paddle is not None:
            results.append(ProviderStatus(name="paddleocr", status="ok", provider_type="ocr",
                                          message="PaddleOCR ready"))
        else:
            results.append(ProviderStatus(name="paddleocr", status="degraded", provider_type="ocr",
                                          message="PaddleOCR not installed, using stub"))
    except Exception as e:
        results.append(ProviderStatus(name="paddleocr", status="down", provider_type="ocr",
                                       message=str(e)[:200], error=str(e)))

    # Database
    try:
        from backend.app.core.database import engine
        start = datetime.now(timezone.utc)
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        latency = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        results.append(ProviderStatus(name="mysql", status="ok", provider_type="database",
                                      message="MySQL connected", latency_ms=latency))
    except Exception as e:
        results.append(ProviderStatus(name="mysql", status="down", provider_type="database",
                                       message=str(e)[:200], error=str(e)))

    # Music API
    results.append(ProviderStatus(name="skymusic", status="degraded", provider_type="music",
                                  message="Music API stub, local library only"))

    return results

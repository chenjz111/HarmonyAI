"""OCR Provider adapter — Sprint 3 Issue #36.

Stub implementation that returns mock OCR text.
Replaced with PaddleOCR in production.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class OCRResult:
    text: str
    confidence: str  # high / medium / low
    provider: str


class OCRProvider:
    """Stub OCR — always returns mock text.
    PaddleOCR integration is Sprint 3+ Nice-to-Have.
    """

    def process(self, storage_path: str, file_type: str) -> OCRResult:
        """Simulate OCR processing. Never fails."""
        if file_type == "pdf":
            return OCRResult(
                text="[OCR Stub] PDF文本提取成功。",
                confidence="medium",
                provider="stub",
            )
        return OCRResult(
            text="[OCR Stub] 图片文本识别成功。",
            confidence="high",
            provider="stub",
        )

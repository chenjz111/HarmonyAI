"""OCR Provider — Sprint 4: PaddleOCR integration.

Real PaddleOCR with explicit failure modes.
OCR失败必须明确返回失败/降级，不伪装成功。
"""
from __future__ import annotations
from dataclasses import dataclass, field
import logging
import os
import struct

logger = logging.getLogger("ocr")

# ── PDF encrypted detection ──
def _is_pdf_encrypted(file_path: str) -> bool:
    """Check if PDF is encrypted by scanning for /Encrypt entry."""
    try:
        with open(file_path, "rb") as f:
            header = f.read(4096).decode("latin-1", errors="ignore")
            return "/Encrypt" in header
    except Exception:
        return False


def _count_pdf_pages(file_path: str) -> int:
    """Count PDF pages. Returns 0 on failure."""
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        text = content.decode("latin-1", errors="ignore")
        count = text.count("/Type /Page") - text.count("/Type /Pages")
        return max(1, count)
    except Exception:
        return 0


@dataclass
class OCRResult:
    text: str
    confidence: str  # high / medium / low / failed
    provider: str  # paddleocr / stub
    page_count: int = 1
    encrypted: bool = False
    page_confidences: list[float] = field(default_factory=list)
    error: str | None = None
    degraded: bool = False


class OCRProvider:
    """Real PaddleOCR provider. Never returns fake success."""

    def __init__(self):
        self._paddle = None
        self._init_attempted = False

    def _init_paddle(self):
        if self._init_attempted:
            return self._paddle
        self._init_attempted = True
        try:
            from paddleocr import PaddleOCR
            self._paddle = PaddleOCR(lang="ch", use_angle_cls=True, show_log=False)
            logger.info("PaddleOCR initialized")
        except ImportError:
            logger.warning("PaddleOCR not installed, will return degraded on all OCR calls")
        except Exception as e:
            logger.warning(f"PaddleOCR init failed: {e}")
        return self._paddle

    def process(self, file_path: str, file_type: str) -> OCRResult:
        """Run OCR. Returns degraded/failed on error, never fakes success."""
        paddle = self._init_paddle()

        # PDF checks
        page_count = 1
        encrypted = False
        if file_type == "pdf":
            encrypted = _is_pdf_encrypted(file_path)
            if encrypted:
                return OCRResult(
                    text="",
                    confidence="failed",
                    provider="paddleocr",
                    page_count=0,
                    encrypted=True,
                    error="encrypted_pdf",
                    degraded=True,
                )
            page_count = _count_pdf_pages(file_path)
            if page_count == 0:
                return OCRResult(
                    text="",
                    confidence="failed",
                    provider="paddleocr",
                    page_count=0,
                    error="pdf_page_count_failed",
                    degraded=True,
                )

        # File existence
        if not os.path.exists(file_path):
            return OCRResult(
                text="",
                confidence="failed",
                provider="paddleocr",
                page_count=page_count,
                encrypted=encrypted,
                error="file_not_found",
                degraded=True,
            )

        # PaddleOCR
        if paddle is not None:
            try:
                result = paddle.ocr(file_path, cls=True)
                if result and result[0]:
                    lines = []
                    page_confs = []
                    for line_info in result[0]:
                        text = line_info[1][0]
                        conf = line_info[1][1]
                        lines.append(text)
                        page_confs.append(conf)
                    text = "\n".join(lines)
                    avg_conf = sum(page_confs) / len(page_confs) if page_confs else 0
                    confidence = "high" if avg_conf >= 0.8 else ("medium" if avg_conf >= 0.5 else "low")
                    return OCRResult(
                        text=text, confidence=confidence,
                        provider="paddleocr", page_count=page_count,
                        encrypted=encrypted, page_confidences=page_confs,
                    )

                # Empty result — this IS a degraded state
                logger.warning(f"PaddleOCR returned empty result: {file_path}")
                return OCRResult(
                    text="",
                    confidence="degraded",
                    provider="paddleocr",
                    page_count=page_count,
                    encrypted=encrypted,
                    error="empty_ocr_result",
                    degraded=True,
                )

            except Exception as e:
                logger.error(f"PaddleOCR error for {os.path.basename(file_path)}: {e}")
                return OCRResult(
                    text="",
                    confidence="failed",
                    provider="paddleocr",
                    page_count=page_count,
                    encrypted=encrypted,
                    error=f"ocr_exception:{type(e).__name__}",
                    degraded=True,
                )

        # PaddleOCR not installed — explicit degraded
        return OCRResult(
            text="",
            confidence="degraded",
            provider="stub",
            page_count=page_count,
            encrypted=encrypted,
            error="paddleocr_not_available",
            degraded=True,
        )

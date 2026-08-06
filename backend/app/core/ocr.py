"""OCR Provider — Sprint 4: PaddleOCR integration.

Attempt to use PaddleOCR; degrade to stub on failure.
Never returns fake success.
"""
from __future__ import annotations
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    text: str
    confidence: str  # high / medium / low
    provider: str  # paddleocr / stub
    error: str | None = None


class OCRProvider:
    """Real PaddleOCR provider with stub fallback."""

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
            logger.info("PaddleOCR initialized successfully")
        except ImportError:
            logger.warning("PaddleOCR not installed, using stub fallback")
        except Exception as e:
            logger.warning(f"PaddleOCR init failed: {e}, using stub fallback")
        return self._paddle

    def process(self, file_path: str, file_type: str) -> OCRResult:
        """Run OCR. Returns real text if PaddleOCR works, stub text otherwise."""
        paddle = self._init_paddle()

        if paddle is not None:
            try:
                result = paddle.ocr(file_path, cls=True)
                if result and result[0]:
                    lines = []
                    total_conf = 0.0
                    count = 0
                    for line_info in result[0]:
                        text = line_info[1][0]
                        conf = line_info[1][1]
                        lines.append(text)
                        total_conf += conf
                        count += 1
                    text = "\n".join(lines)
                    avg_conf = total_conf / count if count > 0 else 0
                    confidence = "high" if avg_conf >= 0.8 else ("medium" if avg_conf >= 0.5 else "low")
                    return OCRResult(text=text, confidence=confidence, provider="paddleocr")

                # PaddleOCR returned empty — degrade to stub
                logger.warning(f"PaddleOCR returned empty result for {file_path}")
                return OCRResult(
                    text="[OCR Stub] PaddleOCR returned empty result",
                    confidence="low",
                    provider="stub",
                    error="empty_result",
                )

            except Exception as e:
                logger.error(f"PaddleOCR error: {e}")
                return OCRResult(
                    text=f"[OCR Stub] PaddleOCR failed: {str(e)[:100]}",
                    confidence="low",
                    provider="stub",
                    error=str(e)[:200],
                )

        # Stub fallback — honestly labeled
        return OCRResult(
            text="[OCR Stub] PaddleOCR not available. Please verify text manually.",
            confidence="low",
            provider="stub",
            error="paddleocr_not_installed",
        )

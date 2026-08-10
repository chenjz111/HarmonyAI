"""OCR Provider — Sprint 4: PaddleOCR integration.

Real PaddleOCR with explicit failure modes.
OCR失败必须明确返回失败/降级，不伪装成功。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from importlib import metadata
import logging
import os
from time import perf_counter

from pypdf import PdfReader

logger = logging.getLogger("ocr")

# ── PDF encrypted detection ──
def _is_pdf_encrypted(file_path: str) -> bool:
    """Read the PDF encryption flag through a real parser."""
    try:
        return bool(PdfReader(file_path, strict=False).is_encrypted)
    except Exception:
        return False


def _count_pdf_pages(file_path: str) -> int:
    """Count PDF pages through pypdf. Returns 0 on invalid/encrypted input."""
    try:
        reader = PdfReader(file_path, strict=False)
        if reader.is_encrypted:
            return 0
        return len(reader.pages)
    except Exception:
        return 0


@dataclass(frozen=True)
class BlockResult:
    text: str
    confidence: float
    bbox: tuple[int, int, int, int]


@dataclass(frozen=True)
class PageResult:
    page_number: int
    text: str
    confidence: float
    blocks: list[BlockResult]


@dataclass
class OCRResult:
    text: str
    confidence: str  # high / medium / low / failed
    provider: str = "paddleocr"
    page_count: int = 1
    encrypted: bool = False
    page_confidences: list[float] = field(default_factory=list)
    page_results: list[PageResult] = field(default_factory=list)
    average_confidence: float = 0.0
    engine_version: str = "unavailable"
    processing_time_ms: int = 0
    error: str | None = None
    error_code: str | None = None
    user_message: str | None = None
    next_actions: tuple[str, ...] = ()
    degraded: bool = False


class OCRProvider:
    """Real PaddleOCR provider. Never returns fake success."""

    def __init__(
        self,
        *,
        engine: str = "paddleocr",
        timeout: float = 30.0,
        paddle=None,
    ):
        if engine != "paddleocr":
            raise ValueError("unsupported OCR engine")
        self.engine = engine
        self.timeout = timeout
        self._paddle = paddle
        self._init_attempted = paddle is not None
        self._engine_version = getattr(paddle, "__version__", "unavailable")

    def _init_paddle(self):
        if self._init_attempted:
            return self._paddle
        self._init_attempted = True
        try:
            from paddleocr import PaddleOCR
            self._paddle = PaddleOCR(lang="ch", use_angle_cls=True, show_log=False)
            self._engine_version = metadata.version("paddleocr")
            logger.info("PaddleOCR initialized")
        except ImportError:
            logger.warning(
                "PaddleOCR unavailable",
                extra={"provider": "paddleocr", "error_code": "OCR_ENGINE_UNAVAILABLE"},
            )
        except Exception:
            logger.warning(
                "PaddleOCR initialization failed",
                extra={"provider": "paddleocr", "error_code": "OCR_ENGINE_UNAVAILABLE"},
            )
        return self._paddle

    @staticmethod
    def _bbox(points) -> tuple[int, int, int, int]:
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        left, top = min(xs), min(ys)
        right, bottom = max(xs), max(ys)
        return (
            round(left),
            round(top),
            round(right - left),
            round(bottom - top),
        )

    @classmethod
    def _parse_pages(cls, raw_result) -> list[PageResult]:
        if not isinstance(raw_result, list):
            return []
        pages: list[PageResult] = []
        for page_number, raw_page in enumerate(raw_result, start=1):
            blocks: list[BlockResult] = []
            if isinstance(raw_page, list):
                for raw_line in raw_page:
                    try:
                        points, recognized = raw_line
                        text, confidence = recognized
                        if not isinstance(text, str) or not text.strip():
                            continue
                        blocks.append(
                            BlockResult(
                                text=text.strip(),
                                confidence=float(confidence),
                                bbox=cls._bbox(points),
                            )
                        )
                    except (TypeError, ValueError, IndexError):
                        continue
            page_text = "\n".join(block.text for block in blocks)
            page_confidence = (
                sum(block.confidence for block in blocks) / len(blocks)
                if blocks
                else 0.0
            )
            pages.append(
                PageResult(
                    page_number=page_number,
                    text=page_text,
                    confidence=page_confidence,
                    blocks=blocks,
                )
            )
        return pages

    def process(self, file_path: str, file_type: str) -> OCRResult:
        """Run OCR. Returns degraded/failed on error, never fakes success."""
        started = perf_counter()
        paddle = self._init_paddle()
        # Keep provider identity stable; availability is expressed through
        # status/error_code rather than a fake stub provider.
        provider = "paddleocr"

        # PDF checks
        page_count = 1
        encrypted = False
        if file_type == "pdf":
            encrypted = _is_pdf_encrypted(file_path)
            if encrypted:
                return OCRResult(
                    text="",
                    confidence="failed",
                    provider=provider,
                    page_count=0,
                    encrypted=True,
                    error="encrypted_pdf",
                    error_code="ENCRYPTED_PDF",
                    user_message="PDF 已加密，请上传未加密文件、手动输入或跳过。",
                    next_actions=("manual_input", "skip_document"),
                    degraded=True,
                )
            page_count = _count_pdf_pages(file_path)
            if page_count == 0:
                return OCRResult(
                    text="",
                    confidence="failed",
                    provider=provider,
                    page_count=0,
                    error="pdf_page_count_failed",
                    error_code="OCR_FAILED",
                    user_message="无法读取 PDF，请重新上传、手动输入或跳过。",
                    next_actions=("manual_input", "retry_ocr", "skip_document"),
                    degraded=True,
                )

        # File existence
        if not os.path.exists(file_path):
            return OCRResult(
                text="",
                confidence="failed",
                provider=provider,
                page_count=page_count,
                encrypted=encrypted,
                error="file_not_found",
                error_code="OCR_FAILED",
                user_message="文件不可读取，请重新上传、手动输入或跳过。",
                next_actions=("manual_input", "retry_ocr", "skip_document"),
                degraded=True,
            )

        # PaddleOCR
        if paddle is not None:
            try:
                result = paddle.ocr(file_path, cls=True)
                page_results = self._parse_pages(result)
                blocks = [
                    block
                    for page in page_results
                    for block in page.blocks
                ]
                if blocks:
                    text = "\n".join(
                        page.text for page in page_results if page.text
                    )
                    avg_conf = sum(block.confidence for block in blocks) / len(blocks)
                    confidence = "high" if avg_conf >= 0.8 else ("medium" if avg_conf >= 0.5 else "low")
                    return OCRResult(
                        text=text, confidence=confidence,
                        provider="paddleocr", page_count=page_count,
                        encrypted=encrypted,
                        page_confidences=[
                            page.confidence for page in page_results
                        ],
                        page_results=page_results,
                        average_confidence=avg_conf,
                        engine_version=self._engine_version,
                        processing_time_ms=max(
                            0, round((perf_counter() - started) * 1000)
                        ),
                    )

                # Empty result — this IS a degraded state
                logger.warning(
                    "PaddleOCR returned no text",
                    extra={"provider": "paddleocr", "error_code": "OCR_FAILED"},
                )
                return OCRResult(
                    text="",
                    confidence="degraded",
                    provider="paddleocr",
                    page_count=page_count,
                    encrypted=encrypted,
                    error="empty_ocr_result",
                    error_code="OCR_FAILED",
                    user_message="未识别到文字，请手动输入、重试或跳过。",
                    next_actions=("manual_input", "retry_ocr", "skip_document"),
                    degraded=True,
                )

            except Exception as exc:
                error_code = (
                    "OCR_TIMEOUT"
                    if isinstance(exc, TimeoutError)
                    else "OCR_FAILED"
                )
                logger.error(
                    "PaddleOCR processing failed",
                    extra={"provider": "paddleocr", "error_code": error_code},
                )
                return OCRResult(
                    text="",
                    confidence="failed",
                    provider="paddleocr",
                    page_count=page_count,
                    encrypted=encrypted,
                    error=f"ocr_exception:{type(exc).__name__}",
                    error_code=error_code,
                    user_message="文字识别失败，请手动输入、重试或跳过。",
                    next_actions=("manual_input", "retry_ocr", "skip_document"),
                    engine_version=self._engine_version,
                    processing_time_ms=max(
                        0, round((perf_counter() - started) * 1000)
                    ),
                    degraded=True,
                )

        # PaddleOCR not installed — explicit degraded
        return OCRResult(
            text="",
            confidence="degraded",
            provider="paddleocr",
            page_count=page_count,
            encrypted=encrypted,
            error="paddleocr_not_available",
            error_code="OCR_ENGINE_UNAVAILABLE",
            user_message="文字识别服务暂时不可用，请手动输入、重试或跳过。",
            next_actions=("manual_input", "retry_ocr", "skip_document"),
            engine_version=self._engine_version,
            processing_time_ms=max(
                0, round((perf_counter() - started) * 1000)
            ),
            degraded=True,
        )

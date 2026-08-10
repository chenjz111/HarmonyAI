"""Real OCR tests — Sprint 4. Never fakes success."""
import io
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import pytest
from pypdf import PdfWriter
from backend.app.core.ocr import OCRProvider, _count_pdf_pages, _is_pdf_encrypted


def _pdf_bytes(page_count=1, password=None):
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)
    if password:
        writer.encrypt(password)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class FakePaddleOCR:
    __version__ = "2.8.1-test"

    def ocr(self, _path, cls=True):
        assert cls is True
        return [
            [
                [
                    [[0, 0], [20, 0], [20, 10], [0, 10]],
                    ("第一页", 0.9),
                ]
            ],
            [
                [
                    [[5, 5], [25, 5], [25, 15], [5, 15]],
                    ("第二页", 0.7),
                ]
            ],
        ]


class FailingPaddleOCR:
    __version__ = "2.8.1-test"

    def ocr(self, _path, cls=True):
        raise RuntimeError("provider response containing private input")


class TestOCRDegradation:
    def test_ocr_never_fakes_success(self):
        """Without PaddleOCR, OCR must return degraded, not success."""
        ocr = OCRProvider()
        result = ocr.process("/nonexistent/file.jpg", "jpg")
        assert result.degraded or result.confidence in ("failed", "degraded")
        assert result.provider == "paddleocr"
        assert result.error_code in {"OCR_ENGINE_UNAVAILABLE", "OCR_FAILED"}
        assert result.user_message
        assert result.next_actions == ("manual_input", "retry_ocr", "skip_document")
        # Must NOT contain fake "success" text
        assert "识别成功" not in (result.text or "")
        assert "[OCR Stub]" not in (result.text or "")

    def test_ocr_missing_file(self):
        """Missing file returns failed, not fake text."""
        ocr = OCRProvider()
        f = tempfile.mktemp(suffix=".png")
        result = ocr.process(f, "png")
        assert result.confidence == "failed"
        assert result.degraded
        assert not result.text  # empty, not fake

    def test_pdf_page_count(self):
        """PDF page counting works."""
        pdf_path = tempfile.mktemp(suffix=".pdf")
        with open(pdf_path, "wb") as f:
            f.write(_pdf_bytes(page_count=2))
        count = _count_pdf_pages(pdf_path)
        assert count == 2
        os.remove(pdf_path)

    def test_encrypted_pdf_detection(self):
        """Encrypted PDF is detected."""
        pdf_path = tempfile.mktemp(suffix=".pdf")
        with open(pdf_path, "wb") as f:
            f.write(_pdf_bytes(page_count=12, password="secret"))
        assert _is_pdf_encrypted(pdf_path)
        os.remove(pdf_path)

    def test_pdf_returns_page_and_block_confidence(self):
        pdf_path = tempfile.mktemp(suffix=".pdf")
        with open(pdf_path, "wb") as f:
            f.write(_pdf_bytes(page_count=2))
        try:
            result = OCRProvider(paddle=FakePaddleOCR()).process(pdf_path, "pdf")
        finally:
            os.remove(pdf_path)

        assert result.text == "第一页\n第二页"
        assert result.average_confidence == pytest.approx(0.8)
        assert result.page_count == 2
        assert [page.page_number for page in result.page_results] == [1, 2]
        assert result.page_results[0].confidence == pytest.approx(0.9)
        assert result.page_results[1].blocks[0].bbox == (5, 5, 20, 10)
        assert result.page_results[1].blocks[0].text == "第二页"

    def test_provider_failure_returns_safe_code_without_fake_text(self):
        image_path = tempfile.mktemp(suffix=".png")
        with open(image_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\nimage")
        try:
            result = OCRProvider(paddle=FailingPaddleOCR()).process(
                image_path, "png"
            )
        finally:
            os.remove(image_path)

        assert result.confidence == "failed"
        assert result.error_code == "OCR_FAILED"
        assert result.text == ""
        assert "private input" not in result.user_message

    def test_ocr_provider_honest(self):
        """OCR labels provider honestly."""
        ocr = OCRProvider()
        result = ocr.process("test.jpg", "jpg")  # non-existent file
        assert result.provider in ("paddleocr", "stub")
        assert result.confidence in ("failed", "degraded")
        assert result.degraded or result.confidence == "failed"


class TestFollowUpLimit:
    def test_max_4_followups(self):
        from backend.app.routers.assessment_v2_router import MAX_FOLLOWUPS
        assert MAX_FOLLOWUPS == 4

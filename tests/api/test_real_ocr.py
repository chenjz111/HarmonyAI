"""Real OCR tests — Sprint 4. Never fakes success."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import pytest
from backend.app.core.ocr import OCRProvider, _count_pdf_pages, _is_pdf_encrypted


class TestOCRDegradation:
    def test_ocr_never_fakes_success(self):
        """Without PaddleOCR, OCR must return degraded, not success."""
        ocr = OCRProvider()
        result = ocr.process("/nonexistent/file.jpg", "jpg")
        assert result.degraded or result.confidence in ("failed", "degraded")
        assert result.provider == "stub"  # No PaddleOCR installed
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
        # Create minimal single-page PDF
        pdf_path = tempfile.mktemp(suffix=".pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4\n1 0 obj<</Type /Page>>\nendobj\n%%EOF")
        count = _count_pdf_pages(pdf_path)
        assert count >= 1
        os.remove(pdf_path)

    def test_encrypted_pdf_detection(self):
        """Encrypted PDF is detected."""
        pdf_path = tempfile.mktemp(suffix=".pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4\n1 0 obj<</Type /Page /Encrypt 2 0 R>>\nendobj\n%%EOF")
        assert _is_pdf_encrypted(pdf_path)
        os.remove(pdf_path)

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

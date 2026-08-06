"""Real OCR tests — Sprint 4."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import pytest
from backend.app.core.ocr import OCRProvider


def test_ocr_stub_fallback():
    """When PaddleOCR not installed, stub returns low confidence."""
    ocr = OCRProvider()
    result = ocr.process("nonexistent.jpg", "jpg")
    assert result.provider == "stub"
    assert result.confidence == "low"
    assert "Stub" in result.text


def test_ocr_never_fakes_success():
    """OCR stub never returns high confidence."""
    ocr = OCRProvider()
    result = ocr.process("anything.png", "png")
    assert result.confidence in ("low", "medium")
    assert result.provider == "stub"


def test_ocr_provider_label_honest():
    """OCR result always labels its provider."""
    ocr = OCRProvider()
    result = ocr.process("test.pdf", "pdf")
    assert result.provider in ("paddleocr", "stub")
    assert isinstance(result.confidence, str)

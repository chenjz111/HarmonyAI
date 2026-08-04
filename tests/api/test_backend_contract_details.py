"""Regression tests for Sprint 3 API contract details."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models.feedback import Feedback
from backend.app.schemas.document import DocumentUploadRequest, MAX_PDF_PAGES


client = TestClient(app)


def _feedback_payload() -> dict:
    return {
        "session_id": "sess_contract_details",
        "music_id": "gong_001",
        "pre_state": {
            "tension": 7,
            "body_tension": 6,
            "mental_fatigue": 8,
            "goal": "sleep",
        },
        "post_state": {
            "tension": 5,
            "body_tension": 4,
            "mental_fatigue": 6,
            "change_label": "slightly_better",
        },
        "experience": {
            "overall_rating": 4,
            "relaxation_rating": 4,
            "music_match_rating": 3,
            "continue_use": "yes",
            "favorite": False,
        },
        "playback": {
            "listened_seconds": 780,
            "duration_seconds": 900,
            "completion_rate": 0.1,
            "pause_count": 2,
            "skip_count": 1,
        },
    }


def test_feedback_persists_playback_and_recomputes_completion_rate():
    response = client.post("/api/v2/feedback", json=_feedback_payload())
    assert response.json()["success"] is True

    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    try:
        feedback = db.query(Feedback).filter_by(
            session_id="sess_contract_details"
        ).one()
        assert feedback.behavioral_completion_rate == pytest.approx(780 / 900)
        assert feedback.behavioral_pause_count == 2
        assert feedback.behavioral_skip_count == 1
        assert feedback.behavioral_listen_session is None
    finally:
        db_generator.close()


def test_feedback_validation_error_does_not_echo_private_input():
    payload = _feedback_payload()
    private_marker = "private-health-note"
    payload["experience"]["comment"] = private_marker + ("x" * 500)

    data = client.post("/api/v2/feedback", json=payload).json()

    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert private_marker not in str(data)


def test_document_schema_uses_competition_pdf_page_limit():
    assert MAX_PDF_PAGES == 3

    with pytest.raises(ValidationError):
        DocumentUploadRequest(
            session_id="sess_pdf_limit",
            original_filename="record.pdf",
            file_type="pdf",
            file_size_bytes=1024,
            page_count=4,
            storage_path="uploads/record.pdf",
        )

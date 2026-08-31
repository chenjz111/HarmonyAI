"""Agent 4 music generation API — state machine, idempotency, ownership, stream.

Covers the frozen V3 contract surface (schemas/v3/music.py) end to end:
  POST /api/v3/music/generations            create (+ idempotent replay)
  GET  /api/v3/music/generations/{task_id}  poll
  POST /api/v3/music/generations/{task_id}/cancel
  GET  /api/v3/music/assets/{music_id}/stream

Security invariants asserted here:
  * private provider task ids / asset locators never reach the client
  * provider raw errors are normalized to the public vocabulary
  * a failed / unconfigured provider never fakes generation success
  * cross-user resources are 404 (not 403) and stream ownership is enforced
"""

import base64
from contextlib import contextmanager
import json
from hashlib import sha256
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import null

from backend.ai_engine.v3.music_provider import (
    MockMusicGenerationProvider,
    MusicProviderCapabilities,
    ProviderTask,
)
from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models import (
    Session as SessionModel,
    User,
)
from backend.app.models.v3.assessment import (
    AssessmentRevisionV3,
    AssessmentV3,
)
from backend.app.models.v3.diagnosis import DiagnosisRun
from backend.app.models.v3.identity import UserIdentity
from backend.app.models.v3.music import MusicAsset
from backend.app.models.v3.prescription import PrescriptionV3
from backend.app.models.v3.understanding import (
    UnderstandingRevision,
    UnderstandingRun,
)
from backend.app.routers.v3.generation_router import get_music_provider


client = TestClient(app)


@contextmanager
def _seed_db():
    """Session bound to the same engine the app's dependency override uses."""
    generator = app.dependency_overrides[get_db]()
    try:
        yield next(generator)
    finally:
        generator.close()


def _v3_data(response):
    return response.json()["data"]


def _public_user_id(token: str) -> str:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["sub"]


def _guest_headers(*, idempotency_key: str | None = None) -> dict[str, str]:
    token = _v3_data(client.post("/api/v3/auth/guest"))["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _create_session(headers: dict[str, str]) -> str:
    return _v3_data(
        client.post("/api/v3/sessions", headers=headers, json={})
    )["session_id"]


def _tone_profile(source_type: str = "available") -> dict[str, object]:
    return {
        "schema_version": "tone_profile_v3.0",
        "status": source_type,
        "weights": {
            "jiao": 0.2,
            "zhi": 0.2,
            "gong": 0.2,
            "shang": 0.2,
            "yu": 0.2,
        },
        "dominant_tone": "gong",
        "score_semantics": "relative_tone_distribution",
        "mapping_version": "test-only-v1",
        "basis": {
            "diagnosis_id": "diag_test",
            "supporting_fact_ids": ["fev_test"],
        },
    }


def _generation_spec() -> dict[str, object]:
    return {
        "schema_version": "generation_spec_v3.0",
        "tone_profile": _tone_profile(),
        "bpm": 60,
        "duration_seconds": 300,
        "instruments": ["guqin"],
        "ambient_sounds": ["water"],
        "structure": {
            "intro_seconds": 30,
            "main_seconds": 240,
            "outro_seconds": 30,
        },
        "energy_curve": "gentle_decline",
        "forbidden_constraints": ["sharp_high_frequency"],
        "fallback_policy": {"allow_local_matching": True},
    }


def _generation_body(
    prescription_id: str,
    idempotency_key: str,
    *,
    fallback: str = "local_matching",
) -> dict[str, object]:
    return {
        "schema_version": "music_generation_v3.0",
        "request_id": f"req_{uuid.uuid4().hex}",
        "prescription_id": prescription_id,
        "idempotency_key": idempotency_key,
        "generation_spec": _generation_spec(),
        "provider_policy": {
            "mode": "prefer_real_generation",
            "fallback": fallback,
        },
    }


def _capabilities() -> MusicProviderCapabilities:
    return MusicProviderCapabilities(
        max_duration_seconds=600,
        supports_progress=True,
        supports_cancel=True,
        supported_instruments=["guqin", "xiao"],
        supported_formats=["mp3", "wav"],
    )


def _row_ids(session, public_user_id: str, session_id: str) -> tuple[int, int]:
    user = (
        session.query(User)
        .join(UserIdentity, UserIdentity.internal_user_pk == User.id)
        .filter(UserIdentity.public_user_id == public_user_id)
        .one()
    )
    sess = (
        session.query(SessionModel)
        .filter(
            SessionModel.session_id == session_id,
            SessionModel.user_id == user.id,
        )
        .one()
    )
    return user.id, sess.id


def _seed_chain(
    session,
    *,
    public_user_id: str,
    session_id: str,
    generation_spec: dict[str, object] | None,
    status: str = "success",
) -> str:
    """Insert the full Assessment→Diagnosis→Prescription chain for a guest."""
    user_pk, session_row_id = _row_ids(session, public_user_id, session_id)
    run = UnderstandingRun(
        understanding_id=f"und_{uuid.uuid4().hex}",
        internal_user_pk=user_pk,
        session_row_id=session_row_id,
        current_revision=1,
        status="confirmed",
        safety_status="passed",
        degradation_json={},
    )
    session.add(run)
    session.flush()
    session.add(
        UnderstandingRevision(
            understanding_id=run.understanding_id,
            revision=1,
            status="confirmed",
            presentation_json={},
        )
    )
    session.flush()
    assessment = AssessmentV3(
        assessment_id=f"a_{uuid.uuid4().hex}",
        internal_user_pk=user_pk,
        session_row_id=session_row_id,
        understanding_id=run.understanding_id,
        understanding_revision=1,
        current_revision=1,
        status="confirmed",
        safety_status="passed",
        user_goal_json={},
    )
    session.add(assessment)
    session.flush()
    session.add(
        AssessmentRevisionV3(
            assessment_id=assessment.assessment_id,
            revision=1,
            understanding_revision=1,
            status="confirmed",
            confirmation_status="confirmed",
            state_summary="s",
            organ_profile_json={},
            evidence_coverage=0.8,
            source_diversity=2,
            conflicts_json=[],
            missing_information_json=[],
            degradation_json={},
            presentation_json={},
        )
    )
    session.flush()
    diagnosis = DiagnosisRun(
        diagnosis_id=f"d_{uuid.uuid4().hex}",
        internal_user_pk=user_pk,
        session_row_id=session_row_id,
        assessment_id=assessment.assessment_id,
        assessment_revision=1,
        status="success",
        abstained=0,
        degradation_json={},
        presentation_json={},
    )
    session.add(diagnosis)
    session.flush()
    prescription = PrescriptionV3(
        prescription_id=f"rx_{uuid.uuid4().hex}",
        internal_user_pk=user_pk,
        session_row_id=session_row_id,
        diagnosis_id=diagnosis.diagnosis_id,
        status=status,
        prescription_mode="syndrome_based",
        generation_spec_json=(
            generation_spec if generation_spec is not None else null()
        ),
        personalization_json={},
        presentation_json={},
    )
    session.add(prescription)
    session.commit()
    return prescription.prescription_id


def _seed_catalog_asset(session, *, audio_path, title: str) -> str:
    checksum = f"sha256:{sha256(audio_path.read_bytes()).hexdigest()}"
    asset = MusicAsset(
        music_asset_id=f"asset_{uuid.uuid4().hex}",
        owner_internal_user_pk=None,
        source_type="matched",
        title=title,
        storage_key=str(audio_path),
        format="mp3",
        duration_seconds=300,
        checksum=checksum,
        tone_profile_json=_tone_profile("fallback"),
        bpm=60,
        instruments_json=["guqin"],
        playable_status="ready",
    )
    session.add(asset)
    session.commit()
    return asset.music_asset_id


def _setup_guest(*, idempotency_key: str) -> tuple[dict[str, str], str]:
    headers = _guest_headers(idempotency_key=idempotency_key)
    session_id = _create_session(headers)
    return headers, session_id


# ---------------------------------------------------------------- fallback path


def test_unconfigured_provider_degrades_to_matched_fallback(tmp_path):
    audio = b"catalog-mp3-bytes"
    audio_path = tmp_path / "matched.mp3"
    audio_path.write_bytes(audio)
    headers, session_id = _setup_guest(idempotency_key="smoke-session")

    with _seed_db() as session:
        public_user_id = _public_user_id(headers["Authorization"].split()[1])
        _seed_catalog_asset(session, audio_path=audio_path, title="审核曲库-角调")
        rx_id = _seed_chain(
            session,
            public_user_id=public_user_id,
            session_id=session_id,
            generation_spec=_generation_spec(),
        )

    response = client.post(
        "/api/v3/music/generations",
        headers=headers,
        json=_generation_body(rx_id, "sha256:gen-fallback-1"),
    )

    assert response.status_code == 201
    body = _v3_data(response)
    # explicit fallback, never a fake success
    assert body["status"] == "matched_fallback"
    assert body["fallback"] == {
        "applied": True,
        "reason_code": "GENERATION_PROVIDER_UNAVAILABLE",
    }
    assert body["audio_asset"]["music_ref"]["source_type"] == "matched"
    # the private provider-not-configured detail is normalized to the public code
    assert "PROVIDER_NOT_CONFIGURED" not in response.text
    assert "MUSIC_PROVIDER_API_KEY" not in response.text
    # local storage paths never leak into the response
    assert str(tmp_path) not in response.text

    stream_url = body["audio_asset"]["stream_url"]
    stream = client.get(stream_url, headers=headers)
    assert stream.status_code == 200
    assert stream.content == audio


def test_unconfigured_provider_without_fallback_returns_failed(tmp_path):
    audio_path = tmp_path / "matched.mp3"
    audio_path.write_bytes(b"catalog-mp3-bytes")
    headers, session_id = _setup_guest(idempotency_key="no-fallback-session")

    with _seed_db() as session:
        public_user_id = _public_user_id(headers["Authorization"].split()[1])
        _seed_catalog_asset(session, audio_path=audio_path, title="审核曲库-角调")
        rx_id = _seed_chain(
            session,
            public_user_id=public_user_id,
            session_id=session_id,
            generation_spec=_generation_spec(),
        )

    response = client.post(
        "/api/v3/music/generations",
        headers=headers,
        json=_generation_body(
            rx_id, "sha256:gen-nofallback-1", fallback="none"
        ),
    )

    assert response.status_code == 201
    body = _v3_data(response)
    assert body["status"] == "failed"
    assert body["error_code"] == "GENERATION_PROVIDER_UNAVAILABLE"
    assert body["audio_asset"] is None
    assert body["fallback"]["applied"] is False


def test_generation_rejected_when_prescription_not_actionable():
    headers, session_id = _setup_guest(idempotency_key="withheld-session")

    with _seed_db() as session:
        public_user_id = _public_user_id(headers["Authorization"].split()[1])
        rx_id = _seed_chain(
            session,
            public_user_id=public_user_id,
            session_id=session_id,
            generation_spec=None,
            status="withheld",
        )

    response = client.post(
        "/api/v3/music/generations",
        headers=headers,
        json=_generation_body(rx_id, "sha256:gen-withheld-1"),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GENERATION_NOT_ALLOWED"


# --------------------------------------------------------------- success path


def test_successful_generation_poll_stream_and_terminal_cancel(tmp_path):
    audio = b"generated-mp3-bytes"
    audio_path = tmp_path / "generated.mp3"
    audio_path.write_bytes(audio)
    headers, session_id = _setup_guest(idempotency_key="success-session")
    provider = MockMusicGenerationProvider(
        tasks=[
            ProviderTask(
                provider_task_id="pt_1",
                status="queued",
                progress_value=None,
                asset_locator=None,
                error_code=None,
            ),
            ProviderTask(
                provider_task_id="pt_1",
                status="succeeded",
                progress_value=100,
                asset_locator=str(audio_path),
                error_code=None,
            ),
        ],
        capabilities=_capabilities(),
    )
    _install_provider_override(provider)

    with _seed_db() as session:
        public_user_id = _public_user_id(headers["Authorization"].split()[1])
        rx_id = _seed_chain(
            session,
            public_user_id=public_user_id,
            session_id=session_id,
            generation_spec=_generation_spec(),
        )

    body = _generation_body(rx_id, "sha256:gen-success-1")
    created = client.post("/api/v3/music/generations", headers=headers, json=body)
    assert created.status_code == 201
    task = _v3_data(created)
    assert task["status"] == "queued"
    assert task["audio_asset"] is None
    task_id = task["task_id"]

    # first poll still queued, second poll completes
    first_poll = client.get(
        f"/api/v3/music/generations/{task_id}", headers=headers
    )
    assert _v3_data(first_poll)["status"] == "queued"

    second_poll = client.get(
        f"/api/v3/music/generations/{task_id}", headers=headers
    )
    completed = _v3_data(second_poll)
    assert completed["status"] == "succeeded"
    assert completed["audio_asset"]["music_ref"]["source_type"] == "generated"
    assert completed["audio_asset"]["stream_url"].endswith("/stream")
    assert str(tmp_path) not in second_poll.text

    stream = client.get(completed["audio_asset"]["stream_url"], headers=headers)
    assert stream.status_code == 200
    assert stream.content == audio

    # a terminal task cannot be cancelled into another state
    cancelled = client.post(
        f"/api/v3/music/generations/{task_id}/cancel", headers=headers
    )
    assert cancelled.status_code == 200
    assert _v3_data(cancelled)["status"] == "succeeded"
    _uninstall_provider_override()


def _install_provider_override(provider) -> None:
    app.dependency_overrides[get_music_provider] = lambda: provider


def _uninstall_provider_override() -> None:
    app.dependency_overrides.pop(get_music_provider, None)


def test_cancel_unsupported_returns_409(tmp_path):
    audio_path = tmp_path / "generated.mp3"
    audio_path.write_bytes(b"x")
    headers, session_id = _setup_guest(idempotency_key="cancel-session")
    caps = MusicProviderCapabilities(
        max_duration_seconds=600,
        supports_progress=True,
        supports_cancel=False,
        supported_instruments=["guqin"],
        supported_formats=["mp3"],
    )
    provider = MockMusicGenerationProvider(
        tasks=[
            ProviderTask(
                provider_task_id="pt_1",
                status="queued",
                progress_value=None,
                asset_locator=None,
                error_code=None,
            )
        ],
        capabilities=caps,
    )
    _install_provider_override(provider)
    try:
        with _seed_db() as session:
            public_user_id = _public_user_id(headers["Authorization"].split()[1])
            rx_id = _seed_chain(
                session,
                public_user_id=public_user_id,
                session_id=session_id,
                generation_spec=_generation_spec(),
            )

        body = _generation_body(rx_id, "sha256:gen-cancel-1")
        created = client.post(
            "/api/v3/music/generations", headers=headers, json=body
        )
        task_id = _v3_data(created)["task_id"]

        response = client.post(
            f"/api/v3/music/generations/{task_id}/cancel", headers=headers
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "GENERATION_CANCEL_UNSUPPORTED"
    finally:
        _uninstall_provider_override()


# ------------------------------------------------------------------ idempotency


def test_idempotent_replay_returns_same_task(tmp_path):
    audio_path = tmp_path / "generated.mp3"
    audio_path.write_bytes(b"x")
    headers, session_id = _setup_guest(idempotency_key="replay-session")
    provider = MockMusicGenerationProvider(
        tasks=[
            ProviderTask(
                provider_task_id="pt_1",
                status="succeeded",
                progress_value=100,
                asset_locator=str(audio_path),
                error_code=None,
            )
        ],
        capabilities=_capabilities(),
    )
    _install_provider_override(provider)
    try:
        with _seed_db() as session:
            public_user_id = _public_user_id(headers["Authorization"].split()[1])
            rx_id = _seed_chain(
                session,
                public_user_id=public_user_id,
                session_id=session_id,
                generation_spec=_generation_spec(),
            )

        body = _generation_body(rx_id, "sha256:gen-replay-1")
        first = client.post("/api/v3/music/generations", headers=headers, json=body)
        assert first.status_code == 201
        task_id = _v3_data(first)["task_id"]

        second = client.post("/api/v3/music/generations", headers=headers, json=body)
        assert second.status_code == 200
        assert _v3_data(second)["task_id"] == task_id
        assert _v3_data(second)["status"] == "succeeded"
    finally:
        _uninstall_provider_override()


def test_idempotency_key_reused_with_different_body_conflicts(tmp_path):
    audio_path = tmp_path / "generated.mp3"
    audio_path.write_bytes(b"x")
    headers, session_id = _setup_guest(idempotency_key="conflict-session")
    provider = MockMusicGenerationProvider(
        tasks=[
            ProviderTask(
                provider_task_id="pt_1",
                status="succeeded",
                progress_value=100,
                asset_locator=str(audio_path),
                error_code=None,
            )
        ],
        capabilities=_capabilities(),
    )
    _install_provider_override(provider)
    try:
        with _seed_db() as session:
            public_user_id = _public_user_id(headers["Authorization"].split()[1])
            rx_id = _seed_chain(
                session,
                public_user_id=public_user_id,
                session_id=session_id,
                generation_spec=_generation_spec(),
            )

        first = client.post(
            "/api/v3/music/generations",
            headers=headers,
            json=_generation_body(rx_id, "sha256:gen-conflict-1"),
        )
        assert first.status_code == 201

        # same key, different request_id -> 409
        second = client.post(
            "/api/v3/music/generations",
            headers=headers,
            json=_generation_body(rx_id, "sha256:gen-conflict-1"),
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    finally:
        _uninstall_provider_override()


# ------------------------------------------------------------------- ownership


def test_cross_user_resources_are_not_found(tmp_path):
    audio = b"generated-mp3-bytes"
    audio_path = tmp_path / "generated.mp3"
    audio_path.write_bytes(audio)
    owner_headers, owner_session = _setup_guest(idempotency_key="owner-session")
    provider = MockMusicGenerationProvider(
        tasks=[
            ProviderTask(
                provider_task_id="pt_1",
                status="succeeded",
                progress_value=100,
                asset_locator=str(audio_path),
                error_code=None,
            )
        ],
        capabilities=_capabilities(),
    )
    _install_provider_override(provider)
    try:
        with _seed_db() as session:
            public_user_id = _public_user_id(
                owner_headers["Authorization"].split()[1]
            )
            rx_id = _seed_chain(
                session,
                public_user_id=public_user_id,
                session_id=owner_session,
                generation_spec=_generation_spec(),
            )

        body = _generation_body(rx_id, "sha256:gen-owner-1")
        created = client.post(
            "/api/v3/music/generations", headers=owner_headers, json=body
        )
        assert created.status_code == 201
        task_id = _v3_data(created)["task_id"]
        music_id = _v3_data(created)["audio_asset"]["music_ref"]["music_id"]

        stranger_headers = _guest_headers()
        stranger = client.get(
            f"/api/v3/music/generations/{task_id}", headers=stranger_headers
        )
        assert stranger.status_code == 404
        assert stranger.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

        stranger_cancel = client.post(
            f"/api/v3/music/generations/{task_id}/cancel",
            headers=stranger_headers,
        )
        assert stranger_cancel.status_code == 404

        stranger_stream = client.get(
            f"/api/v3/music/assets/{music_id}/stream", headers=stranger_headers
        )
        assert stranger_stream.status_code == 404
    finally:
        _uninstall_provider_override()


def test_unauthenticated_requests_are_rejected(tmp_path):
    audio_path = tmp_path / "generated.mp3"
    audio_path.write_bytes(b"x")
    headers, session_id = _setup_guest(idempotency_key="auth-session")
    provider = MockMusicGenerationProvider(
        tasks=[
            ProviderTask(
                provider_task_id="pt_1",
                status="succeeded",
                progress_value=100,
                asset_locator=str(audio_path),
                error_code=None,
            )
        ],
        capabilities=_capabilities(),
    )
    _install_provider_override(provider)
    try:
        with _seed_db() as session:
            public_user_id = _public_user_id(headers["Authorization"].split()[1])
            rx_id = _seed_chain(
                session,
                public_user_id=public_user_id,
                session_id=session_id,
                generation_spec=_generation_spec(),
            )

        body = _generation_body(rx_id, "sha256:gen-auth-1")
        anonymous = client.post(
            "/api/v3/music/generations", json=body
        )
        assert anonymous.status_code == 401
    finally:
        _uninstall_provider_override()

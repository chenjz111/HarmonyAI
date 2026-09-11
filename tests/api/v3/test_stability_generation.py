"""Agent 4 — Stability Stable Audio 2.5 real adapter end to end (offline).

Proves the frozen V3 surface with the real StabilityMusicProvider wired in
(fake poster, hermetic CI):

  POST /api/v3/music/generations -> succeeded + real audio asset persisted with
                                    provider=stability, source_type=generated,
                                    duration measured from the saved file
  GET  /api/v3/music/assets/{id}/stream -> plays the owned asset bytes

and the fail-closed paths:
  * Stability failure + reviewed catalog -> explicit matched_fallback
  * Stability failure without fallback   -> explicit failed task

The provider HTTP poster is faked (no network, no key); the Owner real-key
smoke stays an explicit gate (tools/stability_music_smoke.py).
"""

import base64
from contextlib import contextmanager
import json
from hashlib import sha256
from pathlib import Path
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import null

from backend.ai_engine.v3.stability_music_provider import StabilityMusicProvider
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
from backend.app.models.v3.music import GenerationTask, MusicAsset
from backend.app.models.v3.prescription import PrescriptionV3
from backend.app.models.v3.understanding import (
    UnderstandingRevision,
    UnderstandingRun,
)
from backend.app.routers.v3.generation_router import get_music_provider

client = TestClient(app)


# --------------------------------------------------------------------------- #
# fixtures / helpers
# --------------------------------------------------------------------------- #


def _mp3_bytes(*, seconds: float = 3.0) -> bytes:
    """Deterministic MPEG1 Layer III 128 kbps 44.1 kHz stream."""
    bitrate_kbps = 128
    samplerate = 44100
    samples_per_frame = 1152
    frame_length = int(samples_per_frame * bitrate_kbps * 1000 / (8 * samplerate))
    frame = b"\xff\xfb\x90\x00" + bytes(max(0, frame_length - 4))
    frames = max(1, int(seconds * samplerate / samples_per_frame) + 1)
    return frame * frames


class _FakeResponse:
    def __init__(self, *, status_code: int = 200, content: bytes = b""):
        self.status_code = status_code
        self.content = content
        self.headers = {"content-type": "audio/mpeg"}
        self.text = ""


class _FakePoster:
    def __init__(self, *, response: _FakeResponse | None = None, error: BaseException | None = None):
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def __call__(self, url, *, headers, data, files, timeout):
        self.calls.append({"url": url, "data": dict(data)})
        if self.error is not None:
            raise self.error
        if self.response is None:
            raise AssertionError("no scripted stability response")
        return self.response


@contextmanager
def _seed_db():
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
    return _v3_data(client.post("/api/v3/sessions", headers=headers, json={}))[
        "session_id"
    ]


def _tone_profile(source_type: str = "available") -> dict[str, object]:
    del source_type  # V3.1 ToneProfile has no status variant
    return {
        "schema_version": "tone_profile_v3.1",
        "weights": {
            "jiao": 0.2,
            "zhi": 0.2,
            "gong": 0.2,
            "shang": 0.2,
            "yu": 0.2,
        },
        "primary_tone": "gong",
        "secondary_tone": None,
        "score_semantics": "relative_tone_distribution",
        "mapping_version": "test-only-v1",
        "basis": {
            "diagnosis_id": "diag_test",
            "diagnosis_revision": 1,
            "supporting_evidence_refs": ["fev_test"],
        },
    }


def _generation_spec() -> dict[str, object]:
    return {
        "schema_version": "generation_spec_v3.0",
        "tone_profile": _tone_profile(),
        "bpm": 60,
        "duration_seconds": 60,
        "instruments": ["guqin", "xiao"],
        "ambient_sounds": ["water"],
        "structure": {"intro_seconds": 6, "main_seconds": 48, "outro_seconds": 6},
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
        "provider_policy": {"mode": "prefer_real_generation", "fallback": fallback},
    }


def _row_ids(session, public_user_id: str, session_id: str) -> tuple[int, int]:
    user = (
        session.query(User)
        .join(UserIdentity, UserIdentity.internal_user_pk == User.id)
        .filter(UserIdentity.public_user_id == public_user_id)
        .one()
    )
    sess = (
        session.query(SessionModel)
        .filter(SessionModel.session_id == session_id, SessionModel.user_id == user.id)
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
        duration_seconds=60,
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
    return headers, _create_session(headers)


def _install_provider(provider) -> None:
    app.dependency_overrides[get_music_provider] = lambda: provider


def _uninstall_provider() -> None:
    app.dependency_overrides.pop(get_music_provider, None)


def _real_provider(tmp_path, poster) -> StabilityMusicProvider:
    return StabilityMusicProvider(
        api_key="sk-test-stability-secret",
        model="stable-audio-2.5",
        base_url="https://stability.example.invalid",
        media_root=tmp_path,
        poster=poster,
    )


# ------------------------------------------------------------ generated success


def test_stability_success_persists_generated_asset_with_real_duration(tmp_path):
    audio = _mp3_bytes(seconds=3.0)  # ~3 s of real MPEG frames
    poster = _FakePoster(response=_FakeResponse(content=audio))
    _install_provider(_real_provider(tmp_path, poster))
    try:
        headers, session_id = _setup_guest(idempotency_key="stab-success")
        with _seed_db() as session:
            public_user_id = _public_user_id(headers["Authorization"].split()[1])
            rx_id = _seed_chain(
                session,
                public_user_id=public_user_id,
                session_id=session_id,
                generation_spec=_generation_spec(),
            )

        created = client.post(
            "/api/v3/music/generations",
            headers=headers,
            json=_generation_body(rx_id, "sha256:stab-success-1"),
        )
        assert created.status_code == 201
        body = _v3_data(created)
        assert body["status"] == "succeeded"
        assert body["fallback"]["applied"] is False
        assert body["error_code"] is None
        audio_asset = body["audio_asset"]
        assert audio_asset["music_ref"]["source_type"] == "generated"
        # duration is measured from the saved file (~3s), NOT the requested 60s
        assert audio_asset["duration_seconds"] == 3
        assert "stability.example.invalid" not in created.text
        assert "sk-test-stability-secret" not in created.text

        task_id = body["task_id"]
        with _seed_db() as session:
            task = (
                session.query(GenerationTask)
                .filter(GenerationTask.task_id == task_id)
                .one()
            )
            assert task.status == "succeeded"
            assert task.provider == "stability"
            assert task.provider_task_id is not None
            assert task.music_asset_id is not None
            assert task.fallback_applied == 0
            asset_row = (
                session.query(MusicAsset)
                .filter(MusicAsset.music_asset_id == task.music_asset_id)
                .one()
            )
            assert asset_row.source_type == "generated"
            assert asset_row.duration_seconds == 3
            assert asset_row.playable_status == "ready"
            assert Path(asset_row.storage_key).is_file()

        # Player reads the owned asset bytes
        stream = client.get(audio_asset["stream_url"], headers=headers)
        assert stream.status_code == 200
        assert stream.content == audio
        # exactly one provider POST (no automatic retry)
        assert len(poster.calls) == 1
    finally:
        _uninstall_provider()


# ------------------------------------------------- fail -> explicit fallback


def test_stability_failure_degrades_to_explicit_matched_fallback(tmp_path):
    import requests as _requests

    catalog = _mp3_bytes(seconds=2)
    audio_path = tmp_path / "matched.mp3"
    audio_path.write_bytes(catalog)

    poster = _FakePoster(error=_requests.ConnectionError("provider down"))
    _install_provider(_real_provider(tmp_path, poster))
    try:
        headers, session_id = _setup_guest(idempotency_key="stab-fallback")
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
            json=_generation_body(rx_id, "sha256:stab-fallback-1"),
        )
        assert response.status_code == 201
        body = _v3_data(response)
        # explicit reviewed fallback, never a fake generated success
        assert body["status"] == "matched_fallback"
        assert body["fallback"]["applied"] is True
        assert body["fallback"]["reason_code"] == "GENERATION_PROVIDER_UNAVAILABLE"
        assert body["audio_asset"]["music_ref"]["source_type"] == "matched"
        assert "stability.example.invalid" not in response.text
        assert "sk-test-stability-secret" not in response.text

        with _seed_db() as session:
            task = (
                session.query(GenerationTask)
                .filter(GenerationTask.task_id == body["task_id"])
                .one()
            )
            assert task.status == "matched_fallback"
            assert task.provider == "stability"
            assert task.provider_task_id is None
            assert task.fallback_applied == 1
            assert task.music_asset_id is not None

        # fallback asset remains playable
        stream = client.get(body["audio_asset"]["stream_url"], headers=headers)
        assert stream.status_code == 200
        assert stream.content == catalog
    finally:
        _uninstall_provider()


# --------------------------------------------------- fail without fallback


def test_stability_failure_without_fallback_returns_failed(tmp_path):
    import requests as _requests

    poster = _FakePoster(
        response=_FakeResponse(
            status_code=401,
            content=b"",
        )
    )
    _install_provider(_real_provider(tmp_path, poster))
    try:
        headers, session_id = _setup_guest(idempotency_key="stab-fail")
        with _seed_db() as session:
            public_user_id = _public_user_id(headers["Authorization"].split()[1])
            rx_id = _seed_chain(
                session,
                public_user_id=public_user_id,
                session_id=session_id,
                generation_spec=_generation_spec(),
            )

        response = client.post(
            "/api/v3/music/generations",
            headers=headers,
            json=_generation_body(rx_id, "sha256:stab-fail-1", fallback="none"),
        )
        assert response.status_code == 201
        body = _v3_data(response)
        assert body["status"] == "failed"
        assert body["error_code"] == "GENERATION_PROVIDER_AUTH_FAILED"
        assert body["audio_asset"] is None
        assert body["fallback"]["applied"] is False

        with _seed_db() as session:
            task = (
                session.query(GenerationTask)
                .filter(GenerationTask.task_id == body["task_id"])
                .one()
            )
            assert task.status == "failed"
            assert task.provider == "stability"
            assert task.error_code == "GENERATION_PROVIDER_AUTH_FAILED"
            assert task.music_asset_id is None
    finally:
        _uninstall_provider()

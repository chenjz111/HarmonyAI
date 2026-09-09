"""Agent 4 — MiniMax real adapter end to end (offline, fake transport).

Proves the frozen V3 surface with the real MiniMaxMusicProvider wired in:

  POST /api/v3/music/generations  -> succeeded + real audio asset + provider
                                    metadata persisted (source_type=generated)
  GET  /api/v3/music/assets/{id}/stream -> plays the owned asset bytes

and the fail-closed paths:
  * MiniMax failure + reviewed catalog -> explicit matched_fallback (never a
    fake generated success, provider identity still recorded)
  * MiniMax failure without fallback -> explicit failed task

The provider transport is faked (no network, no key) so CI stays hermetic; the
real-key smoke remains an Owner gate.
"""

import base64
from contextlib import contextmanager
import json
from hashlib import sha256
from pathlib import Path
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import null

from backend.ai_engine.v3.minimax_music_provider import MiniMaxMusicProvider
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

_MP3_BYTES = b"\xff\xfb\x90\x64\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"


class _FakeMiniMaxTransport:
    """Returns scripted MiniMax JSON or raises a scripted transport error."""

    def __init__(self, *, response: bytes | None = None, error: BaseException | None = None):
        self.response = response
        self.error = error

    def __call__(self, url, headers, body, timeout):
        if self.error is not None:
            raise self.error
        if self.response is None:
            raise AssertionError("no scripted miniMax response")
        return self.response


def _minimax_response(*, audio: bytes = _MP3_BYTES, status_code: int = 0) -> bytes:
    return json.dumps(
        {
            "data": {"status": 2, "audio": audio.hex()},
            "trace_id": "trace-minimax-1",
            "base_resp": {"status_code": status_code, "status_msg": "success"},
        }
    ).encode("utf-8")


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
        "basis": {"diagnosis_id": "diag_test", "supporting_fact_ids": ["fev_test"]},
    }


def _generation_spec() -> dict[str, object]:
    return {
        "schema_version": "generation_spec_v3.0",
        "tone_profile": _tone_profile(),
        "bpm": 60,
        "duration_seconds": 300,
        "instruments": ["guqin", "xiao"],
        "ambient_sounds": ["water"],
        "structure": {"intro_seconds": 30, "main_seconds": 240, "outro_seconds": 30},
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


def _install_provider(provider) -> None:
    app.dependency_overrides[get_music_provider] = lambda: provider


def _uninstall_provider() -> None:
    app.dependency_overrides.pop(get_music_provider, None)


def _setup_guest(*, idempotency_key: str) -> tuple[dict[str, str], str]:
    headers = _guest_headers(idempotency_key=idempotency_key)
    return headers, _create_session(headers)


# ------------------------------------------------------------ generated success


def test_minimax_success_persists_generated_asset_and_provider_metadata(tmp_path):
    transport = _FakeMiniMaxTransport(response=_minimax_response())
    provider = MiniMaxMusicProvider(
        base_url="https://minimax.example.invalid",
        api_key="sk-test-minimax-secret",
        model="music-3.0",
        media_root=tmp_path,
        transport=transport,
    )
    _install_provider(provider)
    try:
        headers, session_id = _setup_guest(idempotency_key="mmx-success")
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
            json=_generation_body(rx_id, "sha256:mmx-success-1"),
        )
        assert created.status_code == 201
        body = _v3_data(created)
        # real provider success -> real generated asset, never fallback
        assert body["status"] == "succeeded"
        assert body["fallback"]["applied"] is False
        assert body["error_code"] is None
        audio = body["audio_asset"]
        assert audio["music_ref"]["source_type"] == "generated"
        assert audio["stream_url"].endswith("/stream")
        assert "minimax.example.invalid" not in created.text
        assert "sk-test-minimax-secret" not in created.text
        assert "trace-minimax-1" not in created.text

        task_id = body["task_id"]
        with _seed_db() as session:
            task = (
                session.query(GenerationTask)
                .filter(GenerationTask.task_id == task_id)
                .one()
            )
            # ops-internal provider metadata persisted
            assert task.status == "succeeded"
            assert task.provider == "minimax"
            assert task.provider_task_id is not None
            assert task.music_asset_id is not None
            assert task.fallback_applied == 0
            asset_row = (
                session.query(MusicAsset)
                .filter(MusicAsset.music_asset_id == task.music_asset_id)
                .one()
            )
            assert asset_row.source_type == "generated"
            assert asset_row.playable_status == "ready"
            assert Path(asset_row.storage_key).is_file()

        # Player can read the owned asset bytes
        stream = client.get(audio["stream_url"], headers=headers)
        assert stream.status_code == 200
        assert stream.content == _MP3_BYTES
    finally:
        _uninstall_provider()


# ------------------------------------------------- fail -> explicit fallback


def test_minimax_failure_degrades_to_explicit_matched_fallback(tmp_path):
    from urllib.error import HTTPError

    catalog = b"reviewed-catalog-mp3"
    audio_path = tmp_path / "matched.mp3"
    audio_path.write_bytes(catalog)

    provider = MiniMaxMusicProvider(
        base_url="https://minimax.example.invalid",
        api_key="sk-test-minimax-secret",
        model="music-3.0",
        media_root=tmp_path,
        transport=_FakeMiniMaxTransport(
            error=HTTPError("https://minimax.example.invalid", 503, "boom", None, None)
        ),
    )
    _install_provider(provider)
    try:
        headers, session_id = _setup_guest(idempotency_key="mmx-fallback")
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
            json=_generation_body(rx_id, "sha256:mmx-fallback-1"),
        )
        assert response.status_code == 201
        body = _v3_data(response)
        # explicit reviewed fallback, never a fake generated success
        assert body["status"] == "matched_fallback"
        assert body["fallback"]["applied"] is True
        assert body["fallback"]["reason_code"] == "GENERATION_PROVIDER_UNAVAILABLE"
        assert body["audio_asset"]["music_ref"]["source_type"] == "matched"
        # raw vendor detail / private endpoint never leak into the response
        assert "boom" not in response.text
        assert "minimax.example.invalid" not in response.text

        with _seed_db() as session:
            task = (
                session.query(GenerationTask)
                .filter(GenerationTask.task_id == body["task_id"])
                .one()
            )
            assert task.status == "matched_fallback"
            assert task.provider == "minimax"
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


def test_minimax_failure_without_fallback_returns_failed(tmp_path):
    from urllib.error import HTTPError

    provider = MiniMaxMusicProvider(
        base_url="https://minimax.example.invalid",
        api_key="sk-test-minimax-secret",
        model="music-3.0",
        media_root=tmp_path,
        transport=_FakeMiniMaxTransport(
            error=HTTPError("https://minimax.example.invalid", 401, "denied", None, None)
        ),
    )
    _install_provider(provider)
    try:
        headers, session_id = _setup_guest(idempotency_key="mmx-fail")
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
            json=_generation_body(
                rx_id, "sha256:mmx-fail-1", fallback="none"
            ),
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
            assert task.provider == "minimax"
            assert task.error_code == "GENERATION_PROVIDER_AUTH_FAILED"
            assert task.music_asset_id is None
    finally:
        _uninstall_provider()

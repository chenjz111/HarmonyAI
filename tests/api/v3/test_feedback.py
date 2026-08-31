"""Agent 5 feedback / favorites / personal-data API.

Covers the two-stage persistence semantics: stage-1 feedback is durable even
when preference learning fails or is skipped; favorite linkage follows the
feedback intent; the preference profile is an immutable version chain; and
all personal data is scoped to the authenticated user.
"""

import base64
from contextlib import contextmanager
import json
from hashlib import sha256
import uuid

from fastapi.testclient import TestClient

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models import Session as SessionModel, User
from backend.app.models.v3.feedback import FeedbackV3 as FeedbackRow
from backend.app.models.v3.identity import UserIdentity
from backend.app.models.v3.music import MusicAsset


client = TestClient(app)


def _v3_data(response):
    return response.json()["data"]


def _public_user_id(token: str) -> str:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["sub"]


def _guest_headers() -> dict[str, str]:
    token = _v3_data(client.post("/api/v3/auth/guest"))["access_token"]
    return {"Authorization": f"Bearer {token}"}


@contextmanager
def _seed_db():
    generator = app.dependency_overrides[get_db]()
    try:
        yield next(generator)
    finally:
        generator.close()


def _setup_guest() -> tuple[dict[str, str], str]:
    headers = _guest_headers()
    session_id = _v3_data(
        client.post(
            "/api/v3/sessions",
            headers={**headers, "Idempotency-Key": "seed-session"},
            json={},
        )
    )["session_id"]
    return headers, session_id


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


def _seed_asset(
    session,
    *,
    user_pk: int,
    source_type: str = "matched",
    bpm: int = 60,
    duration_seconds: int = 300,
    instruments: tuple[str, ...] = ("guqin",),
) -> str:
    asset = MusicAsset(
        music_asset_id=f"asset_{uuid.uuid4().hex}",
        owner_internal_user_pk=user_pk,
        source_type=source_type,
        title="测试音频",
        storage_key="",
        format="mp3",
        duration_seconds=duration_seconds,
        checksum=f"sha256:{sha256(b'x').hexdigest()}",
        bpm=bpm,
        instruments_json=list(instruments),
        playable_status="ready",
    )
    session.add(asset)
    session.commit()
    return asset.music_asset_id


def _feedback_body(
    session_id: str,
    music_id: str,
    *,
    rating: int = 5,
    favorite: bool | None = None,
    comment: str | None = None,
    change_label: str = "slightly_better",
    features: tuple[str, ...] = (),
    adjustments: tuple[str, ...] = (),
    source_type: str = "matched",
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": "feedback_v3.0",
        "session_id": session_id,
        "music_ref": {"music_id": music_id, "source_type": source_type},
        "pre_state_snapshot": {
            "snapshot_id": f"snap_{uuid.uuid4().hex}",
            "source": "player_session",
            "captured_at": "2026-01-01T00:00:00Z",
            "tension": 6,
            "fatigue": 5,
        },
        "post_state": {
            "change_label": change_label,
            "tension": 3,
            "fatigue": 2,
        },
        "experience": {"overall_rating": rating, "music_match_rating": rating},
        "continue_use": "yes" if rating >= 4 else "maybe",
        "liked_features": list(features),
        "adjustment_preferences": list(adjustments),
        "playback": {"played_seconds": 300, "completed": True},
    }
    if favorite is not None:
        body["favorite"] = favorite
    if comment is not None:
        body["comment"] = comment
    return body


def _post_feedback(
    headers: dict[str, str], body: dict[str, object], idempotency_key: str
):
    return client.post(
        "/api/v3/feedback",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json=body,
    )


def _seed_user_asset(headers: dict[str, str], session_id: str) -> str:
    with _seed_db() as session:
        public_user_id = _public_user_id(headers["Authorization"].split()[1])
        user_pk, _ = _row_ids(session, public_user_id, session_id)
        return _seed_asset(session, user_pk=user_pk)


def test_submit_feedback_is_durable_and_idempotent():
    headers, session_id = _setup_guest()
    music_id = _seed_user_asset(headers, session_id)
    body = _feedback_body(session_id, music_id, comment="很有帮助")

    first = _post_feedback(headers, body, "sha256:fb-1")
    assert first.status_code == 201
    saved = _v3_data(first)
    assert saved["status"] == "saved"
    assert saved["preference_update"]["applied"] is False  # < min_samples
    feedback_id = saved["feedback_id"]

    second = _post_feedback(headers, body, "sha256:fb-1")
    assert second.status_code == 200
    assert _v3_data(second)["feedback_id"] == feedback_id

    history = _v3_data(client.get("/api/v3/me/history", headers=headers))
    assert history["total"] == 1
    assert history["items"][0]["feedback_id"] == feedback_id
    assert history["items"][0]["music_ref"]["music_id"] == music_id


def test_feedback_without_idempotency_key_is_rejected():
    headers, session_id = _setup_guest()
    music_id = _seed_user_asset(headers, session_id)
    response = client.post(
        "/api/v3/feedback",
        headers=headers,
        json=_feedback_body(session_id, music_id),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_favorite_lifecycle_never_deletes_asset():
    headers, session_id = _setup_guest()
    music_id = _seed_user_asset(headers, session_id)

    add = _post_feedback(
        headers,
        _feedback_body(session_id, music_id, favorite=True),
        "sha256:fb-fav-1",
    )
    assert add.status_code == 201

    favorites = _v3_data(client.get("/api/v3/favorites", headers=headers))
    assert favorites["total"] == 1
    assert favorites["items"][0]["music_ref"]["music_id"] == music_id

    # explicit favorite=false removes the linkage
    _post_feedback(
        headers,
        _feedback_body(session_id, music_id, favorite=False),
        "sha256:fb-unfav-1",
    )
    favorites = _v3_data(client.get("/api/v3/favorites", headers=headers))
    assert favorites["total"] == 0

    # hard-deleting the favorite must not delete the music asset itself
    state = _v3_data(
        client.delete(f"/api/v3/favorites/{music_id}", headers=headers)
    )
    assert state["is_favorite"] is False
    with _seed_db() as session:
        assert session.query(MusicAsset).filter(
            MusicAsset.music_asset_id == music_id
        ).one_or_none() is not None


def test_preference_learning_advances_versions_after_min_samples():
    headers, session_id = _setup_guest()
    music_id = _seed_user_asset(headers, session_id)

    # feedback 1-3: same positive signal, distinct keys
    for index in range(1, 4):
        response = _post_feedback(
            headers,
            _feedback_body(session_id, music_id, rating=5, features=("relaxing",)),
            f"sha256:fb-learn-{index}",
        )
        assert response.status_code == 201

    # 4th feedback carries a new feature so the learned profile changes
    fourth = _post_feedback(
        headers,
        _feedback_body(session_id, music_id, rating=5, features=("focus",)),
        "sha256:fb-learn-4",
    )
    update = _v3_data(fourth)["preference_update"]
    assert update["applied"] is True
    assert update["previous_version"] == 1
    assert update["new_version"] == 2
    assert "preferred_features" in update["changed_fields"]

    profile = _v3_data(
        client.get("/api/v3/me/preferences", headers=headers)
    )
    assert profile["version"] == 2
    assert profile["public_user_id"] == _public_user_id(
        headers["Authorization"].split()[1]
    )
    assert profile["learning"]["feedback_count"] == 4
    instrument_codes = {item["code"] for item in profile["preferred_instruments"]}
    assert "guqin" in instrument_codes
    feature_codes = {item["code"] for item in profile["preferred_features"]}
    assert {"relaxing", "focus"} <= feature_codes
    assert profile["preferred_bpm_range"] == {"min": 60, "max": 60, "weight": 1.0}


def test_cross_user_personal_data_is_isolated():
    owner_headers, owner_session = _setup_guest()
    music_id = _seed_user_asset(owner_headers, owner_session)
    _post_feedback(
        owner_headers,
        _feedback_body(owner_session, music_id, favorite=True),
        "sha256:fb-owner-1",
    )

    stranger_headers = _guest_headers()

    prefs = client.get("/api/v3/me/preferences", headers=stranger_headers)
    assert prefs.status_code == 404

    history = _v3_data(client.get("/api/v3/me/history", headers=stranger_headers))
    assert history["total"] == 0

    favorites = _v3_data(client.get("/api/v3/favorites", headers=stranger_headers))
    assert favorites["total"] == 0

    # stranger cannot submit feedback against the owner's session
    denied = _post_feedback(
        stranger_headers,
        _feedback_body(owner_session, music_id),
        "sha256:fb-stranger-1",
    )
    assert denied.status_code == 404

    # stranger cannot favorite the owner's private generated asset
    denied_fav = client.put(
        "/api/v3/favorites",
        headers=stranger_headers,
        json={"music_ref": {"music_id": music_id, "source_type": "matched"}},
    )
    assert denied_fav.status_code == 404


def test_comment_is_stored_as_hash_never_plaintext():
    headers, session_id = _setup_guest()
    music_id = _seed_user_asset(headers, session_id)
    secret = "this-is-a-secret-comment"
    response = _post_feedback(
        headers,
        _feedback_body(session_id, music_id, comment=secret),
        "sha256:fb-comment-1",
    )
    assert response.status_code == 201
    assert secret not in response.text

    with _seed_db() as session:
        fb = session.query(FeedbackRow).one()
        assert fb.comment_ciphertext.startswith("sha256:")
        assert fb.comment_ciphertext != secret


def test_feedback_music_ref_mismatch_is_rejected():
    headers, session_id = _setup_guest()
    music_id = _seed_user_asset(headers, session_id)
    response = _post_feedback(
        headers,
        _feedback_body(session_id, music_id, source_type="generated"),
        "sha256:fb-mismatch-1",
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_FEEDBACK"

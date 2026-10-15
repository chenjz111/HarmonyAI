"""Sprint 7 M1 / BE-2B (Issue #151): private music library API tests.

Covered acceptance items:

* owner A/B isolation, NULL owner, shared matched asset with the caller's own
  terminal task, several tasks for the caller and for another owner,
  failed/cancelled tasks and assets that never reached a terminal task;
* a succeeded-but-unplayed asset appears in history;
* real availability (expired / deleted / quarantined / missing / unsafe key) is
  identical for the list, the detail and the playback gate;
* static pagination has no duplicates and no omissions; a stale epoch, a tampered
  cursor, a cross-owner cursor and a cross-list cursor are all rejected;
* private-title create / update / clear with compare-and-swap, per-owner
  isolation, and a real concurrent lost-update check;
* playback idempotency, cross-asset conflict, max semantics and
  ``source_context_id`` authorization;
* the persisted history explanation is bound to an explicitly selected owned
  context, never to "the latest session";
* reading and managing a library performs 0 generation work and never mutates the
  stored asset title/checksum, and GET never writes playback/owner state.

Runs fully offline with synthetic rows, an isolated SQLite database and no
provider call.  Integration (Issue #150) owns ``main.py`` registration, so these
tests mount the routers on a local app instead of mutating the shared app object.
"""

import base64
import json
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.models.v3.feedback import Favorite
from backend.app.models.v3.identity import UserIdentity
from backend.app.models.v3.music import GenerationTask, MusicAsset
from backend.app.models.v3.music_library import (
    MusicLibraryState,
    MusicPlaybackEvent,
    OwnerMusicState,
)
from backend.app.routers.v3 import auth_router, feedback_router, music_library_router
from backend.app.routers.v3.transport import V3APIError, v3_api_error_handler
from backend.app.services.v3.music_library_access import (
    FeedbackContextUnavailable,
    LibraryAccessDenied,
    require_library_access,
    resolve_feedback_context,
)
from backend.app.services.v3.music_library_service import (
    TitleVersionConflict,
    owner_music_item,
    read_private_title,
    record_playback_event,
    update_private_title,
)
from backend.app.services.v3.owner_music_state_service import (
    advance_feedback_epoch,
    advance_library_epoch,
    feedback_evidence_epoch_for,
    library_epoch_for,
)


UTC = timezone.utc
CURSOR_SECRET = "synthetic-s7-cursor-secret-0123456789"
DEFAULT_INSTRUMENT = "\u7b1b"  # 笛
PRIVATE_TITLE = "\u6211\u7684\u7b2c\u4e00\u9996"  # 我的第一首
PRIVATE_TITLE_V2 = "\u7b2c\u4e8c\u7248"  # 第二版
STALE_WRITE_TITLE = "\u8fc7\u671f\u5199\u5165"  # 过期写入
NO_GENERATION_TITLE = "\u65e0\u751f\u6210"  # 无生成
ALIAS_A = "A \u7684\u540d\u5b57"  # A 的名字
ALIAS_B = "B \u7684\u540d\u5b57"  # B 的名字
CARD_FIELDS = {
    "music_id",
    "source_type",
    "default_title",
    "user_title",
    "display_title",
    "metadata_version",
    "playable_created_at",
    "last_played_at",
    "activity_at",
    "duration_seconds",
    "availability",
    "is_favorite",
    "primary_instrument_code",
    "primary_instrument_origin",
    "source_summary",
}


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True)
def cursor_signing_secret(monkeypatch):
    monkeypatch.setenv("HARMONY_LIBRARY_CURSOR_SECRET", CURSOR_SECRET)


@pytest.fixture(autouse=True)
def controlled_media_root(tmp_path, monkeypatch):
    root = tmp_path / "media"
    (root / "music").mkdir(parents=True)
    monkeypatch.setenv("HARMONY_MEDIA_ROOT", str(root))
    return root


def _build_client(session_factory) -> TestClient:
    api = FastAPI()
    api.add_exception_handler(V3APIError, v3_api_error_handler)
    api.include_router(auth_router.router, prefix="/api/v3")
    api.include_router(music_library_router.router, prefix="/api/v3")
    # The existing favorites authority is reused, not reimplemented, so the
    # cross-check test needs the real Agent 5 favorites routes mounted as well.
    api.include_router(feedback_router.router, prefix="/api/v3")

    def _override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    api.dependency_overrides[get_db] = _override_get_db
    return TestClient(api)


@pytest.fixture
def client(db_session_factory):
    with _build_client(db_session_factory) as test_client:
        yield test_client


@pytest.fixture
def concurrent_client(concurrent_api_database):
    session_factory, _engine = concurrent_api_database
    with _build_client(session_factory) as test_client:
        yield test_client


# --------------------------------------------------------------------------- helpers


def _payload(response) -> dict:
    body = response.json()
    assert body.get("ok") is True, body
    return body["data"]


def _error(response) -> dict:
    body = response.json()
    assert body.get("ok") is False, body
    return body["error"]


def _public_user_id(headers: dict[str, str]) -> str:
    token = headers["Authorization"].split()[1]
    payload = token.split(".")[1]
    padded = payload + "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))["sub"]


def _principal(client, session_factory) -> tuple[dict[str, str], int]:
    """Create a guest principal and return its headers plus internal user pk."""

    token = _payload(client.post("/api/v3/auth/guest"))["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    with session_factory() as db:
        identity = (
            db.query(UserIdentity)
            .filter(UserIdentity.public_user_id == _public_user_id(headers))
            .one()
        )
        return headers, identity.internal_user_pk


def _seed_user(db, openid: str) -> int:
    user = User(openid=openid)
    db.add(user)
    db.flush()
    return user.id


def _asset(
    music_id: str,
    *,
    owner: int | None,
    created_at: datetime,
    source_type: str = "matched",
    instrument: str | None = DEFAULT_INSTRUMENT,
    storage_key: str | None = None,
) -> MusicAsset:
    return MusicAsset(
        music_asset_id=music_id,
        owner_internal_user_pk=owner,
        generation_task_id=None,
        source_type=source_type,
        catalog_track_id=f"catalog-{music_id}",
        title="stored asset title",
        storage_key=storage_key if storage_key is not None else f"music/{music_id}.mp3",
        format="mp3",
        duration_seconds=240,
        checksum=f"sha256:{music_id:0<64}"[-71:],
        tone_profile_json=None,
        bpm=84,
        instruments_json=[instrument] if instrument else None,
        playable_status="ready",
        created_at=created_at,
        updated_at=created_at,
    )


def _task(
    task_id: str,
    *,
    owner: int,
    music_id: str | None,
    completed_at: datetime,
    status: str = "succeeded",
) -> GenerationTask:
    return GenerationTask(
        task_id=task_id,
        internal_user_pk=owner,
        session_row_id=owner,
        prescription_id=f"rx-{task_id}",
        idempotency_key=f"idem-{task_id}",
        status=status,
        provider="offline-fixture",
        provider_task_id=None,
        progress_value=100,
        progress_indeterminate=0,
        message_code="completed",
        fallback_applied=1 if status == "matched_fallback" else 0,
        fallback_reason_code="catalog_match" if status == "matched_fallback" else None,
        error_code=None,
        music_asset_id=music_id,
        created_at=completed_at,
        updated_at=completed_at,
        completed_at=completed_at,
    )


def _write_audio(root, music_id: str) -> str:
    (root / "music").mkdir(parents=True, exist_ok=True)
    (root / "music" / f"{music_id}.mp3").write_bytes(b"synthetic audio")
    return f"music/{music_id}.mp3"


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _history_ids(client, headers, **params) -> list[str]:
    response = client.get("/api/v3/me/music-assets", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return [item["music_id"] for item in _payload(response)["items"]]


# --------------------------------------------------------------------------- pagination


def test_history_pagination_is_complete_and_free_of_duplicates(
    client, db_session_factory, controlled_media_root
):
    headers, owner = _principal(client, db_session_factory)
    _other_headers, other = _principal(client, db_session_factory)
    with db_session_factory() as db:
        for index in range(5):
            music_id = f"music_p{index}"
            db.add(
                _asset(
                    music_id,
                    owner=owner,
                    created_at=datetime(2026, 10, 1 + index, 8, tzinfo=UTC),
                    storage_key=_write_audio(controlled_media_root, music_id),
                )
            )
        db.add(
            _asset(
                "music_foreign",
                owner=other,
                created_at=datetime(2026, 10, 20, 8, tzinfo=UTC),
            )
        )
        db.commit()

    first = client.get("/api/v3/me/music-assets", headers=headers, params={"limit": 2})
    assert first.status_code == 200, first.text
    page = _payload(first)
    assert [item["music_id"] for item in page["items"]] == ["music_p4", "music_p3"]
    assert page["has_more"] is True
    assert page["next_cursor"]

    collected = [item["music_id"] for item in page["items"]]
    cursor = page["next_cursor"]
    while cursor:
        response = client.get(
            "/api/v3/me/music-assets",
            headers=headers,
            params={"limit": 2, "cursor": cursor},
        )
        assert response.status_code == 200, response.text
        page = _payload(response)
        collected.extend(item["music_id"] for item in page["items"])
        cursor = page["next_cursor"]

    assert collected == ["music_p4", "music_p3", "music_p2", "music_p1", "music_p0"]
    assert len(set(collected)) == len(collected)
    assert "music_foreign" not in collected


def test_invalid_limit_is_rejected_with_a_stable_code(client, db_session_factory):
    headers, _owner = _principal(client, db_session_factory)
    for limit in (0, -1, 51):
        response = client.get(
            "/api/v3/me/music-assets", headers=headers, params={"limit": limit}
        )
        assert response.status_code == 400, response.text
        assert _error(response)["code"] == "INVALID_LIMIT"
    # A non-integer limit is a request-shape problem, not a range problem.
    assert (
        client.get(
            "/api/v3/me/music-assets", headers=headers, params={"limit": "abc"}
        ).status_code
        == 422
    )


def test_tampered_cursor_is_rejected(client, db_session_factory, controlled_media_root):
    headers, owner = _principal(client, db_session_factory)
    with db_session_factory() as db:
        for index in range(3):
            music_id = f"music_t{index}"
            db.add(
                _asset(
                    music_id,
                    owner=owner,
                    created_at=datetime(2026, 10, 1 + index, 8, tzinfo=UTC),
                    storage_key=_write_audio(controlled_media_root, music_id),
                )
            )
        db.commit()

    cursor = _payload(
        client.get("/api/v3/me/music-assets", headers=headers, params={"limit": 1})
    )["next_cursor"]
    assert cursor

    encoded, signature = cursor.split(".")
    forged = (
        base64.urlsafe_b64encode(
            json.dumps(
                {
                    "v": 1,
                    "o": owner,
                    "l": "history",
                    "e": 0,
                    "a": "2026-10-09T08:00:00+00:00",
                    "m": "music_t0",
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        .decode("ascii")
        .rstrip("=")
    )
    for bad in (f"{forged}.{signature}", f"{encoded}.{signature[:-2]}xx", "not-a-cursor"):
        response = client.get(
            "/api/v3/me/music-assets", headers=headers, params={"cursor": bad}
        )
        assert response.status_code == 400, response.text
        assert _error(response)["code"] == "INVALID_CURSOR"


def test_cursor_is_bound_to_owner_and_to_the_list(
    client, db_session_factory, controlled_media_root
):
    headers_a, owner_a = _principal(client, db_session_factory)
    headers_b, owner_b = _principal(client, db_session_factory)
    with db_session_factory() as db:
        for owner, prefix in ((owner_a, "a"), (owner_b, "b")):
            for index in range(3):
                music_id = f"music_{prefix}{index}"
                db.add(
                    _asset(
                        music_id,
                        owner=owner,
                        created_at=datetime(2026, 10, 1 + index, 8, tzinfo=UTC),
                        storage_key=_write_audio(controlled_media_root, music_id),
                    )
                )
        db.commit()

    cursor_a = _payload(
        client.get("/api/v3/me/music-assets", headers=headers_a, params={"limit": 1})
    )["next_cursor"]

    # Another owner cannot reuse it.
    response = client.get(
        "/api/v3/me/music-assets", headers=headers_b, params={"cursor": cursor_a}
    )
    assert response.status_code == 400
    assert _error(response)["code"] == "INVALID_CURSOR"

    # The same owner cannot reuse a history cursor on the favorites list.
    response = client.get(
        "/api/v3/me/music-favorites", headers=headers_a, params={"cursor": cursor_a}
    )
    assert response.status_code == 400
    assert _error(response)["code"] == "INVALID_CURSOR"


def test_stale_cursor_after_epoch_bump_and_fail_closed_signing(
    client, db_session_factory, controlled_media_root, monkeypatch
):
    headers, owner = _principal(client, db_session_factory)
    with db_session_factory() as db:
        for index in range(3):
            music_id = f"music_e{index}"
            db.add(
                _asset(
                    music_id,
                    owner=owner,
                    created_at=datetime(2026, 10, 1 + index, 8, tzinfo=UTC),
                    storage_key=_write_audio(controlled_media_root, music_id),
                )
            )
        db.commit()

    cursor = _payload(
        client.get("/api/v3/me/music-assets", headers=headers, params={"limit": 1})
    )["next_cursor"]

    # Reading never creates owner state: the epoch stays at its implicit 0.
    with db_session_factory() as db:
        assert library_epoch_for(db, internal_user_pk=owner) == 0
        assert db.query(OwnerMusicState).count() == 0
        assert advance_library_epoch(db, internal_user_pk=owner) == 1
        db.commit()

    response = client.get(
        "/api/v3/me/music-assets", headers=headers, params={"cursor": cursor}
    )
    assert response.status_code == 409
    error = _error(response)
    assert error["code"] == "LIBRARY_CURSOR_STALE"
    assert error["retryable"] is True
    assert error["next_actions"] == ["refetch_first_page"]

    # No unsigned fallback: without signing configuration the paged read fails closed.
    monkeypatch.delenv("HARMONY_LIBRARY_CURSOR_SECRET")
    response = client.get("/api/v3/me/music-assets", headers=headers)
    assert response.status_code == 503
    assert _error(response)["code"] == "LIBRARY_CURSOR_UNAVAILABLE"


# --------------------------------------------------------------------------- authorization


def test_other_owner_asset_is_never_reachable(
    client, db_session_factory, controlled_media_root
):
    headers, _intruder = _principal(client, db_session_factory)
    _victim_headers, victim = _principal(client, db_session_factory)
    with db_session_factory() as db:
        db.add(
            _asset(
                "music_victim",
                owner=victim,
                created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_victim"),
            )
        )
        db.add(
            _task(
                "task-victim",
                owner=victim,
                music_id="music_victim",
                completed_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
            )
        )
        db.commit()

    for response in (
        client.get("/api/v3/music/assets/music_victim", headers=headers),
        client.patch(
            "/api/v3/music/assets/music_victim/title",
            headers=headers,
            json={"user_title": "stolen", "expected_version": 0},
        ),
        client.post(
            "/api/v3/music/assets/music_victim/playback-events",
            headers=headers,
            json={"event_id": "evt-intruder", "event_type": "play_started"},
        ),
    ):
        assert response.status_code == 404, response.text
        assert _error(response)["code"] == "RESOURCE_NOT_FOUND"

    with db_session_factory() as db:
        assert (
            db.query(MusicLibraryState)
            .filter(MusicLibraryState.music_asset_id == "music_victim")
            .count()
            == 0
        )
        assert db.query(MusicPlaybackEvent).count() == 0
    assert _history_ids(client, headers) == []


def test_null_owner_and_favorite_alone_do_not_grant_access(
    client, db_session_factory, controlled_media_root
):
    headers, owner = _principal(client, db_session_factory)
    with db_session_factory() as db:
        db.add(
            _asset(
                "music_shared",
                owner=None,
                created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_shared"),
            )
        )
        db.flush()
        db.add(
            Favorite(
                favorite_id="fav-shared",
                internal_user_pk=owner,
                music_asset_id="music_shared",
            )
        )
        db.commit()

    assert _history_ids(client, headers) == []
    detail = client.get("/api/v3/music/assets/music_shared", headers=headers)
    assert detail.status_code == 404
    favorites = _payload(client.get("/api/v3/me/music-favorites", headers=headers))
    assert favorites["items"] == []

    # The caller's own terminal task does grant access.
    with db_session_factory() as db:
        db.add(
            _task(
                "task-shared",
                owner=owner,
                music_id="music_shared",
                completed_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                status="matched_fallback",
            )
        )
        db.commit()

    assert _history_ids(client, headers) == ["music_shared"]
    detail = client.get("/api/v3/music/assets/music_shared", headers=headers)
    assert detail.status_code == 200
    assert _payload(detail)["card"]["source_type"] == "matched"
    favorites = _payload(client.get("/api/v3/me/music-favorites", headers=headers))
    assert [item["music_id"] for item in favorites["items"]] == ["music_shared"]


def test_failed_and_cancelled_tasks_and_absent_assets_stay_out_of_history(
    client, db_session_factory, controlled_media_root
):
    headers, owner = _principal(client, db_session_factory)
    with db_session_factory() as db:
        db.add(
            _asset(
                "music_ok",
                owner=None,
                created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_ok"),
            )
        )
        db.add(
            _asset(
                "music_orphan",
                owner=None,
                created_at=datetime(2026, 10, 13, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_orphan"),
            )
        )
        db.flush()
        db.add_all(
            [
                _task(
                    "task-ok",
                    owner=owner,
                    music_id="music_ok",
                    completed_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                ),
                _task(
                    "task-failed",
                    owner=owner,
                    music_id=None,
                    completed_at=datetime(2026, 10, 11, 8, tzinfo=UTC),
                    status="failed",
                ),
                _task(
                    "task-cancelled",
                    owner=owner,
                    music_id=None,
                    completed_at=datetime(2026, 10, 11, 9, tzinfo=UTC),
                    status="cancelled",
                ),
            ]
        )
        db.commit()

    assert _history_ids(client, headers) == ["music_ok"]


# --------------------------------------------------------------------------- availability


@pytest.mark.parametrize(
    "stored_status,expired,expected",
    [
        ("deleted", False, "deleted"),
        ("quarantined", False, "quarantined"),
        ("ready", True, "expired"),
        ("ready", False, "ready"),
    ],
)
def test_list_detail_and_playback_agree_on_availability(
    client,
    db_session_factory,
    controlled_media_root,
    stored_status,
    expired,
    expected,
):
    headers, owner = _principal(client, db_session_factory)
    with db_session_factory() as db:
        asset = _asset(
            "music_avail",
            owner=owner,
            created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
            storage_key=_write_audio(controlled_media_root, "music_avail"),
        )
        asset.playable_status = stored_status
        if expired:
            asset.retention_expires_at = datetime(2020, 1, 1, tzinfo=UTC)
        db.add(asset)
        db.commit()

    listed = _payload(client.get("/api/v3/me/music-assets", headers=headers))["items"]
    assert listed[0]["availability"] == expected

    detail = _payload(client.get("/api/v3/music/assets/music_avail", headers=headers))
    assert detail["audio"]["availability"] == expected

    playback = client.post(
        "/api/v3/music/assets/music_avail/playback-events",
        headers=headers,
        json={"event_id": f"evt-{expected}", "event_type": "play_started"},
    )
    if expected == "ready":
        assert playback.status_code == 201, playback.text
    else:
        assert playback.status_code == 404
        assert _error(playback)["code"] == "RESOURCE_NOT_AVAILABLE"


@pytest.mark.parametrize(
    "storage_key",
    ["../outside.mp3", "https://example.invalid/a.mp3", "bad\x00key", "  "],
)
def test_unsafe_locators_are_missing_not_ready(
    client, db_session_factory, controlled_media_root, storage_key
):
    headers, owner = _principal(client, db_session_factory)
    (controlled_media_root.parent / "outside.mp3").write_bytes(b"private")
    with db_session_factory() as db:
        asset = _asset(
            "music_unsafe",
            owner=owner,
            created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
        )
        asset.storage_key = storage_key
        db.add(asset)
        db.commit()

    listed = _payload(client.get("/api/v3/me/music-assets", headers=headers))["items"]
    assert listed[0]["availability"] == "missing"
    detail = _payload(client.get("/api/v3/music/assets/music_unsafe", headers=headers))
    assert detail["audio"]["availability"] == "missing"


# --------------------------------------------------------------------------- detail / context


def test_detail_requires_explicit_context_and_uses_persisted_facts(
    client, db_session_factory, controlled_media_root
):
    headers, owner = _principal(client, db_session_factory)
    _other_headers, other = _principal(client, db_session_factory)
    with db_session_factory() as db:
        db.add(
            _asset(
                "music_ctx",
                owner=owner,
                created_at=datetime(2026, 10, 10, 6, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_ctx"),
            )
        )
        db.add_all(
            [
                _task(
                    "task-early",
                    owner=owner,
                    music_id="music_ctx",
                    completed_at=datetime(2026, 10, 11, 8, tzinfo=UTC),
                ),
                _task(
                    "task-late",
                    owner=owner,
                    music_id="music_ctx",
                    completed_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                    status="matched_fallback",
                ),
                _task(
                    "task-foreign",
                    owner=other,
                    music_id="music_ctx",
                    completed_at=datetime(2026, 10, 13, 8, tzinfo=UTC),
                ),
            ]
        )
        db.commit()

    plain = _payload(client.get("/api/v3/music/assets/music_ctx", headers=headers))
    # No context requested -> nothing is silently selected.
    assert plain["selected_context_id"] is None
    assert plain["history_explanation"] is None
    assert [item["context_id"] for item in plain["source_contexts"]] == [
        "task-early",
        "task-late",
    ]
    assert plain["card"]["last_played_at"] is None
    assert _utc(plain["card"]["activity_at"]) == datetime(2026, 10, 11, 8, tzinfo=UTC)
    # Duration stays unknown: W2 has no persisted measurement provenance.
    assert plain["card"]["duration_seconds"] is None
    assert plain["audio"]["duration_seconds"] is None
    assert plain["audio"]["format"] == "mp3"

    selected = _payload(
        client.get(
            "/api/v3/music/assets/music_ctx",
            headers=headers,
            params={"context_id": "task-early"},
        )
    )
    assert selected["selected_context_id"] == "task-early"
    explanation = selected["history_explanation"]
    assert explanation["context_id"] == "task-early"
    assert explanation["task_status"] == "succeeded"
    assert explanation["source_type"] == "generated"
    assert explanation["fallback_applied"] is False
    assert _utc(explanation["completed_at"]) == datetime(2026, 10, 11, 8, tzinfo=UTC)
    assert explanation["prescription_id"] == "rx-task-early"

    # The other owner's task is not even offered as a choice.
    for bad_context in ("task-foreign", "task-unknown"):
        response = client.get(
            "/api/v3/music/assets/music_ctx",
            headers=headers,
            params={"context_id": bad_context},
        )
        assert response.status_code == 422, response.text
        assert _error(response)["code"] == "CONTEXT_NOT_AVAILABLE"


def test_card_shape_and_measured_duration_stay_contract_exact(
    client, db_session_factory, controlled_media_root
):
    headers, owner = _principal(client, db_session_factory)
    with db_session_factory() as db:
        db.add(
            _asset(
                "music_card",
                owner=owner,
                created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_card"),
            )
        )
        db.commit()
        checksum = (
            db.query(MusicAsset)
            .filter(MusicAsset.music_asset_id == "music_card")
            .one()
            .checksum
        )

    card = _payload(client.get("/api/v3/me/music-assets", headers=headers))["items"][0]
    assert set(card) == CARD_FIELDS
    # The legacy generation target is never reported as a measured duration.
    assert card["duration_seconds"] is None
    assert card["user_title"] is None
    assert card["metadata_version"] == 0
    assert card["display_title"] == card["default_title"]
    assert card["source_summary"]["context_count"] == 0
    with db_session_factory() as db:
        assert (
            db.query(MusicAsset)
            .filter(MusicAsset.music_asset_id == "music_card")
            .one()
            .checksum
            == checksum
        )


# --------------------------------------------------------------------------- private title


def test_private_title_create_update_clear_and_checksum_is_untouched(
    client, db_session_factory, controlled_media_root
):
    headers, owner = _principal(client, db_session_factory)
    with db_session_factory() as db:
        db.add(
            _asset(
                "music_title",
                owner=owner,
                created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_title"),
            )
        )
        db.commit()
        row = (
            db.query(MusicAsset)
            .filter(MusicAsset.music_asset_id == "music_title")
            .one()
        )
        stored_title, stored_checksum = row.title, row.checksum

    created = client.patch(
        "/api/v3/music/assets/music_title/title",
        headers=headers,
        json={"user_title": f"  {PRIVATE_TITLE}  ", "expected_version": 0},
    )
    assert created.status_code == 200, created.text
    state = _payload(created)
    assert state["user_title"] == PRIVATE_TITLE
    assert state["display_title"] == PRIVATE_TITLE
    assert state["metadata_version"] == 1

    listed = _payload(client.get("/api/v3/me/music-assets", headers=headers))["items"][0]
    assert listed["user_title"] == PRIVATE_TITLE
    assert listed["display_title"] == PRIVATE_TITLE
    assert listed["metadata_version"] == 1

    updated = _payload(
        client.patch(
            "/api/v3/music/assets/music_title/title",
            headers=headers,
            json={"user_title": PRIVATE_TITLE_V2, "expected_version": 1},
        )
    )
    assert updated["user_title"] == PRIVATE_TITLE_V2
    assert updated["metadata_version"] == 2

    # A stale expected_version must not overwrite a newer value.
    conflict = client.patch(
        "/api/v3/music/assets/music_title/title",
        headers=headers,
        json={"user_title": STALE_WRITE_TITLE, "expected_version": 1},
    )
    assert conflict.status_code == 409
    assert _error(conflict)["code"] == "TITLE_VERSION_CONFLICT"

    cleared = _payload(
        client.patch(
            "/api/v3/music/assets/music_title/title",
            headers=headers,
            json={"user_title": None, "expected_version": 2},
        )
    )
    assert cleared["user_title"] is None
    assert cleared["display_title"] == listed["default_title"]
    assert cleared["metadata_version"] == 3

    with db_session_factory() as db:
        row = (
            db.query(MusicAsset)
            .filter(MusicAsset.music_asset_id == "music_title")
            .one()
        )
        # The private alias never rewrites the stored asset title or its checksum.
        assert row.title == stored_title
        assert row.checksum == stored_checksum


@pytest.mark.parametrize(
    "payload",
    [
        {"user_title": "   ", "expected_version": 0},
        {"user_title": "x" * 121, "expected_version": 0},
        {"user_title": "bad\nnewline", "expected_version": 0},
        {"user_title": "tab\there", "expected_version": 0},
        {"user_title": None, "expected_version": -1},
        {"expected_version": 0},
        {"user_title": "ok", "expected_version": 0, "unexpected": True},
    ],
)
def test_private_title_rejects_unsafe_payloads(
    client, db_session_factory, controlled_media_root, payload
):
    headers, owner = _principal(client, db_session_factory)
    with db_session_factory() as db:
        db.add(
            _asset(
                "music_badt",
                owner=owner,
                created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_badt"),
            )
        )
        db.commit()

    response = client.patch(
        "/api/v3/music/assets/music_badt/title", headers=headers, json=payload
    )
    assert response.status_code == 422, response.text


def test_private_title_is_not_shared_between_owners(
    concurrent_client, concurrent_api_database, controlled_media_root
):
    session_factory, _engine = concurrent_api_database
    headers_a, owner_a = _principal(concurrent_client, session_factory)
    headers_b, owner_b = _principal(concurrent_client, session_factory)
    with session_factory() as db:
        db.add(
            _asset(
                "music_alias",
                owner=None,
                created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_alias"),
            )
        )
        db.add_all(
            [
                _task(
                    "task-alias-a",
                    owner=owner_a,
                    music_id="music_alias",
                    completed_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                ),
                _task(
                    "task-alias-b",
                    owner=owner_b,
                    music_id="music_alias",
                    completed_at=datetime(2026, 10, 12, 9, tzinfo=UTC),
                ),
            ]
        )
        db.commit()

    a_write = concurrent_client.patch(
        "/api/v3/music/assets/music_alias/title",
        headers=headers_a,
        json={"user_title": ALIAS_A, "expected_version": 0},
    )
    assert a_write.status_code == 200, a_write.text

    b_view = _payload(
        concurrent_client.get("/api/v3/music/assets/music_alias", headers=headers_b)
    )
    assert b_view["card"]["user_title"] is None
    assert b_view["card"]["metadata_version"] == 0

    b_write = concurrent_client.patch(
        "/api/v3/music/assets/music_alias/title",
        headers=headers_b,
        json={"user_title": ALIAS_B, "expected_version": 0},
    )
    assert b_write.status_code == 200, b_write.text

    a_view = _payload(
        concurrent_client.get("/api/v3/music/assets/music_alias", headers=headers_a)
    )
    assert a_view["card"]["user_title"] == ALIAS_A
    assert a_view["card"]["metadata_version"] == 1

    with session_factory() as db:
        assert db.query(MusicLibraryState).count() == 2

    # The shared stored asset title is still the untouched original.
    with session_factory() as db:
        row = (
            db.query(MusicAsset)
            .filter(MusicAsset.music_asset_id == "music_alias")
            .one()
        )
        assert row.title == "stored asset title"


def test_concurrent_private_title_cas_loses_no_update(
    concurrent_api_database, controlled_media_root
):
    session_factory, _engine = concurrent_api_database
    with session_factory() as setup:
        owner_id = _seed_user(setup, "cas-owner")
        setup.add(
            _asset(
                "music_cas",
                owner=owner_id,
                created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_cas"),
            )
        )
        setup.commit()

    with session_factory() as first, session_factory() as second:
        first_asset = first.query(MusicAsset).filter_by(music_asset_id="music_cas").one()
        second_asset = (
            second.query(MusicAsset).filter_by(music_asset_id="music_cas").one()
        )
        # Both writers observe the same version before either commits.
        assert (
            read_private_title(
                first, internal_user_pk=owner_id, asset=first_asset
            ).metadata_version
            == 0
        )
        assert (
            read_private_title(
                second, internal_user_pk=owner_id, asset=second_asset
            ).metadata_version
            == 0
        )

        update_private_title(
            first,
            internal_user_pk=owner_id,
            asset=first_asset,
            user_title="winner",
            expected_version=0,
        )
        first.commit()

        with pytest.raises(TitleVersionConflict):
            update_private_title(
                second,
                internal_user_pk=owner_id,
                asset=second_asset,
                user_title="loser",
                expected_version=0,
            )

    with session_factory() as verify:
        row = (
            verify.query(MusicLibraryState)
            .filter(MusicLibraryState.music_asset_id == "music_cas")
            .one()
        )
        assert row.user_title == "winner"
        assert row.metadata_version == 1

    # The same CAS guard protects an existing sidecar row.
    with session_factory() as third, session_factory() as fourth:
        third_asset = third.query(MusicAsset).filter_by(music_asset_id="music_cas").one()
        update_private_title(
            third,
            internal_user_pk=owner_id,
            asset=third_asset,
            user_title="v2",
            expected_version=1,
        )
        third.commit()
        fourth_asset = (
            fourth.query(MusicAsset).filter_by(music_asset_id="music_cas").one()
        )
        with pytest.raises(TitleVersionConflict):
            update_private_title(
                fourth,
                internal_user_pk=owner_id,
                asset=fourth_asset,
                user_title="stale",
                expected_version=1,
            )


# --------------------------------------------------------------------------- playback


def test_playback_event_is_idempotent_per_owner_and_conflicts_across_assets(
    client, db_session_factory, controlled_media_root
):
    headers, owner = _principal(client, db_session_factory)
    with db_session_factory() as db:
        for music_id in ("music_play1", "music_play2"):
            db.add(
                _asset(
                    music_id,
                    owner=owner,
                    created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                    storage_key=_write_audio(controlled_media_root, music_id),
                )
            )
        db.commit()

    first = client.post(
        "/api/v3/music/assets/music_play1/playback-events",
        headers=headers,
        json={"event_id": "evt-1", "event_type": "play_started"},
    )
    assert first.status_code == 201, first.text
    created = _payload(first)
    assert created["replayed"] is False
    assert created["event_type"] == "play_started"
    assert created["last_played_at"] == created["occurred_at"]

    replay = client.post(
        "/api/v3/music/assets/music_play1/playback-events",
        headers=headers,
        json={"event_id": "evt-1", "event_type": "play_started"},
    )
    assert replay.status_code == 200, replay.text
    replayed = _payload(replay)
    assert replayed["replayed"] is True
    assert replayed["occurred_at"] == created["occurred_at"]
    assert replayed["last_played_at"] == created["last_played_at"]

    with db_session_factory() as db:
        assert db.query(MusicPlaybackEvent).count() == 1

    # The same owner-scoped event id for another asset is a conflict.
    conflict = client.post(
        "/api/v3/music/assets/music_play2/playback-events",
        headers=headers,
        json={"event_id": "evt-1", "event_type": "play_started"},
    )
    assert conflict.status_code == 409
    assert _error(conflict)["code"] == "PLAYBACK_EVENT_CONFLICT"

    # A real play moves the card to the top and updates activity/last_played.
    listed = _payload(client.get("/api/v3/me/music-assets", headers=headers))["items"]
    assert listed[0]["music_id"] == "music_play1"
    assert listed[0]["last_played_at"] == created["occurred_at"]
    assert listed[0]["activity_at"] == created["occurred_at"]

    # Only play_started is a play; page view / prefetch / seek are rejected.
    for bad_type in ("page_view", "prefetch", "seek", "play_completed"):
        response = client.post(
            "/api/v3/music/assets/music_play1/playback-events",
            headers=headers,
            json={"event_id": f"evt-{bad_type}", "event_type": bad_type},
        )
        assert response.status_code == 422, response.text


def test_playback_requires_owned_ready_asset_and_owned_context(
    client, db_session_factory, controlled_media_root
):
    headers, owner = _principal(client, db_session_factory)
    _other_headers, other = _principal(client, db_session_factory)
    with db_session_factory() as db:
        db.add(
            _asset(
                "music_playctx",
                owner=None,
                created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_playctx"),
            )
        )
        db.add_all(
            [
                _task(
                    "task-own-ctx",
                    owner=owner,
                    music_id="music_playctx",
                    completed_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                ),
                _task(
                    "task-other-ctx",
                    owner=other,
                    music_id="music_playctx",
                    completed_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                ),
            ]
        )
        db.commit()

    foreign_context = client.post(
        "/api/v3/music/assets/music_playctx/playback-events",
        headers=headers,
        json={
            "event_id": "evt-ctx",
            "event_type": "play_started",
            "source_context_id": "task-other-ctx",
        },
    )
    assert foreign_context.status_code == 422, foreign_context.text
    assert _error(foreign_context)["code"] == "CONTEXT_NOT_AVAILABLE"

    owned_context = client.post(
        "/api/v3/music/assets/music_playctx/playback-events",
        headers=headers,
        json={
            "event_id": "evt-ctx",
            "event_type": "play_started",
            "source_context_id": "task-own-ctx",
        },
    )
    assert owned_context.status_code == 201, owned_context.text

    with db_session_factory() as db:
        row = db.query(MusicPlaybackEvent).one()
        assert row.source_context_id == "task-own-ctx"


def test_playback_last_played_is_the_maximum_not_the_last_writer(
    concurrent_api_database, controlled_media_root
):
    session_factory, _engine = concurrent_api_database
    with session_factory() as setup:
        owner_id = _seed_user(setup, "play-max-owner")
        setup.add(
            _asset(
                "music_max",
                owner=owner_id,
                created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_max"),
            )
        )
        setup.commit()

    early = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)
    late = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)

    # A later event is committed first, then an earlier one is written afterwards.
    with session_factory() as db:
        asset = db.query(MusicAsset).filter_by(music_asset_id="music_max").one()
        record_playback_event(
            db,
            internal_user_pk=owner_id,
            asset=asset,
            context_ids=(),
            event_id="evt-late",
            event_type="play_started",
            source_context_id=None,
            now=late,
        )
        db.commit()

    with session_factory() as db:
        asset = db.query(MusicAsset).filter_by(music_asset_id="music_max").one()
        result = record_playback_event(
            db,
            internal_user_pk=owner_id,
            asset=asset,
            context_ids=(),
            event_id="evt-early",
            event_type="play_started",
            source_context_id=None,
            now=early,
        )
        # The write response already reflects the maximum, not the new event.
        assert result.occurred_at == early
        assert result.last_played_at == late
        db.commit()

    with session_factory() as verify:
        item = owner_music_item(verify, internal_user_pk=owner_id, music_id="music_max")
        assert item is not None
        assert item.card.last_played_at == late
        assert item.card.activity_at == late
        assert verify.query(MusicPlaybackEvent).count() == 2


def test_resolve_feedback_context_needs_a_real_play_and_an_explicit_context(
    db_session_factory, controlled_media_root
):
    with db_session_factory() as db:
        owner_id = _seed_user(db, "feedback-ctx-owner")
        other_id = _seed_user(db, "feedback-ctx-other")
        db.add(
            _asset(
                "music_fb",
                owner=None,
                created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_fb"),
            )
        )
        db.add(
            _task(
                "task-fb",
                owner=owner_id,
                music_id="music_fb",
                completed_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
            )
        )
        db.commit()

        # Membership alone is not enough: no play, no context.
        with pytest.raises(FeedbackContextUnavailable):
            resolve_feedback_context(
                db, internal_user_pk=owner_id, music_id="music_fb", context_id="task-fb"
            )
        # No explicit context is never inferred.
        with pytest.raises(FeedbackContextUnavailable):
            resolve_feedback_context(
                db, internal_user_pk=owner_id, music_id="music_fb", context_id=None
            )
        # Another owner cannot resolve a context on this asset.
        with pytest.raises(LibraryAccessDenied):
            resolve_feedback_context(
                db, internal_user_pk=other_id, music_id="music_fb", context_id="task-fb"
            )

        db.add(
            MusicPlaybackEvent(
                internal_user_pk=owner_id,
                event_id="evt-fb",
                music_asset_id="music_fb",
                event_type="play_started",
                source_context_id=None,
                occurred_at=datetime(2026, 10, 12, 9, tzinfo=UTC),
            )
        )
        db.commit()

        assert (
            resolve_feedback_context(
                db, internal_user_pk=owner_id, music_id="music_fb", context_id="task-fb"
            )
            == "task-fb"
        )
        with pytest.raises(FeedbackContextUnavailable):
            resolve_feedback_context(
                db,
                internal_user_pk=owner_id,
                music_id="music_fb",
                context_id="task-unknown",
            )


# --------------------------------------------------------------------------- favorites


def test_favorites_page_reuses_the_existing_favorite_authority(
    client, db_session_factory, controlled_media_root
):
    headers, owner = _principal(client, db_session_factory)
    with db_session_factory() as db:
        db.add(
            _asset(
                "music_fav",
                owner=owner,
                created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_fav"),
            )
        )
        db.add(
            _asset(
                "music_fav_orphan",
                owner=None,
                created_at=datetime(2026, 10, 13, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_fav_orphan"),
            )
        )
        db.commit()

    assert (
        _payload(client.get("/api/v3/me/music-favorites", headers=headers))["items"] == []
    )

    added = client.put(
        "/api/v3/favorites",
        headers=headers,
        json={"music_ref": {"music_id": "music_fav", "source_type": "matched"}},
    )
    assert added.status_code == 200, added.text

    favorites = _payload(client.get("/api/v3/me/music-favorites", headers=headers))
    assert [item["music_id"] for item in favorites["items"]] == ["music_fav"]
    assert favorites["items"][0]["is_favorite"] is True

    # The existing favorites authority and the library view agree.
    existing = _payload(client.get("/api/v3/favorites", headers=headers))
    assert [item["music_ref"]["music_id"] for item in existing["items"]] == ["music_fav"]

    # A favorite on an asset the caller cannot access is never listed.
    with db_session_factory() as db:
        db.add(
            Favorite(
                favorite_id="fav-orphan",
                internal_user_pk=owner,
                music_asset_id="music_fav_orphan",
            )
        )
        db.commit()
    favorites = _payload(client.get("/api/v3/me/music-favorites", headers=headers))
    assert [item["music_id"] for item in favorites["items"]] == ["music_fav"]

    removed = client.delete("/api/v3/favorites/music_fav", headers=headers)
    assert removed.status_code == 200, removed.text
    assert (
        _payload(client.get("/api/v3/me/music-favorites", headers=headers))["items"] == []
    )


# --------------------------------------------------------------------------- no side effects


def test_library_reads_and_management_never_generate(
    client, db_session_factory, controlled_media_root, monkeypatch
):
    headers, owner = _principal(client, db_session_factory)
    with db_session_factory() as db:
        db.add(
            _asset(
                "music_nogen",
                owner=owner,
                created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_nogen"),
            )
        )
        db.commit()

    def _forbidden_provider():
        raise AssertionError("library operations must not build a music provider")

    import backend.app.routers.v3.generation_router as generation_router

    monkeypatch.setattr(generation_router, "get_music_provider", _forbidden_provider)

    with db_session_factory() as db:
        before = db.query(GenerationTask).count()

    client.get("/api/v3/me/music-assets", headers=headers)
    client.get("/api/v3/me/music-favorites", headers=headers)
    client.get("/api/v3/music/assets/music_nogen", headers=headers)
    client.patch(
        "/api/v3/music/assets/music_nogen/title",
        headers=headers,
        json={"user_title": NO_GENERATION_TITLE, "expected_version": 0},
    )
    client.post(
        "/api/v3/music/assets/music_nogen/playback-events",
        headers=headers,
        json={"event_id": "evt-nogen", "event_type": "play_started"},
    )

    with db_session_factory() as db:
        assert db.query(GenerationTask).count() == before


def test_get_requests_do_not_write_owner_state_or_playback(
    client, db_session_factory, controlled_media_root
):
    headers, owner = _principal(client, db_session_factory)
    with db_session_factory() as db:
        db.add(
            _asset(
                "music_readonly",
                owner=owner,
                created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_readonly"),
            )
        )
        db.commit()

    for _ in range(2):
        client.get("/api/v3/me/music-assets", headers=headers)
        client.get("/api/v3/me/music-favorites", headers=headers)
        client.get("/api/v3/music/assets/music_readonly", headers=headers)

    with db_session_factory() as db:
        assert db.query(MusicPlaybackEvent).count() == 0
        assert db.query(OwnerMusicState).count() == 0
        assert db.query(MusicLibraryState).count() == 0


def test_epoch_hooks_participate_in_the_callers_transaction(
    db_session_factory, controlled_media_root
):
    with db_session_factory() as db:
        owner_id = _seed_user(db, "epoch-hook-owner")
        db.commit()

    with db_session_factory() as db:
        assert advance_feedback_epoch(db, internal_user_pk=owner_id) == 1
        assert advance_feedback_epoch(db, internal_user_pk=owner_id) == 2
        # No commit here: the caller decides, so a rollback must undo everything.
        db.rollback()

    with db_session_factory() as db:
        assert feedback_evidence_epoch_for(db, internal_user_pk=owner_id) == 0
        assert library_epoch_for(db, internal_user_pk=owner_id) == 0
        assert db.query(OwnerMusicState).count() == 0

        assert advance_library_epoch(db, internal_user_pk=owner_id) == 1
        # A second bump inside the same transaction still works.
        assert advance_library_epoch(db, internal_user_pk=owner_id) == 2
        db.commit()

    with db_session_factory() as db:
        assert library_epoch_for(db, internal_user_pk=owner_id) == 2


def test_membership_requires_a_direct_owner_or_the_callers_own_terminal_task(
    db_session_factory, controlled_media_root
):
    with db_session_factory() as db:
        intruder_id = _seed_user(db, "service-intruder")
        victim_id = _seed_user(db, "service-victim")
        db.add(
            _asset(
                "music_service",
                owner=victim_id,
                created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                storage_key=_write_audio(controlled_media_root, "music_service"),
            )
        )
        db.add(
            _task(
                "task-service-victim",
                owner=victim_id,
                music_id="music_service",
                completed_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
            )
        )
        db.commit()

        with pytest.raises(LibraryAccessDenied):
            require_library_access(
                db, internal_user_pk=intruder_id, music_id="music_service"
            )
        access = require_library_access(
            db, internal_user_pk=victim_id, music_id="music_service"
        )
        assert access.access_sources == ("direct_owner", "owner_task")
        assert access.context_ids == ("task-service-victim",)

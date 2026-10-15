import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.models.user import User
from backend.app.models.v3.feedback import Favorite
from backend.app.models.v3.music import GenerationTask, MusicAsset
from backend.app.schemas.v3.music_library import MusicCardV1
from backend.app.services.v3.music_library_service import list_owner_music_history


UTC = timezone.utc


@pytest.fixture(autouse=True)
def controlled_media_root(tmp_path, monkeypatch):
    root = tmp_path / "media"
    root.mkdir()
    (root / "music").mkdir()
    (root / "music" / "music_shared.mp3").write_bytes(b"fixture audio")
    monkeypatch.setenv("HARMONY_MEDIA_ROOT", str(root))
    return root


@pytest.mark.parametrize("key,expected", [
    ("readable.mp3", "ready"), ("absent.mp3", "missing"),
    ("", "missing"), (None, "missing"),
    ("../outside.mp3", "missing"), ("https://example.invalid/a.mp3", "missing"),
    ("folder", "missing"), ("bad\x00key", "missing"),
])
def test_availability_checks_real_local_file(controlled_media_root, key, expected):
    from backend.app.services.v3.music_library_service import _availability
    (controlled_media_root / "readable.mp3").write_bytes(b"audio")
    (controlled_media_root / "folder").mkdir()
    (controlled_media_root.parent / "outside.mp3").write_bytes(b"private")
    asset = _asset("a", owner=1, created_at=datetime(2026, 10, 12, tzinfo=UTC))
    asset.storage_key = key
    assert _availability(asset, now=datetime(2026, 10, 14, tzinfo=UTC)) == expected


def test_availability_handles_windows_read_denial(controlled_media_root, monkeypatch):
    from backend.app.services.v3.music_library_service import _availability
    target = controlled_media_root / "denied.mp3"
    target.write_bytes(b"audio")
    original = Path.open
    def denied(path, *args, **kwargs):
        if path.resolve() == target.resolve():
            raise PermissionError("controlled Windows read denial")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", denied)
    asset = _asset("a", owner=1, created_at=datetime(2026, 10, 12, tzinfo=UTC))
    asset.storage_key = str(target)
    assert _availability(asset, now=datetime(2026, 10, 14, tzinfo=UTC)) == "missing"


def test_absolute_media_path_is_readable_but_absolute_outside_is_denied(controlled_media_root):
    from backend.app.services.v3.music_library_service import _availability
    asset = _asset("a", owner=1, created_at=datetime(2026, 10, 12, tzinfo=UTC))
    for target, expected in ((controlled_media_root / "a.mp3", "ready"),
                             (controlled_media_root.parent / "outside.mp3", "missing")):
        target.write_bytes(b"audio")
        asset.storage_key = str(target)
        assert _availability(asset, now=datetime(2026, 10, 14, tzinfo=UTC)) == expected


def test_symlink_escape_is_not_read(controlled_media_root, monkeypatch):
    from backend.app.services.v3.music_library_service import _availability
    outside = controlled_media_root.parent / "private.mp3"
    outside.write_bytes(b"private")
    link = controlled_media_root / "escape.mp3"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Windows symlink creation privilege unavailable")
    original = Path.open
    def no_outside_read(path, *args, **kwargs):
        if path.resolve() == outside.resolve():
            pytest.fail("outside audio was opened")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", no_outside_read)
    asset = _asset("a", owner=1, created_at=datetime(2026, 10, 12, tzinfo=UTC))
    asset.storage_key = str(link)
    assert _availability(asset, now=datetime(2026, 10, 14, tzinfo=UTC)) == "missing"


@pytest.mark.parametrize("status", ["failed", "cancelled"])
def test_failed_or_cancelled_tasks_do_not_grant_history(db_session_factory, status):
    with db_session_factory() as db:
        owner = User(openid="no-success")
        db.add(owner)
        db.flush()
        asset = _asset("music_shared", owner=None, created_at=datetime(2026, 10, 12, tzinfo=UTC))
        db.add(asset)
        db.flush()
        task = _task("not-success", owner=owner.id, music_id=asset.music_asset_id,
                     completed_at=datetime(2026, 10, 12, tzinfo=UTC), status=status)
        task.music_asset_id = None
        db.add(task)
        db.commit()
        assert list_owner_music_history(db, internal_user_pk=owner.id) == []


def test_canonical_escape_is_rejected_before_file_open(controlled_media_root, monkeypatch):
    """A resolver redirect cannot authorize an out-of-root file, even without symlink privileges."""
    from backend.app.services.v3.music_library_service import _availability
    outside = controlled_media_root.parent / "outside.mp3"
    outside.write_bytes(b"private")
    target = controlled_media_root / "redirect.mp3"
    target.write_bytes(b"audio")
    original_resolve = Path.resolve
    def redirected(path, *args, **kwargs):
        if path == target:
            return outside
        return original_resolve(path, *args, **kwargs)
    def forbidden_open(path, *args, **kwargs):
        pytest.fail("canonical escape must be rejected before any file open")
    monkeypatch.setattr(Path, "resolve", redirected)
    monkeypatch.setattr(Path, "open", forbidden_open)
    asset = _asset("a", owner=1, created_at=datetime(2026, 10, 12, tzinfo=UTC))
    asset.storage_key = str(target)
    assert _availability(asset, now=datetime(2026, 10, 14, tzinfo=UTC)) == "missing"


@pytest.mark.parametrize("status,expired,expected", [
    ("ready", True, "expired"), ("expired", False, "expired"),
    ("deleted", True, "deleted"), ("quarantined", True, "quarantined"),
])
def test_file_presence_never_overrides_status(controlled_media_root, status, expired, expected):
    from backend.app.services.v3.music_library_service import _availability
    target = controlled_media_root / "readable.mp3"
    target.write_bytes(b"audio")
    asset = _asset("a", owner=1, created_at=datetime(2026, 10, 12, tzinfo=UTC))
    asset.storage_key = str(target)
    asset.playable_status = status
    if expired:
        asset.retention_expires_at = datetime(2026, 10, 13, tzinfo=UTC)
    assert _availability(asset, now=datetime(2026, 10, 14, tzinfo=UTC)) == expected


def _asset(
    music_id: str,
    *,
    owner: int | None,
    source_type: str = "matched",
    created_at: datetime,
    instruments: list[str] | None = None,
) -> MusicAsset:
    return MusicAsset(
        music_asset_id=music_id,
        owner_internal_user_pk=owner,
        generation_task_id=None,
        source_type=source_type,
        catalog_track_id=f"catalog-{music_id}",
        title="legacy title must not be exposed",
        storage_key=f"music/{music_id}.mp3",
        format="mp3",
        duration_seconds=240,
        checksum=f"sha256:{music_id:0<64}"[-71:],
        tone_profile_json=None,
        bpm=84,
        instruments_json=instruments,
        playable_status="ready",
        created_at=created_at,
        updated_at=created_at,
    )


def _task(
    task_id: str,
    *,
    owner: int,
    music_id: str,
    completed_at: datetime,
    status: str = "matched_fallback",
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


def test_owner_history_includes_unplayed_assets_and_deduplicates_contexts(
    db_session_factory,
):
    """Catches filtering history by feedback/play events or emitting one card per task."""

    with db_session_factory() as db:
        owner = User(openid="owner-a")
        other = User(openid="owner-b")
        db.add_all([owner, other])
        db.flush()

        shared = _asset(
            "music_shared",
            owner=None,
            created_at=datetime(2026, 10, 12, 9, tzinfo=UTC),
            instruments=["笛", "古琴"],
        )
        direct = _asset(
            "music_direct",
            owner=owner.id,
            source_type="comfort_audio",
            created_at=datetime(2026, 10, 11, 8, tzinfo=UTC),
            instruments=["笛"],
        )
        unattached = _asset(
            "music_unattached",
            owner=None,
            created_at=datetime(2026, 10, 13, 8, tzinfo=UTC),
        )
        other_asset = _asset(
            "music_other",
            owner=other.id,
            created_at=datetime(2026, 10, 14, 8, tzinfo=UTC),
        )
        db.add_all([shared, direct, unattached, other_asset])
        db.flush()
        db.add_all(
            [
                _task(
                    "task-a-1",
                    owner=owner.id,
                    music_id=shared.music_asset_id,
                    completed_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                ),
                _task(
                    "task-a-2",
                    owner=owner.id,
                    music_id=shared.music_asset_id,
                    completed_at=datetime(2026, 10, 12, 10, tzinfo=UTC),
                ),
                _task(
                    "task-b-1",
                    owner=other.id,
                    music_id=shared.music_asset_id,
                    completed_at=datetime(2026, 10, 12, 7, tzinfo=UTC),
                ),
            ]
        )
        db.add_all(
            [
                Favorite(
                    favorite_id="fav-shared",
                    internal_user_pk=owner.id,
                    music_asset_id=shared.music_asset_id,
                ),
                Favorite(
                    favorite_id="fav-unattached",
                    internal_user_pk=owner.id,
                    music_asset_id=unattached.music_asset_id,
                ),
            ]
        )
        db.commit()

        history = list_owner_music_history(db, internal_user_pk=owner.id)

    assert [item.card.music_id for item in history] == ["music_shared", "music_direct"]
    assert history[0].context_ids == ("task-a-1", "task-a-2")
    assert history[0].card.source_summary.context_count == 2
    assert history[0].card.is_favorite is True
    assert history[1].context_ids == ()
    assert history[1].card.is_favorite is False


def test_owner_null_and_favorite_do_not_grant_library_access(db_session_factory):
    """Catches treating a shared catalog row or favorite row as ownership."""

    with db_session_factory() as db:
        owner = User(openid="owner-a")
        db.add(owner)
        db.flush()
        asset = _asset(
            "music_unattached",
            owner=None,
            created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
        )
        db.add(asset)
        db.flush()
        db.add(
            Favorite(
                favorite_id="fav-unattached",
                internal_user_pk=owner.id,
                music_asset_id=asset.music_asset_id,
            )
        )
        db.commit()

        assert list_owner_music_history(db, internal_user_pk=owner.id) == []


def test_legacy_duration_is_null_and_fixture_matches_music_card_contract(
    db_session_factory,
):
    """Catches leaking the legacy target duration or inventing a fallback duration."""

    with db_session_factory() as db:
        owner = User(openid="owner-a")
        db.add(owner)
        db.flush()
        asset = _asset(
            "music_shared",
            owner=None,
            created_at=datetime(2026, 10, 12, 9, tzinfo=UTC),
            instruments=["笛", "古琴"],
        )
        db.add(asset)
        db.flush()
        db.add_all(
            [
                _task(
                    "task-a-1",
                    owner=owner.id,
                    music_id=asset.music_asset_id,
                    completed_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
                ),
                _task(
                    "task-a-2",
                    owner=owner.id,
                    music_id=asset.music_asset_id,
                    completed_at=datetime(2026, 10, 12, 10, tzinfo=UTC),
                ),
            ]
        )
        db.add(
            Favorite(
                favorite_id="fav-shared",
                internal_user_pk=owner.id,
                music_asset_id=asset.music_asset_id,
            )
        )
        db.commit()

        card = list_owner_music_history(db, internal_user_pk=owner.id)[0].card

    assert card.duration_seconds is None
    fixture_path = Path(__file__).with_name("fixtures") / "music_card_v1.json"
    fixture = MusicCardV1.model_validate(json.loads(fixture_path.read_text("utf-8")))
    assert card == fixture


def test_title_uses_asset_date_while_activity_uses_real_completion_time(
    db_session_factory,
):
    """Catches owner/task dates changing a shared asset's deterministic title."""

    with db_session_factory() as db:
        owner = User(openid="owner-a")
        db.add(owner)
        db.flush()
        asset = _asset(
            "music_dated",
            owner=None,
            created_at=datetime(2026, 10, 10, 6, tzinfo=UTC),
        )
        db.add(asset)
        db.flush()
        task = _task(
            "task-completed",
            owner=owner.id,
            music_id=asset.music_asset_id,
            completed_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
            status="succeeded",
        )
        db.add(task)
        db.commit()

        card = list_owner_music_history(db, internal_user_pk=owner.id)[0].card

    assert card.default_title == "2026年10月10日的音乐 · _dated"
    assert card.playable_created_at == datetime(2026, 10, 12, 8, tzinfo=UTC)


def test_missing_completion_time_never_uses_task_creation_time(db_session_factory):
    """Catches presenting a queued-at timestamp as a successful asset timestamp."""

    with db_session_factory() as db:
        owner = User(openid="owner-a")
        db.add(owner)
        db.flush()
        asset = _asset(
            "music_completion",
            owner=None,
            created_at=datetime(2026, 10, 10, 6, tzinfo=UTC),
        )
        db.add(asset)
        db.flush()
        missing = _task(
            "task-missing-time",
            owner=owner.id,
            music_id=asset.music_asset_id,
            completed_at=datetime(2026, 10, 1, 8, tzinfo=UTC),
        )
        missing.completed_at = None
        verified = _task(
            "task-verified-time",
            owner=owner.id,
            music_id=asset.music_asset_id,
            completed_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
        )
        db.add_all([missing, verified])
        db.commit()

        card = list_owner_music_history(db, internal_user_pk=owner.id)[0].card

    assert card.playable_created_at == datetime(2026, 10, 12, 8, tzinfo=UTC)


def test_all_missing_completion_times_fall_back_to_asset_date(db_session_factory):
    """Catches a task creation timestamp replacing an unverifiable success time."""

    with db_session_factory() as db:
        owner = User(openid="owner-a")
        db.add(owner)
        db.flush()
        asset = _asset(
            "music_fallback_date",
            owner=None,
            created_at=datetime(2026, 10, 10, 6, tzinfo=UTC),
        )
        db.add(asset)
        db.flush()
        task = _task(
            "task-missing-time",
            owner=owner.id,
            music_id=asset.music_asset_id,
            completed_at=datetime(2026, 10, 1, 8, tzinfo=UTC),
        )
        task.completed_at = None
        db.add(task)
        db.commit()

        card = list_owner_music_history(db, internal_user_pk=owner.id)[0].card

    assert card.playable_created_at == datetime(2026, 10, 10, 6, tzinfo=UTC)


def test_music_card_rejects_naive_or_non_utc_timestamps():
    """Catches accepting timestamps that violate the UTC wire contract."""

    fixture_path = Path(__file__).with_name("fixtures") / "music_card_v1.json"
    payload = json.loads(fixture_path.read_text("utf-8"))
    for invalid in ("2026-10-12T08:00:00", "2026-10-12T16:00:00+08:00"):
        changed = {**payload, "activity_at": invalid}
        with pytest.raises(ValidationError, match="timezone-aware UTC"):
            MusicCardV1.model_validate(changed)


def test_malformed_legacy_instruments_degrade_to_unknown(db_session_factory):
    """Catches malformed legacy JSON crashing the entire history read."""

    with db_session_factory() as db:
        owner = User(openid="owner-a")
        db.add(owner)
        db.flush()
        asset = _asset(
            "music_bad_instrument",
            owner=owner.id,
            created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
            instruments=[{"unexpected": "shape"}],
        )
        db.add(asset)
        db.commit()

        card = list_owner_music_history(db, internal_user_pk=owner.id)[0].card

    assert card.primary_instrument_code == "unknown"
    assert card.primary_instrument_origin == "unknown"


@pytest.mark.parametrize("stored_status", ["deleted", "quarantined"])
def test_terminal_availability_precedes_retention_expiry(
    db_session_factory, stored_status
):
    """Catches replacing deleted/quarantined state with the weaker expired state."""

    with db_session_factory() as db:
        owner = User(openid=f"owner-{stored_status}")
        db.add(owner)
        db.flush()
        asset = _asset(
            f"music_{stored_status}",
            owner=owner.id,
            created_at=datetime(2026, 10, 12, 8, tzinfo=UTC),
        )
        asset.playable_status = stored_status
        asset.retention_expires_at = datetime(2026, 10, 13, 8, tzinfo=UTC)
        db.add(asset)
        db.commit()

        card = list_owner_music_history(
            db,
            internal_user_pk=owner.id,
            now=datetime(2026, 10, 14, 8, tzinfo=UTC),
        )[0].card

    assert card.availability == stored_status

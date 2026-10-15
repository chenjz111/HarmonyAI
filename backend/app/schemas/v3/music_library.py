"""Sprint 7 music-library read models.

These schemas are additive.  They deliberately do not change the frozen V3
generation schemas, whose audio duration remains a required positive integer.

``MusicCardV1`` (W1) is unchanged.  Everything below the divider is the W2
additive contract; its field sets follow the public adapter intent documented in
``docs/sprint7/TEAM_BASELINE_DEVELOPMENT.md`` (limit 1..50, opaque cursor,
``user_title`` + ``expected_version``, ``event_id`` + ``event_type=play_started``
+ ``source_context_id``).  The four R2-A drafts are not distributed with the team
baseline, so draft-identical naming/shape still needs Integration's freeze before
a downstream module may rely on it.
"""

from typing import Annotated, Literal

from pydantic import Field, field_validator

from backend.app.schemas.v3.common import NonEmptyString, Timestamp, V3BaseModel


Availability = Literal["ready", "expired", "quarantined", "deleted", "missing"]
InstrumentCode = Literal["dizi", "guqin", "guzheng", "sheng", "xiao", "pipa", "unknown"]


class MusicSourceSummaryV1(V3BaseModel):
    kind: Literal["uploaded_documents", "questionnaire", "none", "unknown"]
    availability: Literal["available", "unavailable", "unknown"]
    context_count: Annotated[int, Field(ge=0)]


class MusicCardV1(V3BaseModel):
    music_id: Annotated[str, Field(min_length=1, max_length=64)]
    source_type: Literal["generated", "matched", "comfort_audio"]
    default_title: Annotated[str, Field(min_length=1)]
    user_title: str | None
    display_title: Annotated[str, Field(min_length=1)]
    metadata_version: Annotated[int, Field(ge=0)]
    playable_created_at: Timestamp
    last_played_at: Timestamp | None
    activity_at: Timestamp
    duration_seconds: Annotated[int, Field(gt=0)] | None
    availability: Availability
    is_favorite: bool
    primary_instrument_code: InstrumentCode
    primary_instrument_origin: Literal["persisted", "legacy_single", "unknown"]
    source_summary: MusicSourceSummaryV1


# ---------------------------------------------------------------------------
# Sprint 7 W2 additive contracts (Issue #151).
# ---------------------------------------------------------------------------

USER_TITLE_MAX_LENGTH = 120
PLAYBACK_EVENT_ID_MAX_LENGTH = 64
CONTEXT_ID_MAX_LENGTH = 64

# Event/context identifiers are opaque to the server but must not be able to
# carry separators, control characters or path/format tricks into logs or rows.
_OPAQUE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


def _normalize_private_title(value: str | None) -> str | None:
    """``None`` clears; otherwise plain single-line text within a safe length."""

    if value is None:
        return None
    text = value.strip()
    if not text:
        raise ValueError("user_title must be null to clear or non-empty plain text")
    if len(text) > USER_TITLE_MAX_LENGTH:
        raise ValueError("user_title is too long")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in text):
        raise ValueError("user_title must not contain control characters")
    return text


class MusicSourceContextV1(V3BaseModel):
    """One selectable, owner-verified persisted generation context."""

    context_id: Annotated[str, Field(min_length=1, max_length=CONTEXT_ID_MAX_LENGTH)]
    kind: Literal["uploaded_documents", "questionnaire", "none", "unknown"]
    availability: Literal["available", "unavailable", "unknown"]


class MusicHistoryExplanationV1(V3BaseModel):
    """Persisted origin facts bound to one explicitly selected context."""

    music_id: Annotated[str, Field(min_length=1, max_length=64)]
    context_id: Annotated[str, Field(min_length=1, max_length=CONTEXT_ID_MAX_LENGTH)]
    task_status: Literal["succeeded", "matched_fallback"]
    source_type: Literal["generated", "matched"]
    fallback_applied: bool
    completed_at: Timestamp | None
    prescription_id: NonEmptyString


class LibraryAudioV1(V3BaseModel):
    """Real availability of *this* asset.

    ``duration_seconds`` is the measured duration and stays ``None`` when no
    measured value exists; the legacy generation target is never copied here.
    """

    availability: Availability
    duration_seconds: Annotated[int, Field(gt=0)] | None
    format: Literal["mp3", "wav", "m4a"]


class MusicDetailV1(V3BaseModel):
    card: MusicCardV1
    audio: LibraryAudioV1
    source_contexts: list[MusicSourceContextV1]
    selected_context_id: Annotated[str, Field(min_length=1, max_length=CONTEXT_ID_MAX_LENGTH)] | None
    history_explanation: MusicHistoryExplanationV1 | None


class MusicLibraryPageV1(V3BaseModel):
    """Signed-cursor page envelope for history and favorites."""

    items: list[MusicCardV1]
    next_cursor: str | None
    has_more: bool


class TitleUpdateRequestV1(V3BaseModel):
    """Private title write: ``user_title=null`` clears, CAS on the version."""

    user_title: str | None
    expected_version: Annotated[int, Field(ge=0)]

    @field_validator("user_title")
    @classmethod
    def _validate_user_title(cls, value: str | None) -> str | None:
        return _normalize_private_title(value)


class TitleUpdateResultV1(V3BaseModel):
    music_id: Annotated[str, Field(min_length=1, max_length=64)]
    user_title: str | None
    display_title: Annotated[str, Field(min_length=1)]
    metadata_version: Annotated[int, Field(ge=0)]


class PlaybackEventRequestV1(V3BaseModel):
    """A real playback start.  Page views, prefetch and seek are not plays."""

    event_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=PLAYBACK_EVENT_ID_MAX_LENGTH,
            pattern=_OPAQUE_ID_PATTERN,
        ),
    ]
    event_type: Literal["play_started"]
    source_context_id: (
        Annotated[
            str,
            Field(min_length=1, max_length=CONTEXT_ID_MAX_LENGTH, pattern=_OPAQUE_ID_PATTERN),
        ]
        | None
    ) = None


class PlaybackEventResultV1(V3BaseModel):
    event_id: Annotated[str, Field(min_length=1, max_length=PLAYBACK_EVENT_ID_MAX_LENGTH)]
    music_id: Annotated[str, Field(min_length=1, max_length=64)]
    event_type: Literal["play_started"]
    occurred_at: Timestamp
    last_played_at: Timestamp
    replayed: bool


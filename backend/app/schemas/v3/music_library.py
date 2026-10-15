"""Sprint 7 music-library read models.

These schemas are additive.  They deliberately do not change the frozen V3
generation schemas, whose audio duration remains a required positive integer.
"""

from typing import Annotated, Literal

from pydantic import Field

from backend.app.schemas.v3.common import Timestamp, V3BaseModel


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

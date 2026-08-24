"""Additive Agent 5 read-model / favorites contracts (not part of the frozen
contract surface, so they live in their own module and reuse frozen types).
"""

from __future__ import annotations

from pydantic import Field

from .common import NonEmptyString, Timestamp, V3BaseModel
from .feedback import ChangeLabel
from .music import MusicRef


class FavoriteItem(V3BaseModel):
    favorite_id: NonEmptyString
    music_ref: MusicRef
    favorited_at: Timestamp


class FavoriteList(V3BaseModel):
    items: list[FavoriteItem]
    total: int


class FavoriteState(V3BaseModel):
    music_ref: MusicRef
    is_favorite: bool


class FavoriteRequest(V3BaseModel):
    music_ref: MusicRef


class FeedbackHistoryItem(V3BaseModel):
    feedback_id: NonEmptyString
    session_id: NonEmptyString
    music_ref: MusicRef
    change_label: ChangeLabel
    submitted_at: Timestamp


class FeedbackHistory(V3BaseModel):
    items: list[FeedbackHistoryItem]
    total: int

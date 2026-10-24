"""Sprint 5 V3 persistence models."""

from .identity import AuthSession, UserIdentity, UserProfile
from .session import SessionInputRevision, V3IdempotencyRecord
from .understanding import (
    FactSourceRef,
    NormalizedFact,
    QuestionnaireSubmissionV3,
    UnderstandingRevision,
    UnderstandingRun,
    UnderstandingSource,
)
from .assessment import AssessmentRevisionV3, AssessmentV3, FactEvidence, OrganEvidence
from .document import DocumentRelevance, DocumentSet, DocumentSetItem
from .diagnosis import (
    AiProviderRun,
    DiagnosisCandidate,
    DiagnosisCandidateEvidence,
    DiagnosisRun,
    KnowledgeChunkV3,
    KnowledgeManifest,
    RagRetrievalHit,
    RagRetrievalRun,
)
from .prescription import PrescriptionV3
from .music import GenerationTask, MusicAsset
from .music_library import MusicLibraryState, MusicPlaybackEvent, OwnerMusicState
from .feedback import (
    Favorite,
    FeedbackClearReceipt,
    FeedbackV3,
    PreferenceEvent,
    UserMusicPreference,
    UserMusicPreferenceVersion,
    UserPreferenceItem,
)

__all__ = [
    "MusicLibraryState", "MusicPlaybackEvent", "OwnerMusicState",
    "AuthSession",
    "UserIdentity",
    "UserProfile",
    "V3IdempotencyRecord",
    "SessionInputRevision",
    "UnderstandingRun",
    "UnderstandingSource",
    "UnderstandingRevision",
    "QuestionnaireSubmissionV3",
    "NormalizedFact",
    "FactSourceRef",
    "AssessmentV3",
    "AssessmentRevisionV3",
    "FactEvidence",
    "OrganEvidence",
    "DocumentSet",
    "DocumentSetItem",
    "DocumentRelevance",
    "DiagnosisRun",
    "DiagnosisCandidate",
    "DiagnosisCandidateEvidence",
    "KnowledgeManifest",
    "KnowledgeChunkV3",
    "RagRetrievalRun",
    "RagRetrievalHit",
    "AiProviderRun",
    "PrescriptionV3",
    "GenerationTask",
    "MusicAsset",
    "FeedbackV3",
    "FeedbackClearReceipt",
    "UserMusicPreference",
    "UserMusicPreferenceVersion",
    "UserPreferenceItem",
    "PreferenceEvent",
    "Favorite",
    "AccountCredential", "RegisteredSessionState", "RefreshProof", "LoginBucket",
]

from .account_security import AccountCredential, RegisteredSessionState, RefreshProof, LoginBucket

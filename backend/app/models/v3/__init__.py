"""Sprint 5 V3 persistence models."""

from .identity import UserIdentity, UserProfile
from .session import V3IdempotencyRecord
from .understanding import (
    FactSourceRef,
    NormalizedFact,
    QuestionnaireSubmissionV3,
    UnderstandingRevision,
    UnderstandingRun,
    UnderstandingSource,
)
from .assessment import AssessmentRevisionV3, AssessmentV3, FactEvidence, OrganEvidence
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
from .feedback import (
    Favorite,
    FeedbackV3,
    PreferenceEvent,
    UserMusicPreference,
    UserMusicPreferenceVersion,
    UserPreferenceItem,
)

__all__ = [
    "UserIdentity",
    "UserProfile",
    "V3IdempotencyRecord",
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
    "UserMusicPreference",
    "UserMusicPreferenceVersion",
    "UserPreferenceItem",
    "PreferenceEvent",
    "Favorite",
]

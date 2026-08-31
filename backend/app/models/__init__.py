"""HarmonyAI Database Models — Sprint 4.

11 tables: users / sessions / emotion_assessments / syndrome_diagnoses /
           prescriptions / feedbacks / documents /
           ai_call_logs / assessment_evidences / assessment_followups / assessment_revisions
"""
from backend.app.models.user import User
from backend.app.models.session import Session
from backend.app.models.emotion_assessment import EmotionAssessment
from backend.app.models.syndrome_diagnosis import SyndromeDiagnosis
from backend.app.models.prescription import Prescription
from backend.app.models.feedback import Feedback
from backend.app.models.document import Document
from backend.app.models.ai_call_log import AICallLog
from backend.app.models.assessment_evidence import AssessmentEvidence
from backend.app.models.assessment_followup import AssessmentFollowUp
from backend.app.models.assessment_revision import AssessmentRevision

# Sprint 5 V3 business persistence models (registered so Base.metadata
# create_all / migrations see them regardless of import order).
from backend.app.models.v3 import *  # noqa: F401,F403
from backend.app.models.v3 import __all__ as _v3_all

__all__ = [
    "User", "Session", "EmotionAssessment", "SyndromeDiagnosis",
    "Prescription", "Feedback", "Document",
    "AICallLog", "AssessmentEvidence", "AssessmentFollowUp", "AssessmentRevision",
] + _v3_all

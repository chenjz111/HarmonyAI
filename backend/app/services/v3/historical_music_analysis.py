"""Read the exact task's persisted public explanation, independent of current inputs."""
from sqlalchemy import and_
from backend.app.models.session import Session as SessionModel
from backend.app.models.v3.assessment import AssessmentV3,AssessmentRevisionV3
from backend.app.models.v3.diagnosis import DiagnosisRun
from backend.app.models.v3.prescription import PrescriptionV3
from backend.app.models.v3.music import GenerationTask
from backend.app.services.v3.music_library_access import LibraryAccessDenied,require_library_access,LIBRARY_TERMINAL_TASK_STATUSES
from backend.app.services.v3.internal_agent3_service import load_persisted_five_tone_read_model


def read_historical_music_analysis(db,*,owner,music_id,context_id):
    require_library_access(db,internal_user_pk=owner,music_id=music_id)
    diagnosis=(db.query(DiagnosisRun).select_from(DiagnosisRun)
        .join(PrescriptionV3,PrescriptionV3.diagnosis_id==DiagnosisRun.diagnosis_id)
        .join(GenerationTask,GenerationTask.prescription_id==PrescriptionV3.prescription_id)
        .join(SessionModel,SessionModel.id==GenerationTask.session_row_id)
        .join(AssessmentV3,AssessmentV3.assessment_id==DiagnosisRun.assessment_id)
        .join(AssessmentRevisionV3,and_(AssessmentRevisionV3.assessment_id==DiagnosisRun.assessment_id,
            AssessmentRevisionV3.revision==DiagnosisRun.assessment_revision))
        .filter(GenerationTask.task_id==context_id,GenerationTask.music_asset_id==music_id,
            GenerationTask.status.in_(LIBRARY_TERMINAL_TASK_STATUSES),
            GenerationTask.internal_user_pk==owner,PrescriptionV3.internal_user_pk==owner,
            DiagnosisRun.internal_user_pk==owner,AssessmentV3.internal_user_pk==owner,SessionModel.user_id==owner,
            PrescriptionV3.session_row_id==GenerationTask.session_row_id,
            DiagnosisRun.session_row_id==GenerationTask.session_row_id,
            AssessmentV3.session_row_id==GenerationTask.session_row_id,
            AssessmentRevisionV3.status=='confirmed',AssessmentRevisionV3.confirmation_status=='confirmed')
        .one_or_none())
    if diagnosis is None:raise LibraryAccessDenied
    # Current assessment/input/understanding revisions deliberately do not replace
    # this task's own immutable diagnosis revision. Existing live-generation gates
    # continue to use load_current_five_tone_read_model, unchanged.
    return load_persisted_five_tone_read_model(diagnosis)

"""Agent 3 (Prescription) endpoints (Issue #99 step 5)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.schemas.v3.prescription import PrescriptionV31Request, PrescriptionV3
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.prescription_service import (
    DiagnosisNotReady,
    OwnedResourceNotFound,
    create_prescription,
    get_prescription,
)


router = APIRouter()


@router.post(
    "/prescriptions",
    response_model=V3SuccessEnvelope[PrescriptionV3],
    status_code=201,
)
def create_prescription_endpoint(
    body: PrescriptionV31Request,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[PrescriptionV3]:
    try:
        return v3_success(create_prescription(db, principal, body))
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应诊断。") from None
    except DiagnosisNotReady:
        raise V3APIError(
            409, "DIAGNOSIS_NOT_READY", "诊断尚未完成，无法生成处方。"
        ) from None


@router.get(
    "/prescriptions/{prescription_id}",
    response_model=V3SuccessEnvelope[PrescriptionV3],
)
def get_prescription_endpoint(
    prescription_id: str,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[PrescriptionV3]:
    try:
        return v3_success(get_prescription(db, principal, prescription_id))
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应处方。") from None

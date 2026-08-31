"""V3 prescription persistence model.

Column/constraint semantics mirror 0002_v3_business migration SQL
and harmonyai-v3-persistence-contract.md section 7.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
)
from sqlalchemy.sql import func

from backend.app.core.database import Base


class PrescriptionV3(Base):
    __tablename__ = "prescription_v3"
    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'degraded', 'withheld')",
            name="ck_prescription_v3_status",
        ),
        CheckConstraint(
            "prescription_mode IS NULL OR prescription_mode IN "
            "('syndrome_based', 'conservative_fallback')",
            name="ck_prescription_v3_mode",
        ),
        CheckConstraint(
            "(status = 'withheld' AND generation_spec_json IS NULL) OR "
            "(status IN ('success', 'degraded') AND generation_spec_json IS NOT NULL)",
            name="ck_prescription_v3_spec",
        ),
    )

    prescription_id = Column(String(64), primary_key=True)
    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_row_id = Column(
        Integer, ForeignKey("sessions.id"), nullable=False, index=True
    )
    diagnosis_id = Column(
        String(64),
        ForeignKey("diagnosis_runs.diagnosis_id"),
        nullable=False,
        index=True,
    )
    status = Column(String(16), nullable=False)
    prescription_mode = Column(String(24), nullable=True)
    tone_profile_json = Column(JSON, nullable=True)
    generation_spec_json = Column(JSON, nullable=True)
    preference_profile_id = Column(String(64), nullable=True)
    preference_version_id = Column(String(64), nullable=True)
    personalization_json = Column(JSON, nullable=False)
    presentation_json = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

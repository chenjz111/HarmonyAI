"""V3.1 document-set persistence (Issue #99 step 2).

A DocumentSet is an immutable, revisioned snapshot of 1-3 active source
documents for a with_document session. Adding, deleting or replacing a
document creates a new revision; the previous revision is kept for audit but
no longer active. Item order (position 1-3) preserves the user's upload order.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from backend.app.core.database import Base


class DocumentSet(Base):
    __tablename__ = "document_sets"
    __table_args__ = (
        UniqueConstraint(
            "session_row_id", "document_set_id", name="uq_document_sets_session"
        ),
        CheckConstraint("revision >= 1", name="ck_document_sets_revision"),
        CheckConstraint(
            "status IN ('active', 'superseded', 'discarded')",
            name="ck_document_sets_status",
        ),
    )

    document_set_id = Column(String(64), primary_key=True)
    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_row_id = Column(
        Integer, ForeignKey("sessions.id"), nullable=False, index=True
    )
    revision = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class DocumentSetItem(Base):
    __tablename__ = "document_set_items"
    __table_args__ = (
        UniqueConstraint(
            "document_set_id", "position", name="uq_document_set_items_position"
        ),
        UniqueConstraint(
            "document_set_id", "document_id", name="uq_document_set_items_document"
        ),
        CheckConstraint(
            "position >= 1 AND position <= 3", name="ck_document_set_items_position"
        ),
    )

    document_set_item_id = Column(String(64), primary_key=True)
    document_set_id = Column(
        String(64),
        ForeignKey("document_sets.document_set_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Plain reference column (not a hard FK) so the V3 migration does not need
    # the Sprint-4 documents table; same-user/session ownership is enforced at
    # the service layer.
    document_id = Column(String(64), nullable=False)
    position = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

# app/models/checklist_model.py
import uuid
from sqlalchemy import Column, String, Date, Boolean, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from app.database import Base


class Checklist(Base):
    __tablename__ = "checklists"
    __table_args__ = {"schema": "mechanics_db_schema"}

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    supervisor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mechanics_db_schema.users.id", ondelete="SET NULL"),
        nullable=True,
    )

    date = Column(
        Date,
        nullable=False,
        default=func.current_date(),
    )

    items = Column(
        JSON,
        nullable=False,
        default=list,
    )

    completed = Column(
        Boolean,
        default=False,
    )

    submitted_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
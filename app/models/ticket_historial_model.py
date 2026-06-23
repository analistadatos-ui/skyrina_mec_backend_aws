import uuid

from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    Text,
)

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.sql import func

from sqlalchemy.types import TIMESTAMP

from app.database import Base


class TicketHistorial(Base):

    __tablename__ = "ticket_historial"

    __table_args__ = {
        "schema": "mechanics_db_schema"
    }

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    ticket_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "mechanics_db_schema.tickets.id"
        ),
        nullable=False,
    )

    usuario_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "mechanics_db_schema.users.id"
        ),
        nullable=False,
    )

    accion = Column(
        String(120),
        nullable=False,
    )

    descripcion = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )
import uuid

from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    Text,
)

from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class TicketCambioEstilo(Base):

    __tablename__ = "ticket_cambio_estilo"

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
        unique=True,
    )
    estilo_actual = Column(
        String(255),
        nullable=False,
    )

    nuevo_estilo = Column(
        String(255),
        nullable=False,
    )

    motivo = Column(
        Text,
        nullable=True,
    )

    observaciones = Column(
        Text,
        nullable=True,
    )
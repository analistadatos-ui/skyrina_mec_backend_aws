import uuid

from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    Text,
)

from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class TicketFallaEquipo(Base):

    __tablename__ = "ticket_falla_equipo"

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
    maquina_nombre = Column(
        String(255),
        nullable=False,
    )

    maquina_codigo = Column(
        String(100),
        nullable=True,
    )

    prioridad = Column(
        String(50),
        nullable=False,
    )

    area = Column(
        String(100),
        nullable=True,
    )

    observaciones = Column(
        Text,
        nullable=True,
    )

    image_url = Column(
        String(500),
        nullable=True,
    )
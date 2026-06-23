import uuid
import enum

from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    Enum,
    Text,
)

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.sql import func

from sqlalchemy.types import TIMESTAMP

from app.database import Base


class AsignacionStatus(str, enum.Enum):

    pendiente = "pendiente"

    asignado = "asignado"

    trabajando = "trabajando"

    pausado = "pausado"

    completado = "completado"
class TicketAsignacion(Base):

    __tablename__ = "ticket_asignaciones"

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

    mecanico_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "mechanics_db_schema.users.id"
        ),
        nullable=False,
    )

    asignado_por = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "mechanics_db_schema.users.id"
        ),
         nullable=False,
    )

    status = Column(
        Enum(
            AsignacionStatus,
            schema="mechanics_db_schema",
        ),
        default=AsignacionStatus.asignado,
    )

    notas = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
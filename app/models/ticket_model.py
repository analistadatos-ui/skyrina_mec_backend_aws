import uuid
import enum

from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    Enum,
    Text,
    Boolean,
    Integer,
)

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.sql import func

from sqlalchemy.types import TIMESTAMP

from app.database import Base


# ==========================================
# TICKET TYPE
# ==========================================
class TicketType(str, enum.Enum):
    falla_equipo = "falla_equipo"
    cambio_estilo = "cambio_estilo"


# ==========================================
# TICKET STATUS
# ==========================================
class TicketStatus(str, enum.Enum):
    pendiente = "pendiente"
    asignado = "asignado"
    en_proceso = "en_proceso"
    pausado = "pausado"
    completado = "completado"
    validado = "validado"
    cerrado = "cerrado"
    cancelado = "cancelado"


# ==========================================
# PRIORIDAD
# ==========================================
class PrioridadGeneral(str, enum.Enum):
    baja = "baja"
    normal = "normal"
    alta = "alta"
    critica = "critica"
    urgente = "urgente"  # Add this if you want to keep 'urgente'

# ==========================================
# LOCATION
# ==========================================
class TicketLocation(str, enum.Enum):
    piso = "piso"
    taller = "taller"


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = {"schema": "mechanics_db_schema"}

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    ticket_number = Column(
        String(50),
        unique=True,
        nullable=False,
    )

    tipo = Column(
        Enum(TicketType, schema="mechanics_db_schema"),
        nullable=False,
    )

    titulo = Column(
        String(255),
        nullable=False,
    )

    descripcion = Column(
        Text,
        nullable=False,
    )

    status = Column(
        Enum(TicketStatus, schema="mechanics_db_schema"),
        default=TicketStatus.pendiente,
    )

    prioridad_general = Column(
        Enum(PrioridadGeneral, schema="mechanics_db_schema"),
        default=PrioridadGeneral.normal,
    )

    ubicacion = Column(
        Enum(TicketLocation, schema="mechanics_db_schema"),
        default=TicketLocation.piso,
    )

    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("mechanics_db_schema.users.id"),
        nullable=False,
    )

    linea_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mechanics_db_schema.lineas.id"),
        nullable=False,
    )

    assigned_to = Column(
        UUID(as_uuid=True),
        ForeignKey("mechanics_db_schema.users.id"),
        nullable=True,
    )

    solution_description = Column(
        Text,
        nullable=True,
    )

    assigned_by = Column(
        UUID(as_uuid=True),
        ForeignKey("mechanics_db_schema.users.id"),
        nullable=True,
    )

    assigned_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    started_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    completed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    closed_at = Column(
        TIMESTAMP(timezone=True),
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

    # TIMER SYSTEM FIELDS - ONLY DEFINE ONCE!
    resolution_minutes = Column(
        Integer,
        nullable=True,
    )

    delayed = Column(
        Boolean,
        default=False,
    )
    closed_by = Column(
        UUID(as_uuid=True),
        nullable=True,
    )
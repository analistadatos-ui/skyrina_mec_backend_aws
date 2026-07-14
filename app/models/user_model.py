import uuid
import enum

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Enum,
    Integer,
)

from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


# ==========================================
# USER ROLE
# ==========================================
class UserRole(str, enum.Enum):

    jefe_linea = "jefe_linea"

    jefe_mecanicos = "jefe_mecanicos"

    mecanico = "mecanico"

    supervisor = "supervisor"

    rh = "rh"

    muestra = "muestra"


# ==========================================
# MECHANIC LOCATION
# ==========================================
class MechanicLocation(
    str,
    enum.Enum
):

    piso = "piso"

    taller = "taller"

    muestras = "muestras"


class User(Base):

    __tablename__ = "users"

    __table_args__ = {
        "schema": "mechanics_db_schema"
    }

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    username = Column(
        String(100),
        unique=True,
        nullable=False,
    )

    nombre = Column(
        String(255),
        nullable=False,
    )

    hashed_password = Column(
        String(255),
        nullable=False,
    )

    role = Column(
        Enum(
            UserRole,
            schema="mechanics_db_schema",
        ),
        nullable=False,
    )

    linea_id = Column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # ==========================================
    # CURRENT LOCATION
    # ==========================================
    current_location = Column(

        Enum(
            MechanicLocation,
            schema="mechanics_db_schema",
        ),

        default=MechanicLocation.piso,
    )

    status = Column(
        Boolean,
        default=True,
    )

    # ==========================================
    # EXPERIENCE RANK
    # Used by the ticket auto-assign algorithm to
    # prefer more senior mechanics first. LOWER
    # number = MORE senior/experienced = assigned
    # before mechanics with a higher number.
    # NULL means "no rank set" — treated as lowest
    # priority among regular mecanicos (but still
    # above jefe_mecanicos, who are fallback-only
    # regardless of rank).
    # ==========================================
    experience_rank = Column(
        Integer,
        nullable=True,
    )
import uuid
import enum

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Enum,
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


# ==========================================
# MECHANIC LOCATION
# ==========================================
class MechanicLocation(
    str,
    enum.Enum
):

    piso = "piso"

    taller = "taller"


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
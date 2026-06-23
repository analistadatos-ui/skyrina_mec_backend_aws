import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
)

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.sql import func

from sqlalchemy.types import TIMESTAMP

from app.database import Base


class Linea(Base):

    __tablename__ = "lineas"

    __table_args__ = {
        "schema": "mechanics_db_schema"
    }

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    nombre = Column(
        String(80),
        nullable=False,
    )

    numero = Column(
        Integer,
        unique=True,
        nullable=False,
    )

    activa = Column(
        Boolean,
        default=True,
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )
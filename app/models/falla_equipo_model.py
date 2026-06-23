import uuid

from sqlalchemy import (
    Column,
    String,
    Text,
    ForeignKey,
)

from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class FallaEquipo(Base):

    __tablename__ = "falla_equipo"

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

    maquina_nombre = Column(
        String(255)
    )

    maquina_codigo = Column(
        String(255)
    )

    area = Column(
        String(255)
    )

    observaciones = Column(
        Text
    )

    image_url = Column(
        Text
    )
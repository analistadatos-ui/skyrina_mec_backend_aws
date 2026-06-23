import uuid

from sqlalchemy import (
    Column,
    String,
    Text,
    ForeignKey,
)

from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class CambioEstilo(Base):

    __tablename__ = "cambio_estilo"

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
            "mechanics_db_schema.tickets.id",
            ondelete="CASCADE"  # Add this to handle deletions properly
        ),
        nullable=False,
    )

    estilo_actual = Column(
        String(255),
        nullable=False  # ADD THIS - this field is required
    )

    nuevo_estilo = Column(
        String(255),
        nullable=False  # ADD THIS - this field is required
    )

    observaciones = Column(
        Text,
        nullable=True  # This can remain optional
    )
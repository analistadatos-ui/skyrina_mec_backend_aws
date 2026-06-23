# app/models/ticket_validacion_model.py
import uuid
from sqlalchemy import Column, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from app.database import Base

class TicketValidacion(Base):
    __tablename__ = "tickets_validacion"
    __table_args__ = {"schema": "mechanics_db_schema"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("mechanics_db_schema.tickets.id"), nullable=False)
    validado_por = Column(UUID(as_uuid=True), nullable=False)
    comentario = Column(Text, nullable=True)
    fotos = Column(ARRAY(Text), nullable=True)  # Store photo paths as array of strings
    validated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
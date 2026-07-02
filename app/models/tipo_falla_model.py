import uuid

from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


# ==========================================
# TIPO DE FALLA (failure type catalog)
# Populates the "Tipo de Falla" dropdown in
# NuevaFallaPage. Users can add new ones from
# the frontend via POST /tickets/tipos-falla.
# ==========================================
class TipoFalla(Base):
    __tablename__ = "tipos_falla"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(100), nullable=False, unique=True, index=True)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    activo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
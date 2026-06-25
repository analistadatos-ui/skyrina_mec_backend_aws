# app/models/system_config_model.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(String, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ==========================================
# DEFAULTS — used when a key is not yet in DB
# ==========================================
DEFAULTS: dict[str, str] = {
    "bono_maximo":        "1000",  # MXN
    "dias_laborales":     "6",
    "meta_tiempo_100":    "7",     # minutes → 100 % score
    "meta_tiempo_0":      "15",    # minutes → 0 % score (linear decay between the two)
    "meta_cambio_estilo": "15",    # minutes
    "zona_horaria":       "America/Mexico_City",
    "cierre_automatico":  "Domingo 23:59",
    "bucket_s3":          "skyrina-tickets-fotos",
    "retencion_bd":       "365",   # days
}
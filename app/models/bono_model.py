# app/models/bono_model.py
import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    ForeignKey,
    JSON,
)

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.sql import func

from sqlalchemy.types import TIMESTAMP

from app.database import Base


class BonoCierre(Base):

    __tablename__ = "bono_cierres"

    __table_args__ = {
        "schema": "mechanics_db_schema"
    }

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Monday date string e.g. "2026-06-15"
    semana = Column(
        String(10),
        nullable=False,
        unique=True,
    )

    # "abierto" | "cerrado"
    status = Column(
        String(20),
        nullable=False,
        default="abierto",
    )

    # KPIs computed at close time
    afectacion_pct = Column(Float, nullable=True)
    cambios_pct    = Column(Float, nullable=True)
    orden_pct      = Column(Float, nullable=True)
    bono_pct       = Column(Float, nullable=True)

    # 1000 MXN max
    monto_bono_mxn  = Column(Integer, nullable=True)   # suggested
    monto_final_mxn = Column(Integer, nullable=True)   # adjusted by RH

    # Who closed it
    cerrado_por = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "mechanics_db_schema.users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    # Who reopened it (used by rh_routes.py /bonos/reabrir)
    reabierto_por = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "mechanics_db_schema.users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    # [{ "mecanico_id": "uuid", "nombre": "...", "motivo": "Falta" }]
    exclusiones = Column(
        JSON,
        default=list,
        nullable=False,
    )

    # [{ "mecanico_id": "uuid", "monto_final_mxn": 850 }]
    # Per-mechanic adjusted amounts (used by rh_routes.py get/set_stored_monto)
    montos_individuales = Column(
        JSON,
        default=list,
        nullable=False,
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )

    cerrado_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
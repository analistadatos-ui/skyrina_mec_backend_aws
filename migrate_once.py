"""
Run ONCE against the database to create the schema + tables.

Usage (from project root, venv active, .env pointing at Aurora):

    python migrate_once.py
"""

from sqlalchemy import text

from app.database import engine, Base, DB_SCHEMA

# Import every model so Base.metadata knows about all tables
from app.models.user_model import User  # noqa: F401
from app.models.linea_model import Linea  # noqa: F401
from app.models.ticket_model import Ticket  # noqa: F401
from app.models.ticket_falla_model import TicketFallaEquipo  # noqa: F401
from app.models.ticket_cambio_model import TicketCambioEstilo  # noqa: F401
from app.models.bono_model import BonoCierre  # noqa: F401
from app.models.ticket_asignacion_model import TicketAsignacion  # noqa: F401
from app.models.falla_equipo_model import FallaEquipo  # noqa: F401
from app.models.cambio_estilo_model import CambioEstilo  # noqa: F401
from app.models.ticket_historial_model import TicketHistorial  # noqa: F401
from app.models.ticket_comentario_model import TicketComentario  # noqa: F401
from app.models.ticket_validation_model import TicketValidacion  # noqa: F401
from app.models.checklist_model import Checklist  # noqa: F401


if __name__ == "__main__":
    # 1) Create the schema first (it doesn't exist in a fresh Aurora DB)
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA}"))
        conn.commit()
    print(f"Schema '{DB_SCHEMA}' ready.")

    # 2) Now create all tables inside that schema
    print("Creating tables ...")
    Base.metadata.create_all(bind=engine)
    print("Done.")
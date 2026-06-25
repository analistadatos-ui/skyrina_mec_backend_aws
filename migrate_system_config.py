# migrate_system_config.py
# Creates ONLY the system_config table in Aurora.
# Safe to run: create_all only creates tables that don't already exist;
# it does NOT drop or modify existing tables/data.

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base, DB_SCHEMA
from sqlalchemy import text

# Import the model so SQLAlchemy registers it on Base.metadata
from app.models.system_config_model import SystemConfig


def run():
    # Make sure the schema exists (it already should)
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA}"))
        conn.commit()

    # Tell SQLAlchemy this table lives in your schema
    SystemConfig.__table__.schema = DB_SCHEMA

    # Create ONLY this table (create_all skips ones that already exist)
    Base.metadata.create_all(bind=engine, tables=[SystemConfig.__table__])
    print(f"Done. Ensured 'system_config' table exists in schema '{DB_SCHEMA}'.")

    # Verify
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :s AND table_name = 'system_config'"
        ), {"s": DB_SCHEMA})
        found = [r[0] for r in result]
        print("Verified tables present:", found)


if __name__ == "__main__":
    run()
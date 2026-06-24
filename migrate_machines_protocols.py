# migrate_machines_protocols.py
# Creates ONLY the machines and protocols tables in Aurora.
# Safe to run: create_all only creates tables that don't already exist;
# it does NOT drop or modify existing tables/data.

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base, DB_SCHEMA
from sqlalchemy import text

# Import the two models so SQLAlchemy registers them on Base.metadata
from app.models.machine_model import Machine
from app.models.protocol_model import Protocol


def run():
    # Make sure the schema exists (it already should)
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA}"))
        conn.commit()

    # Tell SQLAlchemy these tables live in your schema
    Machine.__table__.schema = DB_SCHEMA
    Protocol.__table__.schema = DB_SCHEMA

    # Create ONLY these two tables (create_all skips ones that already exist)
    Base.metadata.create_all(bind=engine, tables=[Machine.__table__, Protocol.__table__])
    print(f"Done. Ensured 'machines' and 'protocols' tables exist in schema '{DB_SCHEMA}'.")

    # Verify
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :s AND table_name IN ('machines','protocols')"
        ), {"s": DB_SCHEMA})
        found = [r[0] for r in result]
        print("Verified tables present:", found)


if __name__ == "__main__":
    run()
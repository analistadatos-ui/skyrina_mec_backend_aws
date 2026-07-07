# add_muestras_location.py
# Adds the 'muestras' value to the existing MechanicLocation enum type
# in Postgres. Safe to run: ADD VALUE IF NOT EXISTS is a no-op if the
# value is already there.
#
# Background: current_location uses a native Postgres ENUM type
# (SQLAlchemy Enum(MechanicLocation, schema=...)), not a plain string
# column. Adding "muestras" to the MechanicLocation class in
# user_model.py only changes the Python side. The database's enum
# type also needs this value added, or any insert/update that tries
# to set current_location = "muestras" will fail with:
#   invalid input value for enum mechaniclocation: "muestras"

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, DB_SCHEMA
from sqlalchemy import text

ENUM_NAME = "mechaniclocation"  # SQLAlchemy lowercases the class name by default


def run():
    with engine.connect() as conn:
        # Confirm the enum type actually exists with this name before
        # trying to alter it, so the error message is clear if not.
        result = conn.execute(text(
            "SELECT 1 FROM pg_type t "
            "JOIN pg_namespace n ON n.oid = t.typnamespace "
            "WHERE t.typname = :enum_name AND n.nspname = :schema"
        ), {"enum_name": ENUM_NAME, "schema": DB_SCHEMA})

        exists = result.first() is not None
        conn.commit()  # close out the implicit transaction opened by the SELECT

    if not exists:
        print(
            f"Could not find enum type '{DB_SCHEMA}.{ENUM_NAME}'. "
            f"Check the actual type name with:\n"
            f"  SELECT t.typname, n.nspname FROM pg_type t "
            f"JOIN pg_namespace n ON n.oid = t.typnamespace "
            f"WHERE t.typtype = 'e';"
        )
        return

    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block on
    # Postgres < 12, and SQLAlchemy 2.x auto-begins a transaction on a
    # connection as soon as you run anything on it — so isolation_level
    # can't be changed after the fact on the same connection. Instead,
    # open a dedicated connection that's already in autocommit mode.
    autocommit_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
    with autocommit_engine.connect() as conn:
        conn.execute(text(
            f"ALTER TYPE {DB_SCHEMA}.{ENUM_NAME} ADD VALUE IF NOT EXISTS 'muestras'"
        ))
    print(f"Done. 'muestras' is now a valid value for {DB_SCHEMA}.{ENUM_NAME}.")

    # Verify
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT e.enumlabel FROM pg_enum e "
            "JOIN pg_type t ON t.oid = e.enumtypid "
            "JOIN pg_namespace n ON n.oid = t.typnamespace "
            "WHERE t.typname = :enum_name AND n.nspname = :schema "
            "ORDER BY e.enumsortorder"
        ), {"enum_name": ENUM_NAME, "schema": DB_SCHEMA})
        values = [r[0] for r in result]
        conn.commit()
        print("Current enum values:", values)


if __name__ == "__main__":
    run()
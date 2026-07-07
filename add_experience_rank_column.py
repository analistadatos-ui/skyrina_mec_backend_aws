# add_experience_rank_column.py
# Adds the experience_rank column to mechanics_db_schema.users.
# Plain integer column — no Postgres enum involved this time, so this
# is a normal transactional ALTER TABLE, unlike the muestras migration.

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, DB_SCHEMA
from sqlalchemy import text


def run():
    with engine.connect() as conn:
        conn.execute(text(
            f"ALTER TABLE {DB_SCHEMA}.users "
            f"ADD COLUMN IF NOT EXISTS experience_rank INTEGER"
        ))
        conn.commit()
        print(f"Done. {DB_SCHEMA}.users now has an experience_rank column.")

        # Verify
        result = conn.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = 'users' "
            "ORDER BY ordinal_position"
        ), {"schema": DB_SCHEMA})
        print("Current users columns:")
        for row in result:
            print(f"  {row[0]} ({row[1]})")


if __name__ == "__main__":
    run()
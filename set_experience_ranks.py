# set_experience_ranks.py
# One-time data fix: sets experience_rank for the current mechanic
# roster.
#
# Run this AFTER add_experience_rank_column.py.
#
# Ranking (lower = more senior = assigned first):
#   1  Gregoro Cuevas
#   2  Fernando Reyes
#   3  Jose Luis Carcano
#   4  Emmanuel Corona
#   5  Fernando Esteban Lopez  (least senior of the five — also acts
#      as floor supervisor, but his DB role is plain 'mecanico' like
#      the others, so a low rank alone makes him last-pick)

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine
from sqlalchemy import text

# name -> rank. Matched case-insensitively against `nombre`.
RANKS = {
    "Gregoro Cuevas": 1,
    "Fernando Reyes": 2,
    "Jose Luis Carcano": 3,
    "Emmanuel Corona": 4,
    "Fernando Esteban Lopez": 5,
}


def run():
    with engine.connect() as conn:
        for nombre, rank in RANKS.items():
            result = conn.execute(text(
                "UPDATE mechanics_db_schema.users "
                "SET experience_rank = :rank "
                "WHERE lower(nombre) = lower(:nombre) AND role = 'mecanico'"
            ), {"rank": rank, "nombre": nombre})

            if result.rowcount == 0:
                print(f"WARNING: no 'mecanico' found with nombre = '{nombre}'. "
                      f"Check spelling/casing in the database.")
            elif result.rowcount > 1:
                print(f"WARNING: {result.rowcount} rows matched nombre = '{nombre}'. "
                      f"Rank was applied to all of them — check for duplicate names.")
            else:
                print(f"Set experience_rank = {rank} for '{nombre}'")

        conn.commit()

        # Final printout of the full roster for a sanity check
        print("\nCurrent roster:")
        rows = conn.execute(text(
            "SELECT nombre, role, current_location, experience_rank "
            "FROM mechanics_db_schema.users "
            "WHERE role IN ('mecanico', 'jefe_mecanicos') "
            "ORDER BY role, experience_rank NULLS LAST"
        ))
        for row in rows:
            print(f"  {row[0]:<30} role={row[1]:<15} location={row[2]!s:<10} rank={row[3]}")


if __name__ == "__main__":
    run()
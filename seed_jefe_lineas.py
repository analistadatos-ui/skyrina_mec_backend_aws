"""
Seed script: insert jefe_linea_21 .. jefe_linea_30

Run from your project root (same place you run the app), so that the
`app.` imports resolve:

    python seed_jefes_linea.py

It is idempotent: re-running it will skip usernames that already exist
instead of erroring or creating duplicates.
"""

from app.database import SessionLocal
from app.models.user_model import User, UserRole
from app.models.linea_model import Linea
from app.core.security import hash_password


# Range of jefe_linea accounts to create (inclusive).
START = 21
END = 30


def seed():
    db = SessionLocal()
    created, skipped = [], []

    try:
        for i in range(START, END + 1):
            username = f"jefe_linea_{i}"
            password = f"jefe_l{i}"

            # Skip if the username already exists -> makes the script re-runnable.
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                skipped.append(username)
                continue

            # Try to link the user to the matching line (numero == i).
            # If there is no such line, linea_id is left NULL and we warn.
            linea = db.query(Linea).filter(Linea.numero == i).first()
            linea_id = linea.id if linea else None
            if linea is None:
                print(f"  [warn] no linea with numero={i}; linea_id left NULL for {username}")

            user = User(
                username=username,
                nombre=f"Jefe de Linea {i}",
                hashed_password=hash_password(password),
                role=UserRole.jefe_linea,
                linea_id=linea_id,
                status=True,
            )
            db.add(user)
            created.append(username)

        db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("\n=== Seed summary ===")
    print(f"Created ({len(created)}): {', '.join(created) or '-'}")
    print(f"Skipped ({len(skipped)}, already existed): {', '.join(skipped) or '-'}")


if __name__ == "__main__":
    seed()
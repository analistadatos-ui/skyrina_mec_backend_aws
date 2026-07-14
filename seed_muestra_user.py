# seed_muestra_user.py
from app.database import SessionLocal          # assumes get_db yields SessionLocal()
from app.models.user_model import User
from app.core.security import hash_password


def main():
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == "muestra").first():
            print("User 'muestra' already exists — skipping.")
            return

        user = User(
            username="muestra",
            nombre="Muestras",
            hashed_password=hash_password("muestra123"),
            role="muestra",
            linea_id=None,
            status=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Created user 'muestra' (id={user.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
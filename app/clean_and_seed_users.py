# app/clean_and_seed_users.py
import sys
import os
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.user_model import User
from app.models.linea_model import Linea
from app.core.security import hash_password


def create_lineas(db):
    """Create 20 lineas if they don't exist. Returns list of Linea rows."""
    existing = db.query(Linea).count()
    if existing == 0:
        for i in range(1, 21):
            db.add(Linea(id=uuid.uuid4(), numero=i, nombre=f"Linea {i}", activa=True))
        db.commit()
        print("Created 20 lineas")
    else:
        print(f"{existing} lineas already exist, skipping creation")
    return db.query(Linea).order_by(Linea.numero.asc()).all()


def create_users_directly():
    """Create users, linking each jefe_linea to its matching linea."""
    db = SessionLocal()
    try:
        # 1) Ensure lineas exist FIRST, so we can link users to them
        lineas = create_lineas(db)
        # map numero -> linea.id for quick lookup
        linea_by_numero = {l.numero: l.id for l in lineas}

        users = []

        # 20 jefes de linea, each linked to the matching linea
        for i in range(1, 21):
            users.append(
                User(
                    id=uuid.uuid4(),
                    username=f"jefe_linea_{i}",
                    nombre=f"Jefe Linea {i}",
                    hashed_password=hash_password(f"jefe_l{i}"),
                    role="jefe_linea",
                    linea_id=linea_by_numero.get(i),  # <-- LINKED now
                    status=True,
                )
            )

        # jefe mecanicos
        users.append(
            User(
                id=uuid.uuid4(),
                username="jefe_mecanicos",
                nombre="Jefe Mecanicos",
                hashed_password=hash_password("jefe_mec"),
                role="jefe_mecanicos",
                status=True,
            )
        )

        # mechanics
        mechanics = [
            ("fernando_reyes", "Fernando Reyes", "123456"),
            ("gregoro_cuevas", "Gregoro Cuevas", "123456"),
            ("jose_luis_carcano", "Jose Luis Carcano", "123456"),
            ("javier_juarez", "Javier Juarez", "123456"),
            ("emmanuel_corona", "Emmanuel Corona", "123456"),
            ("juan_carlos_vega", "Juan Carlos Vega", "123456"),
            ("ivan_becerra", "Ivan Becerra", "123456"),
        ]
        for username, nombre, password in mechanics:
            users.append(
                User(
                    id=uuid.uuid4(),
                    username=username,
                    nombre=nombre,
                    hashed_password=hash_password(password),
                    role="mecanico",
                    status=True,
                )
            )

        # supervisor
        users.append(
            User(
                id=uuid.uuid4(),
                username="supervisor",
                nombre="Supervisor",
                hashed_password=hash_password("supervisor"),
                role="supervisor",
                status=True,
            )
        )

        # RH
        users.append(
            User(
                id=uuid.uuid4(),
                username="rh",
                nombre="RH",
                hashed_password=hash_password("rh"),
                role="rh",
                status=True,
            )
        )

        db.add_all(users)
        db.commit()
        print(f"Created {len(users)} users (jefe_linea users linked to lineas)")
        return True

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def clean_and_seed():
    db = SessionLocal()
    try:
        count = db.query(User).count()
        db.query(User).delete()
        db.commit()
        print(f"Deleted {count} existing users")
    except Exception as e:
        db.rollback()
        print(f"Error deleting users: {e}")
        return
    finally:
        db.close()

    create_users_directly()


if __name__ == "__main__":
    print("=" * 50)
    print("CLEAN AND SEED USERS + LINEAS")
    print("=" * 50)

    response = input("This will delete ALL users and re-seed. Continue? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        sys.exit(0)

    clean_and_seed()
    print("\nDone! Users recreated and linked to lineas.")
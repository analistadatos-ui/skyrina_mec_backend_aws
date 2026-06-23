# app/clean_and_seed_users.py
import sys
import os
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.user_model import User
from app.core.security import hash_password

def create_users_directly():
    """Create users directly without importing seed_users."""
    db = SessionLocal()
    try:
        users = []
        
        # Create 20 jefes de linea
        for i in range(1, 21):
            users.append(
                User(
                    id=uuid.uuid4(),
                    username=f"jefe_linea_{i}",
                    nombre=f"Jefe Linea {i}",
                    hashed_password=hash_password(f"jefe_l{i}"),
                    role="jefe_linea",
                    linea_id=None,
                    status=True,
                )
            )
        
        # Create jefe mecanicos
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
        
        # Create mechanics
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
        
        # Create supervisor
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
        
        # Create RH
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
        print(f"✅ Created {len(users)} users with proper hashing")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        return False
    finally:
        db.close()

def clean_and_seed():
    db = SessionLocal()
    try:
        # Delete all users
        count = db.query(User).count()
        db.query(User).delete()
        db.commit()
        print(f"✅ Deleted {count} existing users")
    except Exception as e:
        db.rollback()
        print(f"❌ Error deleting users: {e}")
        return
    finally:
        db.close()
    
    # Create new users
    create_users_directly()

if __name__ == "__main__":
    print("=" * 50)
    print("CLEAN AND SEED USERS")
    print("=" * 50)
    
    response = input("⚠️  This will delete ALL users. Continue? (y/n): ")
    if response.lower() != 'y':
        print("❌ Cancelled.")
        sys.exit(0)
    
    clean_and_seed()
    print("\n✅ Done! Users recreated with new password hashing.")
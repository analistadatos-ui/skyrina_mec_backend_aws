from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.user_model import User

from app.schemas.user_schema import (
    UserRegisterSchema,
    UserLoginSchema,
)

from app.core.security import (
    hash_password,
    verify_password,
)

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


# ==========================================
# REGISTER USER
# ==========================================
@router.post("/register")
def register_user(

    payload: UserRegisterSchema,

    db: Session = Depends(get_db),
):

    existing_user = db.query(User).filter(
        User.username == payload.username
    ).first()

    if existing_user:

        raise HTTPException(
            status_code=400,
            detail="Username already exists",
        )

    hashed_pw = hash_password(
        payload.password
    )

    new_user = User(

        username=payload.username,

        nombre=payload.nombre,

        hashed_password=hashed_pw,

        role=payload.role,

        linea_id=payload.linea_id,
    )

    db.add(new_user)

    db.commit()

    db.refresh(new_user)

    return {

        "success": True,

        "message":
            "User created successfully",

        "user": {

            "id":
                str(new_user.id),

            "username":
                new_user.username,

            "nombre":
                new_user.nombre,

            "role":
                new_user.role,

            "linea_id": (

                str(new_user.linea_id)

                if new_user.linea_id

                else None
            ),
        }
    }


# ==========================================
# LOGIN USER
# ==========================================
@router.post("/login")
def login_user(

    payload: UserLoginSchema,

    db: Session = Depends(get_db),
):

    user = db.query(User).filter(
        User.username == payload.username
    ).first()

    # USER NOT FOUND
    if not user:

        raise HTTPException(

            status_code=401,

            detail="Invalid credentials",
        )

    # VERIFY PASSWORD
    password_valid = verify_password(

        payload.password,

        user.hashed_password,
    )

    if not password_valid:

        raise HTTPException(

            status_code=401,

            detail="Invalid credentials",
        )

    return {

        "success": True,

        "message":
            "Login successful",

        "user": {

            "id":
                str(user.id),

            "username":
                user.username,

            "nombre":
                user.nombre,

            "role":
                user.role,

            "linea_id": (

                str(user.linea_id)

                if user.linea_id

                else None
            ),
        }
    }
# ==========================================
# GET ALL USERS
# ==========================================
@router.get("/users")
def get_users(

    db: Session = Depends(get_db),
):

    users = db.query(User).all()

    response = []

    for user in users:

        response.append({

            "id":
                str(user.id),

            "username":
                user.username,

            "nombre":
                user.nombre,

            # SAFE ENUM
            "role":
                (
                    user.role.value
                    if hasattr(
                        user.role,
                        "value"
                    )
                    else str(user.role)
                ),

            "linea_id":
                (
                    str(user.linea_id)
                    if user.linea_id
                    else None
                ),

            # SAFE LOCATION
            "current_location":
                (
                    user.current_location.value
                    if (
                        user.current_location
                        and hasattr(
                            user.current_location,
                            "value"
                        )
                    )
                    else (
                        str(user.current_location)
                        if user.current_location
                        else "piso"
                    )
                ),
        })

    return {

        "success": True,

        "users": response,
    }
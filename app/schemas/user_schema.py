from pydantic import BaseModel
from typing import Optional


class UserRegisterSchema(BaseModel):

    username: str

    nombre: str

    password: str

    role: str

    linea_id: Optional[str] = None


class UserLoginSchema(BaseModel):

    username: str

    password: str
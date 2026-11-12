from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import Rol


def _normalizar_correo(v: str) -> str:
    return v.strip().lower()


class LoginEntrada(BaseModel):
    correo: str = Field(min_length=1)
    contrasena: str = Field(min_length=1)

    _correo = field_validator("correo")(_normalizar_correo)


class UsuarioCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    correo: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    contrasena: str = Field(min_length=8, max_length=128)
    rol: Rol

    _correo = field_validator("correo")(_normalizar_correo)


class UsuarioActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=150)
    rol: Rol | None = None
    activo: bool | None = None
    contrasena: str | None = Field(default=None, min_length=8, max_length=128)


class UsuarioSalida(BaseModel):
    """Nunca incluye el hash de la contraseña."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    correo: str
    rol: Rol
    activo: bool
    creado_en: datetime


class TokenSalida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioSalida
"""Hash de contraseñas (argon2) y tokens JWT (HS256)."""

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

ALGORITMO = "HS256"
EXPIRACION_TOKEN = timedelta(hours=8)

_hasher = PasswordHasher()


class TokenInvalido(Exception):
    """El token falta, está mal formado, firmado con otra clave o expiró."""


def hashear_contrasena(contrasena: str) -> str:
    return _hasher.hash(contrasena)


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    try:
        return _hasher.verify(hash_guardado, contrasena)
    except (VerificationError, InvalidHashError):
        return False


def crear_token(usuario_id: int, expira_en: timedelta = EXPIRACION_TOKEN) -> str:
    ahora = datetime.now(UTC)
    carga = {"sub": str(usuario_id), "iat": ahora, "exp": ahora + expira_en}
    return jwt.encode(carga, get_settings().secret_key, algorithm=ALGORITMO)


def decodificar_token(token: str) -> int:
    """Devuelve el id de usuario o lanza `TokenInvalido`."""
    try:
        carga = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[ALGORITMO],
            options={"require": ["exp", "sub"]},
        )
        return int(carga["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise TokenInvalido(str(exc)) from exc
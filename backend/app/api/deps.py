"""Dependencias de autenticación y autorización."""

from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.seguridad import TokenInvalido, decodificar_token
from app.db.session import get_db
from app.models.enums import Rol
from app.models.usuario import Usuario

_bearer = HTTPBearer(auto_error=False)


def _no_autenticado(detalle: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detalle, headers={"WWW-Authenticate": "Bearer"}
    )


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    if credenciales is None:
        raise _no_autenticado("No has iniciado sesión.")
    try:
        usuario_id = decodificar_token(credenciales.credentials)
    except TokenInvalido:
        raise _no_autenticado("Token inválido o expirado.") from None
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise _no_autenticado("Token inválido o expirado.")
    return usuario


def requiere_rol(*roles: Rol):
    permitidos = {r.value for r in roles}

    def dependencia(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in permitidos:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tienes permiso para esta acción.")
        return usuario

    return dependencia


def get_storage_dir() -> Path:
    """Raíz del almacenamiento de evidencias (sustituible en pruebas)."""
    return Path(get_settings().storage_dir)

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import usuario_actual
from app.core.config import get_settings
from app.core.limitador import limitador_login
from app.core.seguridad import crear_token, verificar_contrasena
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import LoginEntrada, TokenSalida, UsuarioSalida
from app.services import auditoria

router = APIRouter(prefix="/auth", tags=["auth"])

_CREDENCIALES_INVALIDAS = "Correo o contraseña incorrectos."
log = logging.getLogger(__name__)


@router.post("/login", response_model=TokenSalida)
def login(datos: LoginEntrada, db: Session = Depends(get_db)) -> TokenSalida:
    settings = get_settings()
    espera = limitador_login.segundos_bloqueo(datos.correo)
    if espera:
        # Mismo trato para correos existentes e inexistentes: no revela qué cuentas hay.
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Demasiados intentos fallidos. Intenta de nuevo en {espera} segundos.",
            headers={"Retry-After": str(espera)},
        )
    usuario = db.scalar(select(Usuario).where(Usuario.correo == datos.correo))
    # Mismo error para correo inexistente, contraseña mala o usuario inactivo.
    if (
        usuario is None
        or not verificar_contrasena(datos.contrasena, usuario.hash_contrasena)
        or not usuario.activo
    ):
        limitador_login.registrar_fallo(
            datos.correo,
            settings.login_max_intentos,
            settings.login_ventana_s,
            settings.login_bloqueo_s,
        )
        if limitador_login.segundos_bloqueo(datos.correo):
            log.warning("Inicio de sesión bloqueado temporalmente para %s", datos.correo)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _CREDENCIALES_INVALIDAS)
    limitador_login.registrar_exito(datos.correo)
    auditoria.registrar(db, usuario.id, "login", "usuario", usuario.id)
    db.commit()
    return TokenSalida(
        access_token=crear_token(usuario.id), usuario=UsuarioSalida.model_validate(usuario)
    )


@router.get("/yo", response_model=UsuarioSalida)
def yo(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    return usuario

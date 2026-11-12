from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import usuario_actual
from app.core.seguridad import crear_token, verificar_contrasena
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import LoginEntrada, TokenSalida, UsuarioSalida
from app.services import auditoria

router = APIRouter(prefix="/auth", tags=["auth"])

_CREDENCIALES_INVALIDAS = "Correo o contraseña incorrectos."


@router.post("/login", response_model=TokenSalida)
def login(datos: LoginEntrada, db: Session = Depends(get_db)) -> TokenSalida:
    usuario = db.scalar(select(Usuario).where(Usuario.correo == datos.correo))
    # Mismo error para correo inexistente, contraseña mala o usuario inactivo.
    if (
        usuario is None
        or not verificar_contrasena(datos.contrasena, usuario.hash_contrasena)
        or not usuario.activo
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _CREDENCIALES_INVALIDAS)
    auditoria.registrar(db, usuario.id, "login", "usuario", usuario.id)
    db.commit()
    return TokenSalida(
        access_token=crear_token(usuario.id), usuario=UsuarioSalida.model_validate(usuario)
    )


@router.get("/yo", response_model=UsuarioSalida)
def yo(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    return usuario
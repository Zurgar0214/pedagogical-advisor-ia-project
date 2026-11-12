from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import requiere_rol
from app.core.seguridad import hashear_contrasena
from app.db.session import get_db
from app.models.enums import Rol
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioActualizar, UsuarioCrear, UsuarioSalida
from app.services import auditoria

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

_solo_admin = requiere_rol(Rol.admin)


@router.get("", response_model=list[UsuarioSalida])
def listar(
    rol: Rol | None = None,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(_solo_admin),
) -> list[Usuario]:
    consulta = select(Usuario).order_by(Usuario.id)
    if rol is not None:
        consulta = consulta.where(Usuario.rol == rol.value)
    return list(db.scalars(consulta))


@router.post("", response_model=UsuarioSalida, status_code=status.HTTP_201_CREATED)
def crear(
    datos: UsuarioCrear,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(_solo_admin),
) -> Usuario:
    if db.scalar(select(Usuario.id).where(Usuario.correo == datos.correo)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese correo.")
    usuario = Usuario(
        nombre=datos.nombre,
        correo=datos.correo,
        hash_contrasena=hashear_contrasena(datos.contrasena),
        rol=datos.rol.value,
    )
    db.add(usuario)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ya existe un usuario con ese correo."
        ) from None
    auditoria.registrar(
        db, admin.id, "usuario_creado", "usuario", usuario.id, {"rol": usuario.rol}
    )
    db.commit()
    return usuario


@router.patch("/{usuario_id}", response_model=UsuarioSalida)
def actualizar(
    usuario_id: int,
    datos: UsuarioActualizar,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(_solo_admin),
) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El usuario no existe.")
    es_el_mismo = usuario.id == admin.id
    if es_el_mismo and datos.activo is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puedes desactivar tu propia cuenta.")
    if es_el_mismo and datos.rol is not None and datos.rol.value != usuario.rol:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "No puedes quitarte a ti mismo el rol de administrador."
        )

    if datos.nombre is not None:
        usuario.nombre = datos.nombre
    if datos.rol is not None and datos.rol.value != usuario.rol:
        auditoria.registrar(
            db,
            admin.id,
            "usuario_rol_cambiado",
            "usuario",
            usuario.id,
            {"anterior": usuario.rol, "nuevo": datos.rol.value},
        )
        usuario.rol = datos.rol.value
    if datos.activo is not None and datos.activo != usuario.activo:
        auditoria.registrar(
            db,
            admin.id,
            "usuario_activo_cambiado",
            "usuario",
            usuario.id,
            {"anterior": usuario.activo, "nuevo": datos.activo},
        )
        usuario.activo = datos.activo
    if datos.contrasena is not None:
        usuario.hash_contrasena = hashear_contrasena(datos.contrasena)
        auditoria.registrar(db, admin.id, "usuario_contrasena_cambiada", "usuario", usuario.id)
    db.commit()
    return usuario
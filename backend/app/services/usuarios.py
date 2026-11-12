import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.seguridad import hashear_contrasena
from app.models.enums import Rol
from app.models.usuario import Usuario
from app.services import auditoria

log = logging.getLogger(__name__)

MIN_CONTRASENA = 8


def crear_admin_inicial(db: Session, settings: Settings) -> Usuario | None:
    """Crea el admin de `ADMIN_CORREO`/`ADMIN_CONTRASENA` solo si no hay usuarios."""
    if db.scalar(select(func.count()).select_from(Usuario)):
        return None
    correo = (settings.admin_correo or "").strip().lower()
    contrasena = settings.admin_contrasena or ""
    if not correo or not contrasena:
        log.warning(
            "No hay usuarios y ADMIN_CORREO/ADMIN_CONTRASENA no están definidos: "
            "no se creó el administrador inicial."
        )
        return None
    if len(contrasena) < MIN_CONTRASENA:
        log.warning(
            "ADMIN_CONTRASENA tiene menos de %d caracteres: no se creó el administrador inicial.",
            MIN_CONTRASENA,
        )
        return None
    admin = Usuario(
        nombre="Administrador",
        correo=correo,
        hash_contrasena=hashear_contrasena(contrasena),
        rol=Rol.admin.value,
        activo=True,
    )
    db.add(admin)
    db.flush()
    auditoria.registrar(
        db, admin.id, "usuario_creado", "usuario", admin.id, {"rol": admin.rol, "inicial": True}
    )
    db.commit()
    log.info("Administrador inicial creado: %s", correo)
    return admin
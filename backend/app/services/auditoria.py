from sqlalchemy.orm import Session

from app.models.auditoria import Auditoria


def registrar(
    db: Session,
    usuario_id: int | None,
    accion: str,
    entidad: str,
    entidad_id: int | None = None,
    detalle: dict | None = None,
) -> None:
    """Añade un evento a la sesión; el commit lo hace quien llama (misma transacción).

    `detalle` no debe contener contraseñas ni hashes.
    """
    db.add(
        Auditoria(
            usuario_id=usuario_id,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            detalle=detalle,
        )
    )
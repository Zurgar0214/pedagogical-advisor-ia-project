from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import requiere_rol
from app.db.session import get_db
from app.models.enums import Rol
from app.models.usuario import Usuario
from app.schemas.laboratorio import EstudianteSalida

router = APIRouter(tags=["estudiantes"])

_gestor = requiere_rol(Rol.docente, Rol.admin)


@router.get("/estudiantes", response_model=list[EstudianteSalida])
def listar_estudiantes(
    db: Session = Depends(get_db),
    _: Usuario = Depends(_gestor),
) -> list[Usuario]:
    consulta = (
        select(Usuario)
        .where(Usuario.rol == Rol.estudiante.value, Usuario.activo.is_(True))
        .order_by(Usuario.nombre, Usuario.id)
    )
    return list(db.scalars(consulta))

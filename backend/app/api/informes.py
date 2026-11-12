"""Informe integral (RF-09) y mapa mental (RF-10)."""

from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session_factory, usuario_actual
from app.core.config import get_settings
from app.db.session import get_db
from app.informes.mapa import MapaSalida
from app.models.enums import Rol
from app.models.informe import Informe
from app.models.usuario import Usuario
from app.schemas.informe import InformeEstudiante, InformeResumen, InformeSalida
from app.services import informes as svc

router = APIRouter(tags=["informes"])


def _es_estudiante(usuario: Usuario) -> bool:
    return usuario.rol == Rol.estudiante.value


def _estudiante_accesible(db: Session, estudiante_id: int, usuario: Usuario) -> Usuario:
    """Estudiante: solo él mismo (otro id -> 404). Docente/admin: cualquier estudiante."""
    no_existe = HTTPException(status.HTTP_404_NOT_FOUND, "El estudiante no existe.")
    if _es_estudiante(usuario):
        if usuario.id != estudiante_id:
            raise no_existe
        return usuario
    estudiante = db.get(Usuario, estudiante_id)
    if estudiante is None or estudiante.rol != Rol.estudiante.value:
        raise no_existe
    return estudiante


def _informe_accesible(db: Session, informe_id: int, usuario: Usuario) -> Informe:
    informe = db.get(Informe, informe_id)
    if informe is None or (_es_estudiante(usuario) and informe.estudiante_id != usuario.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El informe no existe.")
    return informe


def _vista(informe: Informe, usuario: Usuario):
    return svc.vista_estudiante(informe) if _es_estudiante(usuario) else svc.vista_docente(informe)


def _informe_listo(informe: Informe) -> Informe:
    if informe.estado != "listo":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El informe no está listo: "
            + (
                "todavía se está generando."
                if informe.estado == "procesando"
                else "falló su generación."
            ),
        )
    return informe


@router.post(
    "/estudiantes/{estudiante_id}/informes",
    response_model=InformeSalida | InformeEstudiante,
    status_code=status.HTTP_202_ACCEPTED,
)
def crear_informe(
    estudiante_id: int,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
    fabrica: Callable[[], Session] = Depends(get_session_factory),
):
    estudiante = _estudiante_accesible(db, estudiante_id, usuario)
    en_curso = db.scalar(
        select(Informe.id).where(
            Informe.estudiante_id == estudiante.id, Informe.estado == "procesando"
        )
    )
    if en_curso is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ya hay un informe en proceso para este estudiante."
        )
    evaluaciones = svc.evaluaciones_publicadas(db, estudiante.id)
    if not evaluaciones:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, svc.MENSAJE_SIN_PUBLICADAS)
    informe = svc.iniciar_informe(db, estudiante, evaluaciones, usuario.id)
    db.commit()
    respuesta = _vista(informe, usuario)
    tareas.add_task(svc.ejecutar_informe, informe.id, fabrica, get_settings(), usuario.id)
    return respuesta


@router.get("/estudiantes/{estudiante_id}/informes", response_model=list[InformeResumen])
def listar_informes(
    estudiante_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
) -> list[InformeResumen]:
    estudiante = _estudiante_accesible(db, estudiante_id, usuario)
    consulta = (
        select(Informe)
        .where(Informe.estudiante_id == estudiante.id)
        .order_by(Informe.generado_en.desc(), Informe.id.desc())
    )
    return [svc.resumen(i) for i in db.scalars(consulta)]


@router.get("/informes/{informe_id}", response_model=InformeSalida | InformeEstudiante)
def obtener_informe(
    informe_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
):
    return _vista(_informe_accesible(db, informe_id, usuario), usuario)


@router.get("/informes/{informe_id}/mapa", response_model=MapaSalida)
def obtener_mapa(
    informe_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
) -> MapaSalida:
    informe = _informe_listo(_informe_accesible(db, informe_id, usuario))
    return svc.mapa_de(informe)


@router.get("/informes/{informe_id}/pdf")
def descargar_pdf(
    informe_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
) -> Response:
    informe = _informe_listo(_informe_accesible(db, informe_id, usuario))
    return Response(
        content=svc.pdf_de(informe),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="informe-{informe.id}.pdf"'},
    )

"""Evaluaciones con IA y revisión docente (RF-06, RF-07, RF-08)."""

from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session_factory, get_storage_dir, requiere_rol, usuario_actual
from app.api.entregas import _entrega_accesible
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.evaluacion import servicio
from app.models.base import ahora_utc
from app.models.enums import EstadoEvaluacion, Rol
from app.models.evaluacion import AjusteCriterio, Evaluacion
from app.models.usuario import Usuario
from app.schemas.evaluacion import (
    AjusteCriterioEntrada,
    ConfiguracionIA,
    EvaluacionEstudiante,
    EvaluacionSalida,
)
from app.schemas.rubrica import Rubrica
from app.services import auditoria
from app.services import evaluaciones as svc

router = APIRouter(tags=["evaluaciones"])

solo_docentes = requiere_rol(Rol.docente, Rol.admin)


def _es_estudiante(usuario: Usuario) -> bool:
    return usuario.rol == Rol.estudiante.value


def _vista(evaluacion: Evaluacion, usuario: Usuario):
    if _es_estudiante(usuario):
        return svc.vista_estudiante(evaluacion)
    return svc.vista_docente(evaluacion)


def _evaluacion_accesible(db: Session, evaluacion_id: int, usuario: Usuario) -> Evaluacion:
    """Estudiante: solo la suya y solo si está publicada; en otro caso 404 (RNF-08)."""
    evaluacion = db.get(Evaluacion, evaluacion_id)
    no_existe = HTTPException(status.HTTP_404_NOT_FOUND, "La evaluación no existe.")
    if evaluacion is None:
        raise no_existe
    if _es_estudiante(usuario) and (
        evaluacion.estado != EstadoEvaluacion.publicada.value
        or evaluacion.entrega.estudiante_id != usuario.id
    ):
        raise no_existe
    return evaluacion


def _evaluacion_docente(db: Session, evaluacion_id: int) -> Evaluacion:
    evaluacion = db.get(Evaluacion, evaluacion_id)
    if evaluacion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La evaluación no existe.")
    return evaluacion


# ---------------------------------------------------------------- crear / listar


@router.post(
    "/entregas/{entrega_id}/evaluaciones",
    response_model=EvaluacionSalida,
    status_code=status.HTTP_202_ACCEPTED,
)
def crear_evaluacion(
    entrega_id: int,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(solo_docentes),
    fabrica: Callable[[], Session] = Depends(get_session_factory),
    storage_dir: Path = Depends(get_storage_dir),
) -> EvaluacionSalida:
    entrega = _entrega_accesible(db, entrega_id, usuario)
    en_curso = db.scalar(
        select(Evaluacion.id).where(
            Evaluacion.entrega_id == entrega.id,
            Evaluacion.estado == EstadoEvaluacion.procesando.value,
        )
    )
    if en_curso is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ya hay una evaluación en proceso para esta entrega."
        )
    if entrega.estado not in ("lista", "evaluada"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La entrega no está lista para evaluar: faltan evidencias o ya se está evaluando.",
        )
    if not entrega.rubrica_version.valida:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "La rúbrica fijada en la entrega tiene inconsistencias y bloquea la evaluación.",
        )
    evaluacion = svc.iniciar_evaluacion(db, entrega, usuario.id)
    db.commit()
    respuesta = svc.vista_docente(evaluacion)
    tareas.add_task(
        svc.ejecutar_evaluacion, evaluacion.id, fabrica, get_settings(), storage_dir, usuario.id
    )
    return respuesta


@router.get(
    "/entregas/{entrega_id}/evaluaciones",
    response_model=list[EvaluacionSalida | EvaluacionEstudiante],
)
def listar_evaluaciones_entrega(
    entrega_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
):
    entrega = _entrega_accesible(db, entrega_id, usuario)
    consulta = (
        select(Evaluacion).where(Evaluacion.entrega_id == entrega.id).order_by(Evaluacion.id.desc())
    )
    if _es_estudiante(usuario):
        consulta = consulta.where(Evaluacion.estado == EstadoEvaluacion.publicada.value)
    return [_vista(e, usuario) for e in db.scalars(consulta)]


@router.get("/evaluaciones", response_model=list[EvaluacionSalida])
def cola_revision(
    estado: str = EstadoEvaluacion.en_revision.value,
    db: Session = Depends(get_db),
    _: Usuario = Depends(solo_docentes),
) -> list[EvaluacionSalida]:
    if estado not in {e.value for e in EstadoEvaluacion}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "estado: tiene un valor no permitido")
    consulta = (
        select(Evaluacion)
        .where(Evaluacion.estado == estado)
        .order_by(Evaluacion.creado_en, Evaluacion.id)
    )
    return [svc.vista_docente(e) for e in db.scalars(consulta)]


@router.get(
    "/evaluaciones/{evaluacion_id}", response_model=EvaluacionSalida | EvaluacionEstudiante
)
def obtener_evaluacion(
    evaluacion_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
):
    return _vista(_evaluacion_accesible(db, evaluacion_id, usuario), usuario)


# ---------------------------------------------------------------- revisión docente


@router.patch(
    "/evaluaciones/{evaluacion_id}/criterios/{criterio_id}", response_model=EvaluacionSalida
)
def ajustar_criterio(
    evaluacion_id: int,
    criterio_id: str,
    datos: AjusteCriterioEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(solo_docentes),
) -> EvaluacionSalida:
    evaluacion = _evaluacion_docente(db, evaluacion_id)
    if evaluacion.estado != EstadoEvaluacion.en_revision.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Solo se pueden ajustar criterios de una evaluación en revisión.",
        )
    rubrica = Rubrica.model_validate(evaluacion.rubrica_version.contenido)
    criterio = next((c for c in rubrica.criterios if c.id == criterio_id), None)
    if criterio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El criterio no existe en la rúbrica.")
    if datos.nivel not in {n.nombre for n in criterio.niveles}:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"nivel: «{datos.nivel}» no existe en el criterio «{criterio.nombre}»",
        )
    anterior = svc.niveles_finales(evaluacion)[criterio_id]
    nota_antes = evaluacion.nota_final
    db.add(
        AjusteCriterio(
            evaluacion_id=evaluacion.id,
            criterio_id=criterio_id,
            nivel_anterior=anterior,
            nivel_nuevo=datos.nivel,
            justificacion=datos.justificacion,
            usuario_id=usuario.id,
            fecha=ahora_utc(),
        )
    )
    db.flush()
    db.refresh(evaluacion, attribute_names=["ajustes"])
    nota = svc.recalcular_nota_final(evaluacion)
    auditoria.registrar(
        db,
        usuario.id,
        "criterio_ajustado",
        "evaluacion",
        evaluacion.id,
        {
            "criterio_id": criterio_id,
            "nivel_anterior": anterior,
            "nivel_nuevo": datos.nivel,
            "justificacion": datos.justificacion,
            "nota_final_anterior": str(nota_antes),
            "nota_final_nueva": str(nota),
        },
    )
    db.commit()
    return svc.vista_docente(evaluacion)


@router.post("/evaluaciones/{evaluacion_id}/aprobar", response_model=EvaluacionSalida)
def aprobar(
    evaluacion_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(solo_docentes),
) -> EvaluacionSalida:
    evaluacion = _evaluacion_docente(db, evaluacion_id)
    if evaluacion.estado != EstadoEvaluacion.en_revision.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Solo se puede aprobar una evaluación en revisión."
        )
    evaluacion.estado = EstadoEvaluacion.aprobada.value
    evaluacion.revisado_por = usuario.id
    evaluacion.aprobado_en = ahora_utc()
    auditoria.registrar(
        db,
        usuario.id,
        "evaluacion_aprobada",
        "evaluacion",
        evaluacion.id,
        {"nota_final": str(evaluacion.nota_final)},
    )
    db.commit()
    db.refresh(evaluacion)
    return svc.vista_docente(evaluacion)


@router.post("/evaluaciones/{evaluacion_id}/publicar", response_model=EvaluacionSalida)
def publicar(
    evaluacion_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(solo_docentes),
) -> EvaluacionSalida:
    evaluacion = _evaluacion_docente(db, evaluacion_id)
    if evaluacion.estado != EstadoEvaluacion.aprobada.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Solo se puede publicar una evaluación aprobada."
        )
    evaluacion.estado = EstadoEvaluacion.publicada.value
    evaluacion.publicado_en = ahora_utc()
    auditoria.registrar(
        db,
        usuario.id,
        "evaluacion_publicada",
        "evaluacion",
        evaluacion.id,
        {"nota_final": str(evaluacion.nota_final)},
    )
    db.commit()
    db.refresh(evaluacion)
    return svc.vista_docente(evaluacion)


# ---------------------------------------------------------------- configuración de IA


@router.get("/ia/configuracion", response_model=ConfiguracionIA)
def configuracion_ia(
    settings: Settings = Depends(get_settings),
    _: Usuario = Depends(solo_docentes),
) -> ConfiguracionIA:
    try:
        disponible, motivo = servicio.estado_proveedor(settings)
    except Exception:
        disponible, motivo = False, "No se pudo comprobar el estado del proveedor de IA."
    return ConfiguracionIA(
        proveedor=settings.ai_provider,
        modelo_principal=settings.ia_modelo_principal,
        modelo_escalamiento=settings.ia_modelo_escalamiento,
        umbral_confianza=settings.ia_umbral_confianza,
        disponible=disponible,
        motivo=motivo,
    )

"""Entregas, evidencias y portafolio (RF-02)."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_storage_dir, usuario_actual
from app.api.laboratorios import consulta_laboratorios, laboratorio_salida, version_vigente
from app.db.session import get_db
from app.models.entrega import Entrega, Evidencia
from app.models.enums import Rol, TipoEvidencia
from app.models.laboratorio import Laboratorio
from app.models.usuario import Usuario
from app.schemas.entrega import (
    EntregaCrear,
    EntregaResumen,
    EntregaSalida,
    EvidenciaSalida,
    PortafolioCohorte,
    PortafolioLaboratorio,
    PortafolioSalida,
)
from app.schemas.laboratorio import EstudianteSalida
from app.services import auditoria, evidencias

router = APIRouter(tags=["entregas"])

_COHORTES = (1, 2)


# ---------------------------------------------------------------- utilidades


def _es_estudiante(usuario: Usuario) -> bool:
    return usuario.rol == Rol.estudiante.value


def _opciones_entrega():
    return (
        selectinload(Entrega.evidencias),
        selectinload(Entrega.estudiante),
        selectinload(Entrega.laboratorio),
        selectinload(Entrega.rubrica_version),
    )


def _resumen(entrega: Entrega) -> dict:
    return {
        "id": entrega.id,
        "estado": entrega.estado,
        "creado_en": entrega.creado_en,
        "estudiante": entrega.estudiante,
        "laboratorio": entrega.laboratorio,
        "rubrica_version": entrega.rubrica_version,
        "faltantes": evidencias.faltantes(entrega),
    }


def entrega_resumen(entrega: Entrega) -> EntregaResumen:
    return EntregaResumen.model_validate(_resumen(entrega), from_attributes=True)


def entrega_salida(entrega: Entrega) -> EntregaSalida:
    datos = {
        **_resumen(entrega),
        "evidencias": sorted(entrega.evidencias, key=lambda e: e.id),
    }
    return EntregaSalida.model_validate(datos, from_attributes=True)


def _entrega_accesible(db: Session, entrega_id: int, usuario: Usuario) -> Entrega:
    """404 si no existe o si es de otro estudiante (RNF-08: no revelar que existe)."""
    entrega = db.scalar(
        select(Entrega).options(*_opciones_entrega()).where(Entrega.id == entrega_id)
    )
    if entrega is None or (_es_estudiante(usuario) and entrega.estudiante_id != usuario.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La entrega no existe.")
    return entrega


def _estudiante_valido(db: Session, estudiante_id: int) -> Usuario:
    estudiante = db.get(Usuario, estudiante_id)
    if estudiante is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El estudiante no existe.")
    if not _es_estudiante(estudiante):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El usuario indicado no es un estudiante.")
    return estudiante


# ---------------------------------------------------------------- portafolio


@router.get("/portafolio", response_model=PortafolioSalida)
def portafolio(
    estudiante_id: int | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
) -> PortafolioSalida:
    if _es_estudiante(usuario):
        estudiante = usuario
    else:
        if estudiante_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "estudiante_id: es obligatorio")
        estudiante = _estudiante_valido(db, estudiante_id)

    entregas = {
        e.laboratorio_id: e
        for e in db.scalars(
            select(Entrega)
            .options(*_opciones_entrega())
            .where(Entrega.estudiante_id == estudiante.id)
        )
    }
    laboratorios = list(
        db.scalars(consulta_laboratorios().order_by(Laboratorio.cohorte, Laboratorio.codigo))
    )
    cohortes = []
    for numero in _COHORTES:
        items = [
            PortafolioLaboratorio(
                laboratorio=laboratorio_salida(lab),
                entrega=entrega_resumen(entregas[lab.id]) if lab.id in entregas else None,
            )
            for lab in laboratorios
            if lab.cohorte == numero
        ]
        cohortes.append(PortafolioCohorte(cohorte=numero, laboratorios=items))
    return PortafolioSalida(
        estudiante=EstudianteSalida.model_validate(estudiante), cohortes=cohortes
    )


# ---------------------------------------------------------------- entregas


@router.get("/entregas", response_model=list[EntregaSalida])
def listar_entregas(
    estudiante_id: int | None = None,
    laboratorio_id: int | None = None,
    estado: str | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
) -> list[EntregaSalida]:
    consulta = select(Entrega).options(*_opciones_entrega()).order_by(Entrega.id)
    if _es_estudiante(usuario):
        consulta = consulta.where(Entrega.estudiante_id == usuario.id)
    elif estudiante_id is not None:
        consulta = consulta.where(Entrega.estudiante_id == estudiante_id)
    if laboratorio_id is not None:
        consulta = consulta.where(Entrega.laboratorio_id == laboratorio_id)
    if estado is not None:
        consulta = consulta.where(Entrega.estado == estado)
    return [entrega_salida(e) for e in db.scalars(consulta)]


@router.post("/entregas", response_model=EntregaSalida, status_code=status.HTTP_201_CREATED)
def crear_entrega(
    datos: EntregaCrear,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
) -> EntregaSalida:
    if _es_estudiante(usuario):
        estudiante = usuario
    else:
        if datos.estudiante_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "estudiante_id: es obligatorio")
        estudiante = _estudiante_valido(db, datos.estudiante_id)

    lab = db.scalar(consulta_laboratorios().where(Laboratorio.id == datos.laboratorio_id))
    if lab is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El laboratorio no existe.")
    vigente = version_vigente(lab)
    if vigente is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "El laboratorio no tiene rúbrica: el docente debe crearla antes de recibir entregas.",
        )
    if not vigente.valida:
        detalle = " ".join(vigente.inconsistencias or [])
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "La rúbrica vigente del laboratorio tiene inconsistencias y bloquea las entregas. "
            f"{detalle}".strip(),
        )

    conflicto = HTTPException(
        status.HTTP_409_CONFLICT, "Ya existe una entrega de este estudiante para el laboratorio."
    )
    if db.scalar(
        select(Entrega.id).where(
            Entrega.estudiante_id == estudiante.id, Entrega.laboratorio_id == lab.id
        )
    ):
        raise conflicto
    entrega = Entrega(
        estudiante_id=estudiante.id,
        laboratorio_id=lab.id,
        rubrica_version_id=vigente.id,
        estado="borrador",
    )
    db.add(entrega)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise conflicto from None
    auditoria.registrar(
        db,
        usuario.id,
        "entrega_creada",
        "entrega",
        entrega.id,
        {
            "laboratorio_id": lab.id,
            "estudiante_id": estudiante.id,
            "rubrica_version_id": vigente.id,
        },
    )
    db.commit()
    return entrega_salida(_entrega_accesible(db, entrega.id, usuario))


@router.get("/entregas/{entrega_id}", response_model=EntregaSalida)
def obtener_entrega(
    entrega_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
) -> EntregaSalida:
    return entrega_salida(_entrega_accesible(db, entrega_id, usuario))


# ---------------------------------------------------------------- evidencias


@router.post(
    "/entregas/{entrega_id}/evidencias",
    response_model=EvidenciaSalida,
    status_code=status.HTTP_201_CREATED,
)
def cargar_evidencia(
    entrega_id: int,
    tipo: Annotated[TipoEvidencia, Form()],
    archivo: Annotated[UploadFile | None, File()] = None,
    url: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
    storage_dir: Path = Depends(get_storage_dir),
) -> Evidencia:
    entrega = _entrega_accesible(db, entrega_id, usuario)
    if entrega.estado not in evidencias.ESTADOS_EDITABLES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La entrega ya está en evaluación y no admite cambios en sus evidencias.",
        )
    if tipo is TipoEvidencia.informe_pdf and any(
        e.tipo == tipo.value for e in entrega.evidencias
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La entrega ya tiene un informe PDF. Bórralo para subir otro.",
        )

    if tipo is TipoEvidencia.repo_github:
        procesada = evidencias.procesar_repo(url)
    else:
        if archivo is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "archivo: es obligatorio")
        procesada = evidencias.guardar_archivo(
            storage_dir, entrega.id, tipo, archivo.file, archivo.filename
        )

    evidencia = Evidencia(
        entrega_id=entrega.id,
        tipo=tipo.value,
        ruta_archivo=procesada.ruta_relativa,
        url=procesada.url,
        nombre_original=procesada.nombre_original,
        sha256=procesada.sha256,
        tamano_bytes=procesada.tamano_bytes,
        texto_extraido=procesada.texto_extraido,
        detalle=procesada.detalle,
    )
    try:
        db.add(evidencia)
        entrega.evidencias.append(evidencia)
        db.flush()
        evidencias.recalcular_estado(entrega)
        auditoria.registrar(
            db,
            usuario.id,
            "evidencia_cargada",
            "evidencia",
            evidencia.id,
            {"entrega_id": entrega.id, "tipo": tipo.value, "sha256": procesada.sha256},
        )
        db.commit()
    except BaseException:
        db.rollback()
        evidencias.borrar_archivo(storage_dir, procesada.ruta_relativa)
        raise
    return evidencia


@router.delete(
    "/entregas/{entrega_id}/evidencias/{evidencia_id}", status_code=status.HTTP_204_NO_CONTENT
)
def borrar_evidencia(
    entrega_id: int,
    evidencia_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
    storage_dir: Path = Depends(get_storage_dir),
) -> Response:
    entrega = _entrega_accesible(db, entrega_id, usuario)
    evidencia = next((e for e in entrega.evidencias if e.id == evidencia_id), None)
    if evidencia is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La evidencia no existe.")
    if entrega.estado not in evidencias.ESTADOS_EDITABLES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La entrega ya está en evaluación y no admite cambios en sus evidencias.",
        )
    ruta = evidencia.ruta_archivo
    detalle = {"entrega_id": entrega.id, "tipo": evidencia.tipo, "sha256": evidencia.sha256}
    entrega.evidencias.remove(evidencia)
    db.delete(evidencia)
    db.flush()
    evidencias.recalcular_estado(entrega)
    auditoria.registrar(db, usuario.id, "evidencia_eliminada", "evidencia", evidencia_id, detalle)
    db.commit()
    evidencias.borrar_archivo(storage_dir, ruta)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/evidencias/{evidencia_id}/archivo")
def descargar_archivo(
    evidencia_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
    storage_dir: Path = Depends(get_storage_dir),
) -> FileResponse:
    evidencia = db.get(Evidencia, evidencia_id)
    if evidencia is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La evidencia no existe.")
    # Mismo 404 si la entrega es ajena: no se revela que la evidencia existe.
    _entrega_accesible(db, evidencia.entrega_id, usuario)
    ruta = (
        evidencias.ruta_absoluta(storage_dir, evidencia.ruta_archivo)
        if evidencia.ruta_archivo
        else None
    )
    if ruta is None or not ruta.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La evidencia no tiene un archivo.")
    nombre = evidencias.nombre_seguro(evidencia.nombre_original, ruta.suffix)
    return FileResponse(
        ruta,
        filename=nombre,
        media_type="application/octet-stream",
        content_disposition_type="attachment",
    )

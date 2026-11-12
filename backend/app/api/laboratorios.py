"""Laboratorios y rúbricas versionadas (RF-01, RF-03, RF-05)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import requiere_rol, usuario_actual
from app.db.session import get_db
from app.models.enums import Rol
from app.models.laboratorio import Laboratorio, Rubrica, RubricaVersion
from app.models.usuario import Usuario
from app.schemas.laboratorio import (
    LaboratorioActualizar,
    LaboratorioCrear,
    LaboratorioSalida,
    RubricaDeLaboratorio,
    RubricaVersionResumen,
    RubricaVersionSalida,
    RubricaVigente,
    UsuarioBasico,
    ValidacionSalida,
)
from app.schemas.rubrica import Rubrica as RubricaContenido
from app.services import auditoria
from app.services.validacion_rubrica import validar_rubrica

router = APIRouter(tags=["laboratorios"])

_gestor = requiere_rol(Rol.docente, Rol.admin)


# ---------------------------------------------------------------- utilidades compartidas


def version_vigente(lab: Laboratorio) -> RubricaVersion | None:
    """La versión vigente es la de número más alto."""
    if lab.rubrica is None or not lab.rubrica.versiones:
        return None
    return max(lab.rubrica.versiones, key=lambda v: v.numero)


def laboratorio_salida(lab: Laboratorio) -> LaboratorioSalida:
    vigente = version_vigente(lab)
    return LaboratorioSalida(
        id=lab.id,
        cohorte=lab.cohorte,
        codigo=lab.codigo,
        titulo=lab.titulo,
        descripcion=lab.descripcion,
        objetivos=lab.objetivos,
        temas=list(lab.temas or []),
        rubrica_vigente=(
            RubricaVigente(version_id=vigente.id, numero=vigente.numero, valida=vigente.valida)
            if vigente
            else None
        ),
    )


def consulta_laboratorios():
    return select(Laboratorio).options(
        selectinload(Laboratorio.rubrica).selectinload(Rubrica.versiones)
    )


def _autor(db: Session, version: RubricaVersion) -> UsuarioBasico | None:
    if version.creado_por is None:
        return None
    usuario = db.get(Usuario, version.creado_por)
    return UsuarioBasico.model_validate(usuario) if usuario else None


def _version_salida(db: Session, v: RubricaVersion) -> RubricaVersionSalida:
    return RubricaVersionSalida(
        id=v.id,
        numero=v.numero,
        valida=v.valida,
        inconsistencias=list(v.inconsistencias or []),
        contenido=RubricaContenido.model_validate(v.contenido),
        creado_por=_autor(db, v),
        creado_en=v.creado_en,
    )


def _version_resumen(db: Session, v: RubricaVersion) -> RubricaVersionResumen:
    return RubricaVersionResumen(
        id=v.id,
        numero=v.numero,
        valida=v.valida,
        inconsistencias=list(v.inconsistencias or []),
        creado_por=_autor(db, v),
        creado_en=v.creado_en,
    )


def _obtener_laboratorio(db: Session, laboratorio_id: int) -> Laboratorio:
    lab = db.scalar(consulta_laboratorios().where(Laboratorio.id == laboratorio_id))
    if lab is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El laboratorio no existe.")
    return lab


def _error_codigo_repetido() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "Ya existe un laboratorio con ese código.")


# ---------------------------------------------------------------- laboratorios


@router.get("/laboratorios", response_model=list[LaboratorioSalida])
def listar_laboratorios(
    cohorte: int | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(usuario_actual),
) -> list[LaboratorioSalida]:
    consulta = consulta_laboratorios().order_by(Laboratorio.cohorte, Laboratorio.codigo)
    if cohorte is not None:
        consulta = consulta.where(Laboratorio.cohorte == cohorte)
    return [laboratorio_salida(lab) for lab in db.scalars(consulta)]


@router.post("/laboratorios", response_model=LaboratorioSalida, status_code=status.HTTP_201_CREATED)
def crear_laboratorio(
    datos: LaboratorioCrear,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_gestor),
) -> LaboratorioSalida:
    if db.scalar(select(Laboratorio.id).where(Laboratorio.codigo == datos.codigo)):
        raise _error_codigo_repetido()
    lab = Laboratorio(**datos.model_dump())
    db.add(lab)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _error_codigo_repetido() from None
    auditoria.registrar(
        db,
        usuario.id,
        "laboratorio_creado",
        "laboratorio",
        lab.id,
        {"codigo": lab.codigo, "cohorte": lab.cohorte},
    )
    db.commit()
    return laboratorio_salida(_obtener_laboratorio(db, lab.id))


@router.get("/laboratorios/{laboratorio_id}", response_model=LaboratorioSalida)
def obtener_laboratorio(
    laboratorio_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(usuario_actual),
) -> LaboratorioSalida:
    return laboratorio_salida(_obtener_laboratorio(db, laboratorio_id))


@router.patch("/laboratorios/{laboratorio_id}", response_model=LaboratorioSalida)
def actualizar_laboratorio(
    laboratorio_id: int,
    datos: LaboratorioActualizar,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_gestor),
) -> LaboratorioSalida:
    lab = _obtener_laboratorio(db, laboratorio_id)
    cambios = datos.model_dump(exclude_unset=True, exclude_none=True)
    if (
        "codigo" in cambios
        and cambios["codigo"] != lab.codigo
        and db.scalar(select(Laboratorio.id).where(Laboratorio.codigo == cambios["codigo"]))
    ):
        raise _error_codigo_repetido()
    for campo, valor in cambios.items():
        setattr(lab, campo, valor)
    if cambios:
        auditoria.registrar(
            db,
            usuario.id,
            "laboratorio_editado",
            "laboratorio",
            lab.id,
            {"campos": sorted(cambios)},
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _error_codigo_repetido() from None
    return laboratorio_salida(lab)


# ---------------------------------------------------------------- rúbricas


@router.get("/laboratorios/{laboratorio_id}/rubrica", response_model=RubricaDeLaboratorio)
def obtener_rubrica(
    laboratorio_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(usuario_actual),
) -> RubricaDeLaboratorio:
    lab = _obtener_laboratorio(db, laboratorio_id)
    vigente = version_vigente(lab)
    versiones = sorted(lab.rubrica.versiones, key=lambda v: v.numero) if lab.rubrica else []
    return RubricaDeLaboratorio(
        vigente=_version_salida(db, vigente) if vigente else None,
        versiones=[_version_resumen(db, v) for v in versiones],
    )


@router.post(
    "/laboratorios/{laboratorio_id}/rubrica/versiones",
    response_model=RubricaVersionSalida,
    status_code=status.HTTP_201_CREATED,
)
def crear_version_rubrica(
    laboratorio_id: int,
    contenido: RubricaContenido,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_gestor),
) -> RubricaVersionSalida:
    lab = _obtener_laboratorio(db, laboratorio_id)
    # Siempre se guarda, aunque sea inválida, para poder corregirla en una versión posterior.
    inconsistencias = validar_rubrica(contenido)
    if lab.rubrica is None:
        lab.rubrica = Rubrica(laboratorio_id=lab.id)
        db.add(lab.rubrica)
        db.flush()
    anterior = version_vigente(lab)
    numero = (anterior.numero if anterior else 0) + 1
    # El campo `version` del contenido lo fija el servidor (igual al número de la tabla).
    datos = contenido.model_copy(update={"version": numero}).model_dump()
    version = RubricaVersion(
        rubrica_id=lab.rubrica.id,
        numero=numero,
        contenido=datos,
        valida=not inconsistencias,
        inconsistencias=inconsistencias,
        creado_por=usuario.id,
    )
    db.add(version)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Otra persona creó una versión al mismo tiempo; vuelve a intentarlo.",
        ) from None
    auditoria.registrar(
        db,
        usuario.id,
        "rubrica_version_creada",
        "rubrica_version",
        version.id,
        {"laboratorio_id": lab.id, "numero": numero, "valida": version.valida},
    )
    db.commit()
    return _version_salida(db, version)


@router.get("/rubrica-versiones/{version_id}", response_model=RubricaVersionSalida)
def obtener_version(
    version_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(usuario_actual),
) -> RubricaVersionSalida:
    version = db.get(RubricaVersion, version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La versión de rúbrica no existe.")
    return _version_salida(db, version)


@router.post("/rubricas/validar", response_model=ValidacionSalida)
def validar(contenido: RubricaContenido, _: Usuario = Depends(_gestor)) -> ValidacionSalida:
    inconsistencias = validar_rubrica(contenido)
    return ValidacionSalida(valida=not inconsistencias, inconsistencias=inconsistencias)

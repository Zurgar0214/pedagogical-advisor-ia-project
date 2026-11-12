"""Orquestación del informe integral y el mapa mental (RF-09, RF-10)."""

import logging
from collections.abc import Callable
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.evaluacion import informe as sintesis_ia
from app.evaluacion.contrato import ErrorEvaluacion, ResultadoIA
from app.informes import mapa as mapa_mod
from app.informes import pdf as pdf_mod
from app.informes.agregacion import (
    EvaluacionPublicada,
    LaboratorioCatalogo,
    construir_agregado,
    normalizar_tema,
)
from app.informes.contrato import CATEGORIAS_IA, AgregadoInforme, SintesisInforme
from app.models.base import ahora_utc
from app.models.entrega import Entrega
from app.models.enums import EstadoEvaluacion
from app.models.evaluacion import Evaluacion
from app.models.informe import Informe
from app.models.laboratorio import Laboratorio
from app.models.usuario import Usuario
from app.schemas.informe import InformeEstudiante, InformeResumen, InformeSalida
from app.schemas.rubrica import Rubrica
from app.services import auditoria
from app.services import evaluaciones as svc_eval

log = logging.getLogger(__name__)

MENSAJE_ERROR_INTERNO = (
    "El informe no pudo generarse por un error interno. "
    "Inténtalo de nuevo; si persiste, avisa al administrador."
)
MENSAJE_SIN_PUBLICADAS = "El estudiante no tiene evaluaciones publicadas para generar el informe."


# ---------------------------------------------------------------- datos de entrada


def evaluaciones_publicadas(db: Session, estudiante_id: int) -> list[Evaluacion]:
    """La evaluación publicada más reciente de cada entrega del estudiante."""
    consulta = (
        select(Evaluacion)
        .join(Entrega, Entrega.id == Evaluacion.entrega_id)
        .where(
            Entrega.estudiante_id == estudiante_id,
            Evaluacion.estado == EstadoEvaluacion.publicada.value,
        )
        .order_by(Evaluacion.publicado_en, Evaluacion.id)
    )
    por_entrega = {e.entrega_id: e for e in db.scalars(consulta)}  # la última pisa a las anteriores
    return sorted(por_entrega.values(), key=lambda e: e.id)


def _a_entrada(evaluacion: Evaluacion) -> EvaluacionPublicada:
    lab = evaluacion.entrega.laboratorio
    return EvaluacionPublicada(
        evaluacion_id=evaluacion.id,
        laboratorio=LaboratorioCatalogo(
            id=lab.id, codigo=lab.codigo, cohorte=lab.cohorte, temas=list(lab.temas or [])
        ),
        titulo=lab.titulo,
        nota_final=float(evaluacion.nota_final),
        publicado_en=evaluacion.publicado_en,
        rubrica=Rubrica.model_validate(evaluacion.rubrica_version.contenido),
        # Misma lógica que la vista de la evaluación: nivel de la IA + último ajuste docente.
        niveles_finales=svc_eval.niveles_finales(evaluacion),
        resultado=ResultadoIA.model_validate(evaluacion.resultado_ia),
    )


def agregar_estudiante(
    db: Session, estudiante: Usuario, evaluaciones: list[Evaluacion]
) -> AgregadoInforme:
    catalogo = [
        LaboratorioCatalogo(
            id=lab.id, codigo=lab.codigo, cohorte=lab.cohorte, temas=list(lab.temas or [])
        )
        for lab in db.scalars(select(Laboratorio).order_by(Laboratorio.id))
    ]
    return construir_agregado(estudiante.nombre, [_a_entrada(e) for e in evaluaciones], catalogo)


# ---------------------------------------------------------------- generación


def iniciar_informe(
    db: Session, estudiante: Usuario, evaluaciones: list[Evaluacion], por: int
) -> Informe:
    informe = Informe(
        estudiante_id=estudiante.id,
        estado="procesando",
        generado_por=por,
        evaluaciones_incluidas=[e.id for e in evaluaciones],
    )
    db.add(informe)
    db.flush()
    auditoria.registrar(
        db,
        por,
        "informe_iniciado",
        "informe",
        informe.id,
        {"estudiante_id": estudiante.id, "evaluaciones_incluidas": informe.evaluaciones_incluidas},
    )
    return informe


def _fallar(db: Session, informe_id: int, mensaje: str, usuario_id: int | None) -> None:
    informe = db.get(Informe, informe_id)
    informe.estado = "error"
    informe.error = mensaje
    auditoria.registrar(
        db, usuario_id, "informe_fallido", "informe", informe_id, {"error": mensaje}
    )
    db.commit()


def temas_con_categoria(agregado: AgregadoInforme, sintesis: SintesisInforme) -> dict[str, str]:
    """Categoría de cada tema del agregado; lo no clasificado o inválido va a «Otros»."""
    propuesta = {normalizar_tema(c.tema): c.categoria for c in sintesis.clasificacion}
    salida = {}
    for t in agregado.temas:
        categoria = propuesta.get(normalizar_tema(t.tema), "Otros")
        salida[t.tema] = categoria if categoria in CATEGORIAS_IA else "Otros"
    return salida


def ejecutar_informe(
    informe_id: int,
    fabrica_sesion: Callable[[], Session],
    settings: Settings,
    usuario_id: int | None = None,
) -> None:
    """Tarea en segundo plano: usa su propia sesión de BD y nunca propaga excepciones."""
    with fabrica_sesion() as db:
        informe = db.get(Informe, informe_id)
        if informe is None or informe.estado != "procesando":
            return
        try:
            evaluaciones = evaluaciones_publicadas(db, informe.estudiante_id)
            if not evaluaciones:
                raise ErrorEvaluacion(MENSAJE_SIN_PUBLICADAS)
            agregado = agregar_estudiante(db, informe.estudiante, evaluaciones)
            resultado = sintesis_ia.sintetizar(agregado, settings)

            costo = sum((Decimal(str(u.costo_usd_estimado)) for u in resultado.uso), Decimal(0))
            informe.evaluaciones_incluidas = [e.id for e in evaluaciones]
            informe.agregado = agregado.model_dump(mode="json")
            informe.sintesis = resultado.sintesis.model_dump(mode="json")
            informe.temas_categoria = temas_con_categoria(agregado, resultado.sintesis)
            informe.proveedor = resultado.proveedor
            informe.modelo = resultado.modelo
            informe.version_prompt = resultado.version_prompt
            informe.advertencias = list(resultado.advertencias)
            informe.uso = [u.model_dump(mode="json") for u in resultado.uso]
            informe.costo_usd_estimado = costo.quantize(Decimal("0.000001"))
            informe.error = None
            informe.estado = "listo"
            informe.generado_en = ahora_utc()
            auditoria.registrar(
                db,
                usuario_id,
                "informe_generado",
                "informe",
                informe.id,
                {
                    "estudiante_id": informe.estudiante_id,
                    "evaluaciones_incluidas": informe.evaluaciones_incluidas,
                    "proveedor": resultado.proveedor,
                    "modelo": resultado.modelo,
                },
            )
            db.commit()
        except ErrorEvaluacion as exc:
            db.rollback()
            _fallar(db, informe_id, str(exc), usuario_id)
        except Exception:
            log.exception("Falló el informe %s", informe_id)
            db.rollback()
            _fallar(db, informe_id, MENSAJE_ERROR_INTERNO, usuario_id)


# ---------------------------------------------------------------- vistas


def _base(informe: Informe) -> dict:
    return {
        "id": informe.id,
        "estado": informe.estado,
        "error": informe.error,
        "estudiante": informe.estudiante,
        "generado_en": informe.generado_en,
        "generado_por": informe.generador,
        "evaluaciones_incluidas": list(informe.evaluaciones_incluidas or []),
        "agregado": informe.agregado,
        "sintesis": informe.sintesis,
        "temas_categoria": informe.temas_categoria or {},
        "proveedor": informe.proveedor,
        "modelo": informe.modelo,
        "version_prompt": informe.version_prompt,
    }


def vista_docente(informe: Informe) -> InformeSalida:
    costo = informe.costo_usd_estimado
    return InformeSalida.model_validate(
        {
            **_base(informe),
            "advertencias": informe.advertencias or [],
            "uso": informe.uso or [],
            "costo_usd_estimado": float(costo) if costo is not None else None,
        },
        from_attributes=True,
    )


def vista_estudiante(informe: Informe) -> InformeEstudiante:
    return InformeEstudiante.model_validate(_base(informe), from_attributes=True)


def resumen(informe: Informe) -> InformeResumen:
    promedio = (informe.agregado or {}).get("promedio_general")
    return InformeResumen(
        id=informe.id,
        estado=informe.estado,
        generado_en=informe.generado_en,
        evaluaciones_incluidas=list(informe.evaluaciones_incluidas or []),
        promedio_general=promedio,
    )


def mapa_de(informe: Informe) -> mapa_mod.MapaSalida:
    return mapa_mod.construir_mapa(
        informe.id,
        {"id": informe.estudiante.id, "nombre": informe.estudiante.nombre},
        AgregadoInforme.model_validate(informe.agregado),
        SintesisInforme.model_validate(informe.sintesis),
        informe.temas_categoria or {},
    )


def pdf_de(informe: Informe) -> bytes:
    return pdf_mod.generar_pdf(
        informe.estudiante.nombre,
        informe.generado_en,
        AgregadoInforme.model_validate(informe.agregado),
        SintesisInforme.model_validate(informe.sintesis),
        informe.temas_categoria or {},
    )

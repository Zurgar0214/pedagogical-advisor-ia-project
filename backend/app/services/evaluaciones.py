"""Orquestación de evaluaciones: contexto, ejecución, vistas y ajustes (RF-06/07/08)."""

import logging
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.evaluacion import servicio
from app.evaluacion.contrato import (
    ContextoEvaluacion,
    ErrorEvaluacion,
    EvidenciaContexto,
    LaboratorioContexto,
    ResultadoIA,
)
from app.models.entrega import Entrega
from app.models.enums import EstadoEvaluacion
from app.models.evaluacion import AjusteCriterio, Evaluacion
from app.schemas.evaluacion import (
    AjusteDocente,
    CriterioEstudiante,
    CriterioEvaluado,
    EvaluacionEstudiante,
    EvaluacionSalida,
    NivelDisponible,
)
from app.schemas.rubrica import Rubrica
from app.services import auditoria, evidencias
from app.services.calculo_nota import calcular_nota

log = logging.getLogger(__name__)

MENSAJE_ERROR_INTERNO = (
    "La evaluación no pudo completarse por un error interno. "
    "Inténtalo de nuevo; si persiste, avisa al administrador."
)


# ---------------------------------------------------------------- contexto


def construir_contexto(
    entrega: Entrega, rubrica_json: dict, storage_dir: Path
) -> ContextoEvaluacion:
    """Contexto para el pipeline con la versión de rúbrica fijada en la entrega."""
    lab = entrega.laboratorio
    items = []
    for ev in sorted(entrega.evidencias, key=lambda e: e.id):
        ruta = None
        if ev.ruta_archivo:
            absoluta = evidencias.ruta_absoluta(storage_dir, ev.ruta_archivo)
            ruta = str(absoluta) if absoluta is not None else None
        items.append(
            EvidenciaContexto(
                id=ev.id,
                tipo=ev.tipo,
                nombre_original=ev.nombre_original,
                ruta_archivo=ruta,
                url=ev.url,
                texto_extraido=ev.texto_extraido,
            )
        )
    return ContextoEvaluacion(
        laboratorio=LaboratorioContexto(
            codigo=lab.codigo,
            titulo=lab.titulo,
            descripcion=lab.descripcion or "",
            objetivos=lab.objetivos or "",
            temas=list(lab.temas or []),
        ),
        rubrica=Rubrica.model_validate(rubrica_json),
        evidencias=items,
    )


# ---------------------------------------------------------------- ejecución


def iniciar_evaluacion(db: Session, entrega: Entrega, usuario_id: int) -> Evaluacion:
    """Crea la evaluación `procesando` con la rúbrica fijada y pone la entrega en evaluación."""
    evaluacion = Evaluacion(
        entrega_id=entrega.id,
        rubrica_version_id=entrega.rubrica_version_id,
        estado=EstadoEvaluacion.procesando.value,
    )
    db.add(evaluacion)
    entrega.estado = "en_evaluacion"
    db.flush()
    auditoria.registrar(
        db,
        usuario_id,
        "evaluacion_iniciada",
        "evaluacion",
        evaluacion.id,
        {"entrega_id": entrega.id, "rubrica_version_id": entrega.rubrica_version_id},
    )
    return evaluacion


def _fallar(db: Session, evaluacion_id: int, mensaje: str, usuario_id: int | None) -> None:
    evaluacion = db.get(Evaluacion, evaluacion_id)
    evaluacion.estado = EstadoEvaluacion.error.value
    evaluacion.error = mensaje
    entrega = db.get(Entrega, evaluacion.entrega_id)
    if entrega is not None:
        entrega.estado = "lista"
    auditoria.registrar(
        db, usuario_id, "evaluacion_fallida", "evaluacion", evaluacion_id, {"error": mensaje}
    )
    db.commit()


def ejecutar_evaluacion(
    evaluacion_id: int,
    fabrica_sesion: Callable[[], Session],
    settings: Settings,
    storage_dir: Path,
    usuario_id: int | None = None,
) -> None:
    """Tarea en segundo plano: usa su propia sesión de BD y nunca propaga excepciones."""
    with fabrica_sesion() as db:
        evaluacion = db.get(Evaluacion, evaluacion_id)
        if evaluacion is None or evaluacion.estado != EstadoEvaluacion.procesando.value:
            return
        try:
            entrega = db.scalar(
                select(Entrega)
                .options(selectinload(Entrega.evidencias), selectinload(Entrega.laboratorio))
                .where(Entrega.id == evaluacion.entrega_id)
            )
            version = evaluacion.rubrica_version
            contexto = construir_contexto(entrega, version.contenido, storage_dir)
            resultado = servicio.evaluar(contexto, settings)

            # La nota la calcula SIEMPRE el backend, con los niveles elegidos.
            nota = calcular_nota(contexto.rubrica, resultado.niveles_elegidos).nota
            costo = sum((Decimal(str(u.costo_usd_estimado)) for u in resultado.uso), Decimal(0))

            evaluacion.resultado_ia = {
                **resultado.resultado.model_dump(mode="json"),
                "niveles_elegidos": dict(resultado.niveles_elegidos),
            }
            evaluacion.verificacion = resultado.verificacion.model_dump(mode="json")
            evaluacion.uso = [u.model_dump(mode="json") for u in resultado.uso]
            evaluacion.costo_usd_estimado = costo.quantize(Decimal("0.000001"))
            evaluacion.proveedor = resultado.proveedor
            evaluacion.modelo = resultado.modelo_principal
            evaluacion.modelo_escalamiento = settings.ia_modelo_escalamiento
            evaluacion.version_prompt = resultado.version_prompt
            evaluacion.requiere_revision = resultado.requiere_revision
            evaluacion.advertencias = list(resultado.advertencias)
            evaluacion.parametros = {
                "umbral_confianza": settings.ia_umbral_confianza,
                "modelo_principal": resultado.modelo_principal,
                "modelo_escalamiento": settings.ia_modelo_escalamiento,
                "criterios_escalados": list(resultado.criterios_escalados),
                "rubrica_version_id": version.id,
                "rubrica_version_numero": version.numero,
            }
            evaluacion.nota_preliminar = nota
            evaluacion.nota_final = nota
            evaluacion.estado = EstadoEvaluacion.en_revision.value
            entrega.estado = "evaluada"
            auditoria.registrar(
                db,
                usuario_id,
                "evaluacion_finalizada",
                "evaluacion",
                evaluacion.id,
                {
                    "nota_preliminar": str(nota),
                    "proveedor": resultado.proveedor,
                    "modelo": resultado.modelo_principal,
                    "requiere_revision": resultado.requiere_revision,
                },
            )
            db.commit()
        except ErrorEvaluacion as exc:
            db.rollback()
            _fallar(db, evaluacion_id, str(exc), usuario_id)
        except Exception:
            log.exception("Falló la evaluación %s", evaluacion_id)
            db.rollback()
            _fallar(db, evaluacion_id, MENSAJE_ERROR_INTERNO, usuario_id)


# ---------------------------------------------------------------- niveles y notas


def niveles_ia(evaluacion: Evaluacion) -> dict[str, str]:
    return dict((evaluacion.resultado_ia or {}).get("niveles_elegidos", {}))


def niveles_finales(evaluacion: Evaluacion) -> dict[str, str]:
    """Nivel de la IA, sustituido por el último ajuste docente de cada criterio."""
    niveles = niveles_ia(evaluacion)
    for ajuste in evaluacion.ajustes:  # ordenados por id: el último gana
        niveles[ajuste.criterio_id] = ajuste.nivel_nuevo
    return niveles


def recalcular_nota_final(evaluacion: Evaluacion) -> Decimal:
    rubrica = Rubrica.model_validate(evaluacion.rubrica_version.contenido)
    nota = calcular_nota(rubrica, niveles_finales(evaluacion)).nota
    evaluacion.nota_final = nota
    return nota


# ---------------------------------------------------------------- vistas


def _ajuste_salida(ajuste: AjusteCriterio) -> AjusteDocente:
    return AjusteDocente.model_validate(
        {
            "nivel": ajuste.nivel_nuevo,
            "justificacion": ajuste.justificacion,
            "usuario": ajuste.usuario,
            "fecha": ajuste.fecha,
            "nivel_anterior": ajuste.nivel_anterior,
        },
        from_attributes=True,
    )


def _criterios(evaluacion: Evaluacion, estudiante: bool) -> list:
    if not evaluacion.resultado_ia:
        return []
    rubrica = Rubrica.model_validate(evaluacion.rubrica_version.contenido)
    competencias = {c.id: c.nombre for c in rubrica.competencias}
    ia = ResultadoIA.model_validate(evaluacion.resultado_ia)
    por_id = {c.criterio_id: c for c in ia.criterios}
    elegidos = niveles_ia(evaluacion)
    finales = niveles_finales(evaluacion)
    historial: dict[str, list[AjusteCriterio]] = {}
    for a in evaluacion.ajustes:
        historial.setdefault(a.criterio_id, []).append(a)

    salida = []
    for crit in rubrica.criterios:
        res = por_id.get(crit.id)
        niveles = [NivelDisponible(**n.model_dump()) for n in crit.niveles]
        valores = {n.nombre: n.valor for n in crit.niveles}
        nivel_final = finales.get(crit.id)
        ajustes = historial.get(crit.id, [])
        comunes = {
            "criterio_id": crit.id,
            "criterio": crit.nombre,
            "competencia": competencias.get(crit.competencia_id, crit.competencia_id),
            "peso": crit.peso,
            "niveles_disponibles": niveles,
            "nivel_final": nivel_final,
            "valor_nivel_final": valores.get(nivel_final) if nivel_final else None,
            "justificacion": res.justificacion if res else "",
            "evidencias": res.evidencias if res else [],
            "fortalezas": res.fortalezas if res else [],
            "debilidades": res.debilidades if res else [],
            "recomendaciones": res.recomendaciones if res else [],
            "ajuste_docente": _ajuste_salida(ajustes[-1]) if ajustes else None,
        }
        if estudiante:
            salida.append(CriterioEstudiante(**comunes))
        else:
            salida.append(
                CriterioEvaluado(
                    **comunes,
                    nivel_ia=elegidos.get(crit.id),
                    confianza=res.confianza if res else None,
                    modelo=res.modelo if res else "",
                    escalado=res.escalado if res else False,
                    historial_ajustes=[_ajuste_salida(a) for a in ajustes],
                )
            )
    return salida


def _base(evaluacion: Evaluacion) -> dict:
    ia = ResultadoIA.model_validate(evaluacion.resultado_ia) if evaluacion.resultado_ia else None
    entrega = evaluacion.entrega
    return {
        "id": evaluacion.id,
        "entrega_id": evaluacion.entrega_id,
        "estado": evaluacion.estado,
        "estudiante": entrega.estudiante,
        "laboratorio": entrega.laboratorio,
        "rubrica_version": evaluacion.rubrica_version,
        "proveedor": evaluacion.proveedor,
        "modelo_principal": evaluacion.modelo,
        "version_prompt": evaluacion.version_prompt,
        "nota_final": float(evaluacion.nota_final) if evaluacion.nota_final is not None else None,
        "resumen": ia.resumen if ia else "",
        "fortalezas": ia.fortalezas if ia else [],
        "debilidades": ia.debilidades if ia else [],
        "recomendaciones": ia.recomendaciones if ia else [],
        "aprendizajes": ia.aprendizajes if ia else [],
        "verificacion": evaluacion.verificacion,
        "creado_en": evaluacion.creado_en,
        "revisado_por": evaluacion.revisor,
        "aprobado_en": evaluacion.aprobado_en,
        "publicado_en": evaluacion.publicado_en,
    }


def vista_docente(evaluacion: Evaluacion) -> EvaluacionSalida:
    preliminar = evaluacion.nota_preliminar
    costo = evaluacion.costo_usd_estimado
    return EvaluacionSalida.model_validate(
        {
            **_base(evaluacion),
            "error": evaluacion.error,
            "nota_preliminar": float(preliminar) if preliminar is not None else None,
            "requiere_revision": bool(evaluacion.requiere_revision),
            "advertencias": evaluacion.advertencias or [],
            "criterios": _criterios(evaluacion, estudiante=False),
            "uso": evaluacion.uso or [],
            "costo_usd_estimado": float(costo) if costo is not None else None,
        },
        from_attributes=True,
    )


def vista_estudiante(evaluacion: Evaluacion) -> EvaluacionEstudiante:
    return EvaluacionEstudiante.model_validate(
        {**_base(evaluacion), "criterios": _criterios(evaluacion, estudiante=True)},
        from_attributes=True,
    )

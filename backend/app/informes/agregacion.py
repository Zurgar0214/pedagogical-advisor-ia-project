"""Agregación determinista del informe integral (RF-09). Función pura: sin BD, sin IA.

Reglas (ver `docs/API.md`, Iteración 4):
- Valor de un criterio = `valor` de su nivel final (IA + ajustes docentes).
- Promedio de competencia = promedio ponderado por `peso` de sus criterios (todas las evaluaciones).
- Nivel de dominio = `nivel_por_valor` del promedio ya redondeado a 2 decimales.
- Temas: unión de `laboratorio.temas` y `aprendizaje.tema` normalizados; el promedio sale de los
  criterios relacionados y, si no hay, de `VALOR_POR_NIVEL` de los aprendizajes.
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field

from app.evaluacion.contrato import Aprendizaje, ResultadoIA
from app.informes.contrato import (
    VALOR_POR_NIVEL,
    AgregadoInforme,
    AprendizajeLab,
    Brecha,
    CompetenciaAgregada,
    LaboratorioAgregado,
    TemaAgregado,
    nivel_por_valor,
)
from app.schemas.rubrica import Rubrica

UMBRAL_CRITERIO_BAJO = 3.0


class LaboratorioCatalogo(BaseModel):
    """Un laboratorio existente en la plataforma (con o sin evaluación publicada del estudiante)."""

    id: int
    codigo: str
    cohorte: int
    temas: list[str] = Field(default_factory=list)


class EvaluacionPublicada(BaseModel):
    """Evaluación publicada (la más reciente de su entrega) con todo lo necesario para agregar."""

    evaluacion_id: int
    laboratorio: LaboratorioCatalogo
    titulo: str
    nota_final: float
    publicado_en: datetime
    rubrica: Rubrica
    niveles_finales: dict[str, str]  # criterio_id -> nombre de nivel (ya con ajustes docentes)
    resultado: ResultadoIA


def normalizar_tema(tema: str) -> str:
    return " ".join(tema.lower().split())


def redondear(valor: float) -> float:
    return float(Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _promedio(valores: list[float]) -> float | None:
    return redondear(sum(valores) / len(valores)) if valores else None


def _sin_duplicados(items) -> list:
    return list(dict.fromkeys(items))


def _valores_criterios(ev: EvaluacionPublicada) -> dict[str, tuple[str, float, float]]:
    """criterio_id -> (nombre de competencia, valor final, peso). Omite los sin nivel válido."""
    competencias = {c.id: c.nombre for c in ev.rubrica.competencias}
    salida = {}
    for crit in ev.rubrica.criterios:
        nivel = ev.niveles_finales.get(crit.id)
        valor = next((n.valor for n in crit.niveles if n.nombre == nivel), None)
        if valor is None:
            continue
        salida[crit.id] = (
            competencias.get(crit.competencia_id, crit.competencia_id),
            valor,
            crit.peso,
        )
    return salida


def construir_agregado(
    estudiante: str,
    evaluaciones: list[EvaluacionPublicada],
    laboratorios: list[LaboratorioCatalogo],
) -> AgregadoInforme:
    evaluaciones = sorted(evaluaciones, key=lambda e: (e.laboratorio.cohorte, e.laboratorio.codigo))
    valores = {e.evaluacion_id: _valores_criterios(e) for e in evaluaciones}

    # ---- laboratorios y promedios de nota
    labs = [
        LaboratorioAgregado(
            laboratorio_id=e.laboratorio.id,
            codigo=e.laboratorio.codigo,
            titulo=e.titulo,
            cohorte=e.laboratorio.cohorte,
            evaluacion_id=e.evaluacion_id,
            nota_final=redondear(e.nota_final),
            publicado_en=e.publicado_en.isoformat(),
            fortalezas=list(e.resultado.fortalezas),
            debilidades=list(e.resultado.debilidades),
            recomendaciones=list(e.resultado.recomendaciones),
        )
        for e in evaluaciones
    ]
    notas = [e.nota_final for e in evaluaciones]
    promedio_general = redondear(sum(notas) / len(notas)) if notas else 0.0
    promedio_cohorte: dict[str, float] = {}
    for cohorte in sorted({e.laboratorio.cohorte for e in evaluaciones}):
        promedio_cohorte[str(cohorte)] = _promedio(
            [e.nota_final for e in evaluaciones if e.laboratorio.cohorte == cohorte]
        )
    tendencia = (
        redondear(promedio_cohorte["2"] - promedio_cohorte["1"])
        if "1" in promedio_cohorte and "2" in promedio_cohorte
        else None
    )

    # ---- competencias (ponderadas por peso)
    acum: dict[str, list[tuple[int, int, str, float, float]]] = {}
    for e in evaluaciones:
        for competencia, valor, peso in valores[e.evaluacion_id].values():
            acum.setdefault(competencia, []).append(
                (e.evaluacion_id, e.laboratorio.cohorte, e.laboratorio.codigo, valor, peso)
            )

    def ponderado(filas) -> float | None:
        total_peso = sum(f[4] for f in filas)
        if total_peso <= 0:
            return None
        return redondear(sum(f[3] * f[4] for f in filas) / total_peso)

    competencias = []
    for nombre in sorted(acum):
        filas = acum[nombre]
        promedio = ponderado(filas)
        if promedio is None:
            continue
        por_cohorte = {}
        for cohorte in sorted({f[1] for f in filas}):
            p = ponderado([f for f in filas if f[1] == cohorte])
            if p is not None:
                por_cohorte[str(cohorte)] = p
        competencias.append(
            CompetenciaAgregada(
                nombre=nombre,
                promedio=promedio,
                nivel_dominio=nivel_por_valor(promedio),
                laboratorios=_sin_duplicados(f[2] for f in filas),
                por_cohorte=por_cohorte,
            )
        )

    # ---- temas
    por_codigo = {e.laboratorio.codigo for e in evaluaciones}
    temas_lab: dict[str, set[str]] = {}  # tema -> códigos de laboratorio que lo declaran
    for lab in [*laboratorios, *(e.laboratorio for e in evaluaciones)]:
        for t in lab.temas:
            if normalizar_tema(t):
                temas_lab.setdefault(normalizar_tema(t), set()).add(lab.codigo)
    aprend: dict[str, list[tuple[EvaluacionPublicada, Aprendizaje]]] = {}
    for e in evaluaciones:
        for a in e.resultado.aprendizajes:
            if normalizar_tema(a.tema):
                aprend.setdefault(normalizar_tema(a.tema), []).append((e, a))

    temas = []
    for tema in sorted(set(temas_lab) | set(aprend)):
        declarados = temas_lab.get(tema, set())
        aplicados = {e.laboratorio.codigo for e, _ in aprend.get(tema, [])} | (
            declarados & por_codigo
        )
        vistos: set[tuple[int, str]] = set()
        valores_crit: list[float] = []
        valores_nivel: list[float] = []
        for e, a in aprend.get(tema, []):
            valores_nivel.append(VALOR_POR_NIVEL[a.nivel_dominio])
            for cid in a.criterios_relacionados:
                dato = valores[e.evaluacion_id].get(cid)
                if dato is not None and (e.evaluacion_id, cid) not in vistos:
                    vistos.add((e.evaluacion_id, cid))
                    valores_crit.append(dato[1])
        promedio = _promedio(valores_crit or valores_nivel)
        temas.append(
            TemaAgregado(
                tema=tema,
                nivel_dominio=nivel_por_valor(promedio) if promedio is not None else None,
                promedio=promedio,
                laboratorios=sorted(aplicados),
                laboratorios_sin_evidencia=sorted(declarados - por_codigo),
                aprendizajes=[
                    AprendizajeLab(
                        laboratorio=e.laboratorio.codigo,
                        que_aprendio=a.que_aprendio,
                        como_aplico=a.como_aplico,
                        nivel_dominio=a.nivel_dominio,
                    )
                    for e, a in aprend.get(tema, [])
                ],
                que_fortalecer=_sin_duplicados(
                    a.que_fortalecer.strip()
                    for _, a in aprend.get(tema, [])
                    if a.que_fortalecer.strip()
                ),
            )
        )

    # ---- brechas
    brechas = [
        Brecha(
            tipo="competencia",
            nombre=c.nombre,
            detalle=f"Promedio {c.promedio:.2f}: nivel de dominio {c.nivel_dominio}.",
        )
        for c in competencias
        if c.nivel_dominio in ("inicial", "basico")
    ]
    brechas += [
        Brecha(
            tipo="tema",
            nombre=t.tema,
            detalle=f"Promedio {t.promedio:.2f}: nivel de dominio {t.nivel_dominio}.",
        )
        for t in temas
        if t.nivel_dominio in ("inicial", "basico")
    ]
    for e in evaluaciones:
        for crit in e.rubrica.criterios:
            dato = valores[e.evaluacion_id].get(crit.id)
            if dato is not None and dato[1] < UMBRAL_CRITERIO_BAJO:
                brechas.append(
                    Brecha(
                        tipo="criterio",
                        nombre=crit.nombre,
                        detalle=(
                            f"Nivel «{e.niveles_finales[crit.id]}» (valor {dato[1]:.2f}) "
                            f"en {e.laboratorio.codigo}."
                        ),
                    )
                )
    brechas += [
        Brecha(
            tipo="sin_evidencia",
            nombre=t.tema,
            detalle=(
                "Sin evaluación publicada en: " + ", ".join(t.laboratorios_sin_evidencia) + "."
                if t.laboratorios_sin_evidencia
                else "El tema no tiene evidencia de dominio en las evaluaciones publicadas."
            ),
        )
        for t in temas
        if t.nivel_dominio is None
    ]

    return AgregadoInforme(
        estudiante=estudiante,
        laboratorios_totales=len(laboratorios),
        laboratorios=labs,
        promedio_general=promedio_general,
        promedio_cohorte=promedio_cohorte,
        nivel_general=nivel_por_valor(promedio_general),
        competencias=competencias,
        temas=temas,
        tendencia=tendencia,
        brechas=brechas,
    )

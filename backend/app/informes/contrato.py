"""Contrato interno del informe integral (RF-09) y el mapa mental (RF-10). Lo define el orquestador.

Flujo:
    backend agrega de forma DETERMINISTA las evaluaciones PUBLICADAS del estudiante
      -> `AgregadoInforme`
      -> `app.evaluacion.informe.sintetizar(agregado, settings)` (IA) -> `SintesisInforme`
      -> backend combina ambos, guarda el informe y construye el mapa a partir de él.

Reglas:
- Notas, promedios y niveles de dominio los calcula el backend (ver `nivel_por_valor`);
  la IA no los cambia.
- La IA solo redacta (resumen, narrativa de evolución), propone el plan de fortalecimiento,
  clasifica cada tema en una categoría de `CATEGORIAS_IA` y propone relaciones
  entre temas EXISTENTES.
- Todo lo que viene de evaluaciones del estudiante es dato, no instrucciones.
"""

from typing import Literal

from pydantic import BaseModel, Field

NivelDominio = Literal["inicial", "basico", "competente", "avanzado"]

CATEGORIAS_IA: tuple[str, ...] = (
    "Fundamentos de IA",
    "Búsqueda y optimización",
    "Aprendizaje supervisado",
    "Aprendizaje no supervisado",
    "Redes neuronales y aprendizaje profundo",
    "Procesamiento de lenguaje natural",
    "Visión por computador",
    "Aprendizaje por refuerzo",
    "IA generativa y modelos de lenguaje",
    "Datos y evaluación de modelos",
    "Ética y responsabilidad en IA",
    "Otros",
)

# Umbrales sobre un promedio 0,0-5,0 (los aplica el backend)
UMBRALES_DOMINIO: tuple[tuple[float, NivelDominio], ...] = (
    (2.5, "inicial"),
    (3.5, "basico"),
    (4.3, "competente"),
)
VALOR_POR_NIVEL: dict[str, float] = {
    "inicial": 1.5,
    "basico": 3.0,
    "competente": 4.0,
    "avanzado": 5.0,
}


def nivel_por_valor(valor: float) -> NivelDominio:
    for limite, nivel in UMBRALES_DOMINIO:
        if valor < limite:
            return nivel
    return "avanzado"


# ---------- Agregado determinista (entrada de la IA) ----------


class LaboratorioAgregado(BaseModel):
    laboratorio_id: int
    codigo: str
    titulo: str
    cohorte: int
    evaluacion_id: int
    nota_final: float
    publicado_en: str  # ISO 8601
    fortalezas: list[str] = Field(default_factory=list)
    debilidades: list[str] = Field(default_factory=list)
    recomendaciones: list[str] = Field(default_factory=list)


class CompetenciaAgregada(BaseModel):
    nombre: str
    promedio: float  # promedio ponderado por peso de los valores de nivel_final
    nivel_dominio: NivelDominio
    laboratorios: list[str]  # códigos
    por_cohorte: dict[str, float] = Field(default_factory=dict)  # "1"/"2" -> promedio


class AprendizajeLab(BaseModel):
    laboratorio: str  # código
    que_aprendio: str
    como_aplico: str
    nivel_dominio: NivelDominio


class TemaAgregado(BaseModel):
    tema: str  # normalizado: minúsculas, sin espacios extra
    nivel_dominio: NivelDominio | None  # None si no hay evidencia
    promedio: float | None
    laboratorios: list[str]  # códigos donde se aplicó (con evaluación publicada)
    # tema declarado por el laboratorio pero sin evaluación publicada
    laboratorios_sin_evidencia: list[str] = Field(default_factory=list)
    aprendizajes: list[AprendizajeLab] = Field(default_factory=list)
    que_fortalecer: list[str] = Field(default_factory=list)


class Brecha(BaseModel):
    tipo: Literal["competencia", "tema", "criterio", "sin_evidencia"]
    nombre: str
    detalle: str


class AgregadoInforme(BaseModel):
    estudiante: str  # nombre
    laboratorios_totales: int
    laboratorios: list[LaboratorioAgregado]
    promedio_general: float
    promedio_cohorte: dict[str, float]
    nivel_general: NivelDominio
    competencias: list[CompetenciaAgregada]
    temas: list[TemaAgregado]
    tendencia: float | None  # promedio cohorte 2 - promedio cohorte 1 (None si falta alguna)
    brechas: list[Brecha]


# ---------- Síntesis de la IA ----------


class AccionPlan(BaseModel):
    prioridad: int = Field(ge=1, le=5, description="1 = más urgente")
    tema: str
    objetivo: str
    actividades: list[str] = Field(min_length=1)
    recursos: list[str] = Field(default_factory=list)
    indicador_logro: str
    plazo_semanas: int = Field(ge=1, le=16)


class ClasificacionTema(BaseModel):
    tema: str
    categoria: str  # uno de CATEGORIAS_IA


class RelacionTemas(BaseModel):
    origen: str  # tema existente
    destino: str  # tema existente, distinto de origen
    tipo: Literal["prerrequisito", "complementa", "aplica"]
    explicacion: str


class SintesisInforme(BaseModel):
    resumen: str
    evolucion: str
    plan: list[AccionPlan] = Field(min_length=1, max_length=8)
    clasificacion: list[ClasificacionTema]  # uno por cada tema del agregado
    relaciones: list[RelacionTemas] = Field(default_factory=list, max_length=30)

"""Esquemas de la API de evaluaciones y revisión docente (RF-06/07/08)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.evaluacion.contrato import (
    Aprendizaje,
    EvidenciaCitada,
    UsoModelo,
    VerificacionTecnica,
)
from app.schemas.entrega import LaboratorioResumen, RubricaVersionRef
from app.schemas.laboratorio import UsuarioBasico


class NivelDisponible(BaseModel):
    nombre: str
    descriptor: str = ""
    valor: float


class AjusteDocente(BaseModel):
    nivel: str
    justificacion: str
    usuario: UsuarioBasico
    fecha: datetime
    nivel_anterior: str | None = None


class CriterioEvaluado(BaseModel):
    """Vista docente/admin de un criterio."""

    criterio_id: str
    criterio: str
    competencia: str
    peso: float
    niveles_disponibles: list[NivelDisponible]
    nivel_ia: str | None = None
    nivel_final: str | None = None
    valor_nivel_final: float | None = None
    confianza: float | None = None
    justificacion: str = ""
    evidencias: list[EvidenciaCitada] = Field(default_factory=list)
    fortalezas: list[str] = Field(default_factory=list)
    debilidades: list[str] = Field(default_factory=list)
    recomendaciones: list[str] = Field(default_factory=list)
    modelo: str = ""
    escalado: bool = False
    ajuste_docente: AjusteDocente | None = None
    historial_ajustes: list[AjusteDocente] = Field(default_factory=list)


class CriterioEstudiante(BaseModel):
    """Vista recortada: sin confianza, nivel_ia, modelo ni escalamiento."""

    criterio_id: str
    criterio: str
    competencia: str
    peso: float
    niveles_disponibles: list[NivelDisponible]
    nivel_final: str | None = None
    valor_nivel_final: float | None = None
    justificacion: str = ""
    evidencias: list[EvidenciaCitada] = Field(default_factory=list)
    fortalezas: list[str] = Field(default_factory=list)
    debilidades: list[str] = Field(default_factory=list)
    recomendaciones: list[str] = Field(default_factory=list)
    ajuste_docente: AjusteDocente | None = None


class _EvaluacionBase(BaseModel):
    id: int
    entrega_id: int
    estado: str
    estudiante: UsuarioBasico
    laboratorio: LaboratorioResumen
    rubrica_version: RubricaVersionRef
    proveedor: str | None = None
    modelo_principal: str | None = None
    version_prompt: str | None = None
    nota_final: float | None = None
    resumen: str = ""
    fortalezas: list[str] = Field(default_factory=list)
    debilidades: list[str] = Field(default_factory=list)
    recomendaciones: list[str] = Field(default_factory=list)
    aprendizajes: list[Aprendizaje] = Field(default_factory=list)
    verificacion: VerificacionTecnica | None = None
    creado_en: datetime
    revisado_por: UsuarioBasico | None = None
    aprobado_en: datetime | None = None
    publicado_en: datetime | None = None


class EvaluacionSalida(_EvaluacionBase):
    error: str | None = None
    nota_preliminar: float | None = None
    requiere_revision: bool = False
    advertencias: list[str] = Field(default_factory=list)
    criterios: list[CriterioEvaluado] = Field(default_factory=list)
    uso: list[UsoModelo] = Field(default_factory=list)
    costo_usd_estimado: float | None = None


class EvaluacionEstudiante(_EvaluacionBase):
    """Lo único que ve el estudiante, y solo cuando la evaluación está publicada."""

    criterios: list[CriterioEstudiante] = Field(default_factory=list)


class AjusteCriterioEntrada(BaseModel):
    nivel: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    justificacion: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10)]


class ConfiguracionIA(BaseModel):
    proveedor: str
    modelo_principal: str
    modelo_escalamiento: str
    umbral_confianza: float
    disponible: bool
    motivo: str

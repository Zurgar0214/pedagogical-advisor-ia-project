"""Esquemas de la API del informe integral (RF-09)."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.evaluacion.contrato import UsoModelo
from app.informes.contrato import AgregadoInforme, SintesisInforme
from app.schemas.laboratorio import EstudianteSalida, UsuarioBasico


class InformeEstudiante(BaseModel):
    """Vista del estudiante: sin `uso`, `costo_usd_estimado` ni `advertencias`."""

    id: int
    estado: str
    error: str | None = None
    estudiante: EstudianteSalida
    generado_en: datetime
    generado_por: UsuarioBasico
    evaluaciones_incluidas: list[int] = Field(default_factory=list)
    agregado: AgregadoInforme | None = None
    sintesis: SintesisInforme | None = None
    temas_categoria: dict[str, str] = Field(default_factory=dict)
    proveedor: str | None = None
    modelo: str | None = None
    version_prompt: str | None = None


class InformeSalida(InformeEstudiante):
    """Vista docente/admin."""

    advertencias: list[str] = Field(default_factory=list)
    uso: list[UsoModelo] = Field(default_factory=list)
    costo_usd_estimado: float | None = None


class InformeResumen(BaseModel):
    id: int
    estado: str
    generado_en: datetime
    evaluaciones_incluidas: list[int]
    promedio_general: float | None = None

"""Esquemas de entregas, evidencias y portafolio (RF-02)."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import TipoEvidencia
from app.schemas.laboratorio import EstudianteSalida, LaboratorioSalida, UsuarioBasico


class EntregaCrear(BaseModel):
    laboratorio_id: int
    estudiante_id: int | None = None


class EvidenciaSalida(BaseModel):
    id: int
    tipo: TipoEvidencia
    nombre_original: str | None = None
    url: str | None = None
    tamano_bytes: int | None = None
    sha256: str | None = None
    creado_en: datetime
    detalle: dict = Field(default_factory=dict)


class LaboratorioResumen(BaseModel):
    id: int
    codigo: str
    titulo: str
    cohorte: int


class RubricaVersionRef(BaseModel):
    id: int
    numero: int


class EntregaResumen(BaseModel):
    """Entrega sin evidencias (listados y portafolio)."""

    id: int
    estado: str
    creado_en: datetime
    estudiante: UsuarioBasico
    laboratorio: LaboratorioResumen
    rubrica_version: RubricaVersionRef
    faltantes: list[str]


class EntregaSalida(EntregaResumen):
    evidencias: list[EvidenciaSalida]


class PortafolioLaboratorio(BaseModel):
    laboratorio: LaboratorioSalida
    entrega: EntregaResumen | None = None


class PortafolioCohorte(BaseModel):
    cohorte: int
    laboratorios: list[PortafolioLaboratorio]


class PortafolioSalida(BaseModel):
    estudiante: EstudianteSalida
    cohortes: list[PortafolioCohorte]

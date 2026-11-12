"""Esquemas de laboratorios, rúbricas versionadas y portafolio (RF-01, RF-02, RF-03)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.rubrica import Rubrica


class LaboratorioCrear(BaseModel):
    cohorte: Literal[1, 2]
    codigo: str = Field(min_length=1, max_length=50)
    titulo: str = Field(min_length=1, max_length=200)
    descripcion: str = ""
    objetivos: str = ""
    temas: list[str] = Field(default_factory=list)


class LaboratorioActualizar(BaseModel):
    cohorte: Literal[1, 2] | None = None
    codigo: str | None = Field(default=None, min_length=1, max_length=50)
    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    descripcion: str | None = None
    objetivos: str | None = None
    temas: list[str] | None = None


class RubricaVigente(BaseModel):
    version_id: int
    numero: int
    valida: bool


class LaboratorioSalida(BaseModel):
    id: int
    cohorte: int
    codigo: str
    titulo: str
    descripcion: str
    objetivos: str
    temas: list[str]
    rubrica_vigente: RubricaVigente | None = None


class UsuarioBasico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str


class EstudianteSalida(UsuarioBasico):
    correo: str


class RubricaVersionSalida(BaseModel):
    id: int
    numero: int
    valida: bool
    inconsistencias: list[str]
    contenido: Rubrica
    creado_por: UsuarioBasico | None = None
    creado_en: datetime


class RubricaVersionResumen(BaseModel):
    """Versión sin contenido (listado de versiones)."""

    id: int
    numero: int
    valida: bool
    inconsistencias: list[str]
    creado_por: UsuarioBasico | None = None
    creado_en: datetime


class RubricaDeLaboratorio(BaseModel):
    vigente: RubricaVersionSalida | None = None
    versiones: list[RubricaVersionResumen] = Field(default_factory=list)


class ValidacionSalida(BaseModel):
    valida: bool
    inconsistencias: list[str]

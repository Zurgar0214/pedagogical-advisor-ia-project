"""Modelos Pydantic de la rúbrica (RF-04/RF-05).

Los rangos (peso, valor 0-5) NO se imponen aquí a propósito: se comprueban en
`services.validacion_rubrica` para poder reportar todas las inconsistencias en
español en lugar de fallar en la primera.
"""

from pydantic import BaseModel, Field


class NivelDesempeno(BaseModel):
    nombre: str
    descriptor: str = ""
    valor: float = Field(description="Valor del nivel en la escala 0,0-5,0")


class Competencia(BaseModel):
    id: str
    nombre: str
    descripcion: str = ""


class Criterio(BaseModel):
    id: str
    nombre: str
    descripcion: str = ""
    competencia_id: str
    peso: float = Field(description="Peso porcentual (0-100)")
    niveles: list[NivelDesempeno] = Field(default_factory=list)


class Rubrica(BaseModel):
    version: int = 1
    competencias: list[Competencia] = Field(default_factory=list)
    criterios: list[Criterio] = Field(default_factory=list)

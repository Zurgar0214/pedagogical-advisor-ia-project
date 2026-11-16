"""Esquema Pydantic de la rúbrica propuesta por la IA (RF-04).

Es la salida cruda del modelo: no impone rangos para poder reportar todo en una validación de negocio
en español (`rubrica_ia._validar`). Se convierte a `app.schemas.rubrica.Rubrica` con `a_rubrica`.
"""

from pydantic import BaseModel, Field

from app.schemas.rubrica import Competencia, Criterio, NivelDesempeno
from app.schemas.rubrica import Rubrica as RubricaContenido


class NivelPropuesto(BaseModel):
    nombre: str
    descriptor: str = ""
    valor: float = Field(description="Valor del nivel en la escala 0,0-5,0")


class CompetenciaPropuesta(BaseModel):
    id: str
    nombre: str
    descripcion: str = ""


class CriterioPropuesto(BaseModel):
    id: str
    nombre: str
    descripcion: str = ""
    competencia_id: str
    peso: float = Field(description="Peso porcentual tal como lo declara el documento (0-100)")
    niveles: list[NivelPropuesto] = Field(default_factory=list)


class RubricaPropuesta(BaseModel):
    competencias: list[CompetenciaPropuesta] = Field(default_factory=list)
    criterios: list[CriterioPropuesto] = Field(default_factory=list)
    observaciones: list[str] = Field(
        default_factory=list,
        description="Ambigüedades, pesos ausentes repartidos, escalas convertidas, etc.",
    )


def a_rubrica(propuesta: RubricaPropuesta) -> RubricaContenido:
    return RubricaContenido(
        version=1,
        competencias=[
            Competencia(id=c.id, nombre=c.nombre, descripcion=c.descripcion)
            for c in propuesta.competencias
        ],
        criterios=[
            Criterio(
                id=k.id,
                nombre=k.nombre,
                descripcion=k.descripcion,
                competencia_id=k.competencia_id,
                peso=k.peso,
                niveles=[
                    NivelDesempeno(nombre=n.nombre, descriptor=n.descriptor, valor=n.valor)
                    for n in k.niveles
                ],
            )
            for k in propuesta.criterios
        ],
    )

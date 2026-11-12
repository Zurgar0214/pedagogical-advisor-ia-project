"""RF-07: cálculo determinista de la nota 0,0-5,0. Nunca usa LLM."""

from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel

from app.schemas.rubrica import Rubrica
from app.services.validacion_rubrica import validar_rubrica


class ErrorCalculoNota(ValueError):
    """La nota no puede calcularse (rúbrica inválida, criterios faltantes o nivel desconocido)."""


class DesgloseCriterio(BaseModel):
    criterio_id: str
    criterio: str
    nivel: str
    peso: Decimal
    valor_nivel: Decimal
    aporte: Decimal  # peso/100 * valor, sin redondear


class ResultadoNota(BaseModel):
    nota: Decimal  # 0,0-5,0 con 1 decimal
    desglose: list[DesgloseCriterio]


def calcular_nota(rubrica: Rubrica, niveles_elegidos: dict[str, str]) -> ResultadoNota:
    """Calcula Σ(peso_i/100 × valor_nivel_i) redondeada a 1 decimal (ROUND_HALF_UP).

    `niveles_elegidos` mapea id de criterio -> nombre del nivel elegido.
    """
    errores = validar_rubrica(rubrica)
    if errores:
        raise ErrorCalculoNota("Rúbrica inválida: " + " ".join(errores))

    ids = {c.id for c in rubrica.criterios}
    faltantes = sorted(ids - niveles_elegidos.keys())
    if faltantes:
        raise ErrorCalculoNota("Faltan niveles para los criterios: " + ", ".join(faltantes) + ".")
    sobrantes = sorted(niveles_elegidos.keys() - ids)
    if sobrantes:
        raise ErrorCalculoNota(
            "Criterios inexistentes en la rúbrica: " + ", ".join(sobrantes) + "."
        )

    desglose: list[DesgloseCriterio] = []
    total = Decimal("0")
    for crit in rubrica.criterios:
        elegido = niveles_elegidos[crit.id]
        nivel = next((n for n in crit.niveles if n.nombre == elegido), None)
        if nivel is None:
            raise ErrorCalculoNota(
                f"El nivel '{elegido}' no existe en el criterio '{crit.nombre}'."
            )
        peso = Decimal(str(crit.peso))
        valor = Decimal(str(nivel.valor))
        aporte = peso / Decimal("100") * valor
        total += aporte
        desglose.append(
            DesgloseCriterio(
                criterio_id=crit.id,
                criterio=crit.nombre,
                nivel=nivel.nombre,
                peso=peso,
                valor_nivel=valor,
                aporte=aporte,
            )
        )

    nota = total.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return ResultadoNota(nota=nota, desglose=desglose)

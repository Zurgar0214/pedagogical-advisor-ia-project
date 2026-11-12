"""RF-05: validación de rúbricas. Devuelve inconsistencias legibles; lista vacía = válida."""

from collections import Counter
from decimal import Decimal

from app.schemas.rubrica import Rubrica

TOLERANCIA_PESOS = Decimal("0.01")
VALOR_MIN = Decimal("0")
VALOR_MAX = Decimal("5")


def _duplicados(valores: list[str]) -> list[str]:
    return [v for v, n in Counter(valores).items() if n > 1]


def validar_rubrica(rubrica: Rubrica) -> list[str]:
    errores: list[str] = []

    if not rubrica.criterios:
        errores.append("La rúbrica no tiene criterios.")

    for cid in _duplicados([c.id for c in rubrica.competencias]):
        errores.append(f"Id de competencia duplicado: '{cid}'.")
    for cid in _duplicados([c.id for c in rubrica.criterios]):
        errores.append(f"Id de criterio duplicado: '{cid}'.")

    competencias = {c.id for c in rubrica.competencias}

    for crit in rubrica.criterios:
        if crit.competencia_id not in competencias:
            errores.append(
                f"El criterio '{crit.nombre}' referencia la competencia inexistente "
                f"'{crit.competencia_id}'."
            )
        peso = Decimal(str(crit.peso))
        if peso < 0 or peso > 100:
            errores.append(
                f"El peso del criterio '{crit.nombre}' ({crit.peso} %) debe estar entre 0 y 100."
            )

        if not crit.niveles:
            errores.append(f"El criterio '{crit.nombre}' no tiene niveles de desempeño.")
            continue

        for nivel in crit.niveles:
            if not nivel.descriptor.strip():
                errores.append(
                    f"El nivel '{nivel.nombre}' del criterio '{crit.nombre}' no tiene descriptor."
                )
            valor = Decimal(str(nivel.valor))
            if valor < VALOR_MIN or valor > VALOR_MAX:
                errores.append(
                    f"El nivel '{nivel.nombre}' del criterio '{crit.nombre}' tiene valor "
                    f"{nivel.valor} fuera del rango 0,0-5,0."
                )
        for v in _duplicados([str(Decimal(str(n.valor))) for n in crit.niveles]):
            errores.append(f"El criterio '{crit.nombre}' tiene niveles con valor duplicado ({v}).")
        for nombre in _duplicados([n.nombre for n in crit.niveles]):
            errores.append(
                f"El criterio '{crit.nombre}' tiene niveles con nombre duplicado ('{nombre}')."
            )

    if rubrica.criterios:
        total = sum((Decimal(str(c.peso)) for c in rubrica.criterios), Decimal("0"))
        if abs(total - Decimal("100")) > TOLERANCIA_PESOS:
            errores.append(f"Los pesos suman {total} % y deben sumar 100 %.")

    return errores

"""Validación de reglas de negocio de la salida del modelo (más allá del esquema Pydantic)."""

import re
from collections import Counter

from app.evaluacion.contexto import ContextoPreparado, FuenteTexto
from app.evaluacion.esquemas import CriterioSalida
from app.schemas.rubrica import Rubrica

_PREFIJO_LINEA = re.compile(r"^\s*\d+\| ?", re.MULTILINE)
MAX_FRAGMENTO = 300


def _norm(texto: str) -> str:
    return " ".join(_PREFIJO_LINEA.sub("", texto).lower().split())


def validar_criterios(
    criterios: list[CriterioSalida],
    rubrica: Rubrica,
    ids_esperados: list[str],
    preparado: ContextoPreparado,
) -> tuple[list[str], list[str]]:
    """Devuelve (errores, avisos). Con errores la salida se rechaza; los avisos solo se registran."""
    errores: list[str] = []
    avisos: list[str] = []
    niveles = {c.id: [n.nombre for n in c.niveles] for c in rubrica.criterios}
    conteo = Counter(c.criterio_id for c in criterios)
    for cid, n in conteo.items():
        if n > 1:
            errores.append(f"El criterio '{cid}' aparece {n} veces; debe aparecer una sola vez.")
        if cid not in ids_esperados:
            errores.append(f"El criterio '{cid}' no es uno de los pedidos: {', '.join(ids_esperados)}.")
    faltantes = [i for i in ids_esperados if i not in conteo]
    if faltantes:
        errores.append("Faltan los criterios: " + ", ".join(faltantes) + ".")

    textos = {f.fuente: f for f in preparado.fuentes}
    validas = preparado.nombres_fuentes()
    sin_coincidencia: list[str] = []
    for c in criterios:
        if c.criterio_id in niveles and c.nivel not in niveles[c.criterio_id]:
            errores.append(
                f"El nivel '{c.nivel}' no existe en el criterio '{c.criterio_id}'. "
                "Niveles válidos: " + ", ".join(f"'{n}'" for n in niveles[c.criterio_id]) + "."
            )
        for ev in c.evidencias:
            if ev.fuente not in validas:
                errores.append(
                    f"En el criterio '{c.criterio_id}' la fuente '{ev.fuente}' no existe. "
                    "Fuentes válidas: " + ", ".join(sorted(validas)[:20]) + "."
                )
                continue
            fuente = textos.get(ev.fuente)
            if isinstance(fuente, FuenteTexto) and ev.fragmento.strip():
                if _norm(ev.fragmento) not in _norm(fuente.texto_original):
                    sin_coincidencia.append(c.criterio_id)
    if sin_coincidencia:
        ids = ", ".join(sorted(set(sin_coincidencia)))
        avisos.append(
            f"{len(sin_coincidencia)} fragmentos citados no coinciden literalmente con la fuente "
            f"(criterios: {ids}); revisar las citas."
        )
    return errores, avisos

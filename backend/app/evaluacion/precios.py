"""Tabla ÚNICA de precios para el costo estimado (USD por millón de tokens).

Escalones por tamaño del prompt (entrada + lectura + escritura de caché). Supuestos:
- Haiku 5.5: lectura de caché = 0,1 x entrada (no publicada en el encargo); por encima de 100K tokens
  de prompt todo se cobra a 0,50 / 2,50.
- Escritura de caché (TTL 5 min) = 1,25 x entrada.
- Modelos locales o desconocidos: costo 0.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Tarifa:
    entrada: float
    salida: float
    lectura_cache: float
    escritura_cache: float


def _tarifa(entrada: float, salida: float, lectura: float) -> Tarifa:
    return Tarifa(entrada, salida, lectura, round(entrada * 1.25, 6))


# prefijo de modelo -> [(tope_tokens_prompt | None, tarifa)] en orden ascendente
PRECIOS: dict[str, list[tuple[int | None, Tarifa]]] = {
    "claude-haiku-5-5": [
        (100_000, _tarifa(0.10, 0.50, 0.01)),
        (None, _tarifa(0.50, 2.50, 0.05)),
    ],
    "claude-sonnet-5-5": [(None, _tarifa(2.0, 10.0, 0.10))],
}


def tarifa_para(modelo: str, tokens_prompt: int) -> Tarifa | None:
    for prefijo, escalones in PRECIOS.items():
        if modelo.startswith(prefijo):
            for tope, tarifa in escalones:
                if tope is None or tokens_prompt <= tope:
                    return tarifa
    return None


def costo_estimado(
    modelo: str,
    tokens_entrada: int,
    tokens_salida: int,
    tokens_cache_lectura: int = 0,
    tokens_cache_escritura: int = 0,
) -> float:
    """Costo en USD. `tokens_entrada` son los tokens NO cacheados."""
    prompt = tokens_entrada + tokens_cache_lectura + tokens_cache_escritura
    t = tarifa_para(modelo, prompt)
    if t is None:
        return 0.0
    total = (
        tokens_entrada * t.entrada
        + tokens_salida * t.salida
        + tokens_cache_lectura * t.lectura_cache
        + tokens_cache_escritura * t.escritura_cache
    )
    return round(total / 1_000_000, 8)

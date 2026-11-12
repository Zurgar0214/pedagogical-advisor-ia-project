"""Mapa mental de competencias (RF-10). Función pura: se construye desde el informe guardado.

Jerarquía: raíz -> categoría -> tema -> laboratorio (`aplicado_en`), más aristas `relacion`.
Las categorías sin temas no aparecen; los laboratorios sin tema asociado tampoco (serían huérfanos).
"""

import re
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.informes.agregacion import normalizar_tema, redondear
from app.informes.contrato import CATEGORIAS_IA, AgregadoInforme, SintesisInforme, nivel_por_valor

ETIQUETA_RAIZ = "Inteligencia Artificial"
CATEGORIA_POR_DEFECTO = "Otros"


class NodoMapa(BaseModel):
    id: str
    tipo: Literal["raiz", "categoria", "tema", "laboratorio"]
    etiqueta: str
    nivel_dominio: str | None = None
    datos: dict[str, Any] = Field(default_factory=dict)


class AristaMapa(BaseModel):
    id: str
    origen: str
    destino: str
    tipo: Literal["jerarquia", "aplicado_en", "relacion"]
    etiqueta: str = ""


class MapaSalida(BaseModel):
    informe_id: int
    estudiante: dict[str, Any]
    nodos: list[NodoMapa]
    aristas: list[AristaMapa]


def slug(texto: str) -> str:
    """Minúsculas, sin tildes, solo [a-z0-9] separados por guion."""
    base = unicodedata.normalize("NFKD", texto)
    base = "".join(c for c in base if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-") or "x"


def categoria_de(tema: str, temas_categoria: dict[str, str]) -> str:
    categoria = temas_categoria.get(tema, CATEGORIA_POR_DEFECTO)
    return categoria if categoria in CATEGORIAS_IA else CATEGORIA_POR_DEFECTO


def _promedio(valores: list[float]) -> float | None:
    return redondear(sum(valores) / len(valores)) if valores else None


def construir_mapa(
    informe_id: int,
    estudiante: dict[str, Any],
    agregado: AgregadoInforme,
    sintesis: SintesisInforme,
    temas_categoria: dict[str, str],
) -> MapaSalida:
    por_codigo = {lab.codigo: lab for lab in agregado.laboratorios}
    categorias = {normalizar_tema(k): v for k, v in temas_categoria.items()}

    # Ids de tema estables y únicos (dos temas con el mismo slug reciben sufijo).
    ids_tema: dict[str, str] = {}
    usados: set[str] = set()
    for t in agregado.temas:
        base = f"tema:{slug(t.tema)}"
        nuevo, n = base, 2
        while nuevo in usados:
            nuevo, n = f"{base}-{n}", n + 1
        usados.add(nuevo)
        ids_tema[t.tema] = nuevo

    por_categoria: dict[str, list] = {}
    for t in agregado.temas:
        por_categoria.setdefault(categoria_de(t.tema, categorias), []).append(t)

    nodos: list[NodoMapa] = []
    aristas: list[AristaMapa] = []

    def arista(origen: str, destino: str, tipo: str, etiqueta: str = "") -> None:
        aristas.append(
            AristaMapa(
                id=f"e{len(aristas) + 1}",
                origen=origen,
                destino=destino,
                tipo=tipo,
                etiqueta=etiqueta,
            )
        )

    promedio_raiz = _promedio([t.promedio for t in agregado.temas if t.promedio is not None])
    nodos.append(
        NodoMapa(
            id="raiz",
            tipo="raiz",
            etiqueta=ETIQUETA_RAIZ,
            nivel_dominio=nivel_por_valor(promedio_raiz) if promedio_raiz is not None else None,
            datos={"promedio": promedio_raiz},
        )
    )

    labs_vistos: set[str] = set()
    for categoria in CATEGORIAS_IA:  # orden estable
        temas = por_categoria.get(categoria)
        if not temas:
            continue
        promedio_cat = _promedio([t.promedio for t in temas if t.promedio is not None])
        id_cat = f"cat:{slug(categoria)}"
        nodos.append(
            NodoMapa(
                id=id_cat,
                tipo="categoria",
                etiqueta=categoria,
                nivel_dominio=nivel_por_valor(promedio_cat) if promedio_cat is not None else None,
                datos={"promedio": promedio_cat, "temas": len(temas)},
            )
        )
        arista("raiz", id_cat, "jerarquia")
        for t in temas:
            id_tema = ids_tema[t.tema]
            cohortes = sorted({por_codigo[c].cohorte for c in t.laboratorios if c in por_codigo})
            nodos.append(
                NodoMapa(
                    id=id_tema,
                    tipo="tema",
                    etiqueta=t.tema,
                    nivel_dominio=t.nivel_dominio,
                    datos={
                        "promedio": t.promedio,
                        "cohortes": cohortes,
                        "laboratorios": list(t.laboratorios),
                        "aprendizajes": [a.model_dump() for a in t.aprendizajes],
                        "que_fortalecer": list(t.que_fortalecer),
                        "sin_evidencia": t.nivel_dominio is None,
                    },
                )
            )
            arista(id_cat, id_tema, "jerarquia")
            for codigo in t.laboratorios:
                lab = por_codigo.get(codigo)
                if lab is None:
                    continue
                id_lab = f"lab:{codigo}"
                if codigo not in labs_vistos:
                    labs_vistos.add(codigo)
                    nodos.append(
                        NodoMapa(
                            id=id_lab,
                            tipo="laboratorio",
                            etiqueta=f"{codigo} · {lab.titulo}",
                            nivel_dominio=None,
                            datos={
                                "cohorte": lab.cohorte,
                                "nota_final": lab.nota_final,
                                "evaluacion_id": lab.evaluacion_id,
                                "titulo": lab.titulo,
                            },
                        )
                    )
                arista(id_tema, id_lab, "aplicado_en")

    # Relaciones propuestas por la IA: solo entre temas existentes y sin duplicados.
    existentes = {normalizar_tema(t.tema): ids_tema[t.tema] for t in agregado.temas}
    vistas: set[tuple[str, str, str]] = set()
    for rel in sintesis.relaciones:
        origen = existentes.get(normalizar_tema(rel.origen))
        destino = existentes.get(normalizar_tema(rel.destino))
        if origen is None or destino is None or origen == destino:
            continue
        if (origen, destino, rel.tipo) in vistas:
            continue
        vistas.add((origen, destino, rel.tipo))
        arista(origen, destino, "relacion", f"{rel.tipo}: {rel.explicacion}")

    return MapaSalida(informe_id=informe_id, estudiante=estudiante, nodos=nodos, aristas=aristas)

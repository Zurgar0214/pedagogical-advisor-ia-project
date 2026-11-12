"""Ayudas para las pruebas del pipeline de evaluación (sin red ni clave)."""

import io
import json
import zipfile
from pathlib import Path

from app.core.config import Settings
from app.evaluacion.contrato import (
    ContextoEvaluacion,
    EvidenciaCitada,
    EvidenciaContexto,
    LaboratorioContexto,
    UsoModelo,
)
from app.evaluacion.esquemas import CriterioSalida, SalidaCriterios, SalidaEvaluacion
from app.evaluacion.proveedores.base import ProveedorIA
from tests.conftest import hacer_rubrica

INFORME = "El estudiante implementa un modelo de regresión lineal con numpy.\nConcluye que funciona."
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def settings(**kw) -> Settings:
    base = {"ai_provider": "falso", "anthropic_api_key": None, "ia_umbral_confianza": 0.6}
    return Settings(_env_file=None, **{**base, **kw})


def crear_zip(destino: Path, archivos: dict[str, bytes | str]) -> Path:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for nombre, datos in archivos.items():
            zf.writestr(nombre, datos)
    destino.write_bytes(buf.getvalue())
    return destino


def notebook(celdas: list[tuple[str, str]]) -> str:
    return json.dumps(
        {
            "cells": [
                {"cell_type": tipo, "source": src.splitlines(keepends=True), "metadata": {}}
                for tipo, src in celdas
            ],
            "nbformat": 4,
            "nbformat_minor": 5,
        }
    )


def contexto(
    tmp_path: Path | None = None,
    codigo: dict[str, bytes | str] | None = None,
    informe: str | None = INFORME,
    pesos: list[float] | None = None,
    extra: list[EvidenciaContexto] | None = None,
) -> ContextoEvaluacion:
    evs: list[EvidenciaContexto] = []
    if informe is not None:
        evs.append(
            EvidenciaContexto(
                id=1, tipo="informe_pdf", nombre_original="informe.pdf", texto_extraido=informe
            )
        )
    if codigo is not None:
        assert tmp_path is not None
        z = crear_zip(tmp_path / "codigo.zip", codigo)
        evs.append(
            EvidenciaContexto(
                id=2, tipo="codigo_zip", nombre_original="codigo.zip", ruta_archivo=str(z)
            )
        )
    evs.extend(extra or [])
    return ContextoEvaluacion(
        laboratorio=LaboratorioContexto(
            codigo="LAB1", titulo="Regresión", temas=["Regresión", "Evaluación de modelos"]
        ),
        rubrica=hacer_rubrica(pesos or [40, 60]),
        evidencias=evs,
    )


def crit(cid: str, nivel: str = "N2.5", conf: float = 0.9, con_evidencia: bool = True):
    evid = (
        [EvidenciaCitada(fuente="informe_pdf", ubicacion="inicio", fragmento="regresión lineal")]
        if con_evidencia
        else []
    )
    return CriterioSalida(
        criterio_id=cid,
        nivel=nivel,
        confianza=conf,
        justificacion=f"Justificación de {cid}",
        evidencias=evid,
        fortalezas=["f"],
        debilidades=["d"],
        recomendaciones=["r"],
    )


def salida(criterios: list[CriterioSalida], **kw) -> SalidaEvaluacion:
    return SalidaEvaluacion(criterios=criterios, resumen="Resumen", **kw)


def salida_esc(criterios: list[CriterioSalida]) -> SalidaCriterios:
    return SalidaCriterios(criterios=criterios)


class ProveedorSimulado(ProveedorIA):
    """Devuelve respuestas controladas, en orden. Un elemento puede ser una Exception."""

    nombre = "simulado"
    acepta_imagenes = True
    modelo_principal = "modelo-barato"
    modelo_escalamiento = "modelo-potente"

    def __init__(self, respuestas: list):
        self.respuestas = list(respuestas)
        self.llamadas: list[dict] = []

    def generar_estructurado(
        self, sistema, bloques_estables, bloques_variables, esquema, modelo, proposito
    ):
        self.llamadas.append(
            {
                "sistema": sistema,
                "estables": bloques_estables,
                "variables": bloques_variables,
                "esquema": esquema,
                "modelo": modelo,
                "proposito": proposito,
            }
        )
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        uso = UsoModelo(
            proveedor=self.nombre,
            modelo=modelo,
            proposito=proposito,
            tokens_entrada=100,
            tokens_salida=50,
        )
        return r, uso

    def texto_variables(self, i: int) -> str:
        return "\n".join(getattr(b, "texto", "") for b in self.llamadas[i]["variables"])

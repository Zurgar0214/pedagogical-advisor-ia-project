"""Verificación técnica del código del estudiante SIN ejecutarlo (RF-06).

- Sintaxis de Python con `ast.parse` (incluidas las celdas de código de los notebooks).
- Análisis estático con `ruff check` en un subproceso con timeout, sobre un directorio temporal
  que se elimina siempre. Ruff analiza el código, no lo ejecuta.
- Pruebas unitarias del estudiante: se ejecutan SOLO en la sandbox (contenedor aislado, sin red,
  con límites), a través de `app.evaluacion.sandbox`; este módulo nunca ejecuta código del estudiante.
"""

import ast
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from app.core.config import Settings
from app.evaluacion.contexto import ContextoPreparado
from app.evaluacion.contrato import HallazgoCodigo, VerificacionTecnica
from app.evaluacion.sandbox import ejecutar_pruebas

TIMEOUT_RUFF_S = 30
MAX_HALLAZGOS = 200


def _sintaxis(preparado: ContextoPreparado) -> list[HallazgoCodigo]:
    errores: list[HallazgoCodigo] = []
    for a in preparado.archivos:
        if a.lenguaje == "python" and not a.truncado:
            try:
                ast.parse(a.texto)
            except SyntaxError as e:
                errores.append(
                    HallazgoCodigo(
                        archivo=a.ruta, linea=e.lineno, regla="sintaxis", mensaje=e.msg or "Error"
                    )
                )
            except ValueError as e:  # p. ej. bytes nulos
                errores.append(HallazgoCodigo(archivo=a.ruta, regla="sintaxis", mensaje=str(e)))
        elif a.lenguaje == "notebook":
            for n, codigo in a.celdas_python:
                try:
                    ast.parse(codigo)
                except SyntaxError as e:
                    errores.append(
                        HallazgoCodigo(
                            archivo=f"{a.ruta} (celda {n})",
                            linea=e.lineno,
                            regla="sintaxis",
                            mensaje=e.msg or "Error",
                        )
                    )
                except ValueError as e:
                    errores.append(
                        HallazgoCodigo(archivo=f"{a.ruta} (celda {n})", regla="sintaxis", mensaje=str(e))
                    )
    return errores


def _comando_ruff() -> list[str] | None:
    exe = shutil.which("ruff")
    if exe:
        return [exe]
    # En el venv del proyecto, `ruff` vive junto al intérprete aunque no esté en el PATH.
    candidato = Path(sys.executable).parent / ("ruff.exe" if sys.platform == "win32" else "ruff")
    if candidato.is_file():
        return [str(candidato)]
    return None


def _ruff(preparado: ContextoPreparado, notas: list[str]) -> list[HallazgoCodigo]:
    py = [a for a in preparado.archivos if a.lenguaje == "python"]
    if not py:
        return []
    cmd = _comando_ruff()
    if cmd is None:
        notas.append("Ruff no está disponible en el servidor: se omitió el análisis estático.")
        return []
    tmp = Path(tempfile.mkdtemp(prefix="eval_ruff_"))
    try:
        for i, a in enumerate(py):
            destino = tmp / f"{i:04d}" / a.ruta
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(a.texto, encoding="utf-8")
        try:
            proc = subprocess.run(  # noqa: S603 - solo analiza, no ejecuta el código del estudiante
                [*cmd, "check", "--output-format", "json", "--no-cache", "--isolated", str(tmp)],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_RUFF_S,
                cwd=tmp,
                check=False,
            )
        except subprocess.TimeoutExpired:
            notas.append(f"Ruff superó el tiempo límite ({TIMEOUT_RUFF_S} s); se omitió.")
            return []
        except OSError as e:
            notas.append(f"No se pudo ejecutar ruff: {e}")
            return []
        if proc.returncode not in (0, 1):
            notas.append("Ruff terminó con error; se omitió el análisis estático.")
            return []
        try:
            datos = json.loads(proc.stdout or "[]")
        except ValueError:
            notas.append("La salida de ruff no es JSON válido; se omitió.")
            return []
        hallazgos: list[HallazgoCodigo] = []
        for d in datos:
            if not d.get("code"):  # errores de sintaxis: ya se reportan aparte
                continue
            nombre = Path(d["filename"])
            try:
                rel = nombre.resolve().relative_to(tmp.resolve())
                archivo = "/".join(rel.parts[1:])
            except ValueError:
                archivo = nombre.name
            hallazgos.append(
                HallazgoCodigo(
                    archivo=archivo,
                    linea=(d.get("location") or {}).get("row"),
                    regla=d["code"],
                    mensaje=d.get("message", ""),
                )
            )
        if len(hallazgos) > MAX_HALLAZGOS:
            notas.append(
                f"Ruff reportó {len(hallazgos)} hallazgos; se conservan los primeros {MAX_HALLAZGOS}."
            )
            hallazgos = hallazgos[:MAX_HALLAZGOS]
        return hallazgos
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def verificar(preparado: ContextoPreparado, settings: Settings) -> VerificacionTecnica:
    notas: list[str] = []
    por_lenguaje = Counter(a.lenguaje for a in preparado.archivos)
    return VerificacionTecnica(
        archivos_analizados=len(preparado.archivos),
        archivos_por_lenguaje=dict(por_lenguaje),
        errores_sintaxis=_sintaxis(preparado),
        hallazgos_estaticos=_ruff(preparado, notas),
        pruebas=ejecutar_pruebas(preparado.archivos, settings),
        repositorios_no_analizados=list(preparado.repositorios_no_analizados),
        notas=notas,
    )

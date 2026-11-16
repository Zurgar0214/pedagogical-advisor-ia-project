"""Cliente de la sandbox de ejecución de pruebas (RNF-04, RNF-03).

Este módulo NO ejecuta código del estudiante: envía los archivos de Python al servicio interno
`sandbox` (HTTP + token), que los corre en un contenedor desechable sin red y con límites.
Nunca lanza excepciones: cualquier fallo se devuelve como `ResultadoPruebas(ejecutadas=False, motivo=...)`.
"""

import posixpath

import httpx

from app.core.config import Settings
from app.evaluacion.contexto import ArchivoCodigo
from app.evaluacion.contrato import ResultadoPruebas

MOTIVO_SIN_PRUEBAS = "La entrega no incluye pruebas unitarias (archivos test_*.py o *_test.py)"
MOTIVO_DESHABILITADA = "La sandbox de ejecución no está configurada en este servidor"
MARGEN_HTTP_S = 30


def es_archivo_de_prueba(ruta: str) -> bool:
    nombre = posixpath.basename(ruta)
    return nombre.endswith(".py") and (nombre.startswith("test_") or nombre.endswith("_test.py"))


def _no_ejecutadas(motivo: str) -> ResultadoPruebas:
    return ResultadoPruebas(ejecutadas=False, motivo=motivo)


def ejecutar_pruebas(
    archivos: list[ArchivoCodigo],
    settings: Settings,
    cliente: httpx.Client | None = None,
) -> ResultadoPruebas:
    """Ejecuta las pruebas unitarias del estudiante en la sandbox y devuelve sus resultados."""
    # Solo Python completo (sin truncar); los notebooks y otros lenguajes no se envían.
    py = [a for a in archivos if a.lenguaje == "python" and not a.truncado]
    if not any(es_archivo_de_prueba(a.ruta) for a in py):
        return _no_ejecutadas(MOTIVO_SIN_PRUEBAS)
    if not settings.sandbox_url:
        return _no_ejecutadas(MOTIVO_DESHABILITADA)

    url = settings.sandbox_url.rstrip("/") + "/ejecutar"
    cuerpo = {"archivos": {a.ruta: a.texto for a in py}, "timeout_s": settings.sandbox_timeout_s}
    cabeceras = {"Authorization": f"Bearer {settings.sandbox_token}"}
    propio = cliente is None
    http = cliente or httpx.Client(timeout=settings.sandbox_timeout_s + MARGEN_HTTP_S)
    try:
        resp = http.post(url, json=cuerpo, headers=cabeceras)
    except httpx.HTTPError as e:
        return _no_ejecutadas(f"No se pudo contactar la sandbox: {type(e).__name__}")
    finally:
        if propio:
            http.close()

    if resp.status_code != 200:
        return _no_ejecutadas(f"La sandbox respondió con error HTTP {resp.status_code}")
    try:
        d = resp.json()
        if not isinstance(d, dict):
            raise ValueError
    except ValueError:
        return _no_ejecutadas("La sandbox devolvió una respuesta que no es JSON válido")

    if not d.get("ok"):
        motivo = str(d.get("motivo") or "La ejecución no produjo un resultado válido")
        return ResultadoPruebas(ejecutadas=False, motivo=motivo, salida=str(d.get("salida", ""))[:8000])
    try:
        return ResultadoPruebas(
            ejecutadas=True,
            motivo=str(d.get("motivo", "")),
            total=int(d.get("total", 0)),
            exitosas=int(d.get("exitosas", 0)),
            fallidas=int(d.get("fallidas", 0)),
            errores=int(d.get("errores", 0)),
            omitidas=int(d.get("omitidas", 0)),
            salida=str(d.get("salida", ""))[:8000],
            tiempo_agotado=bool(d.get("tiempo_agotado", False)),
        )
    except (TypeError, ValueError):
        return _no_ejecutadas("La sandbox devolvió contadores inválidos")

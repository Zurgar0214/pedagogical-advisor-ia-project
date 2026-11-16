"""Pruebas unitarias del cliente de la sandbox (sin Docker: httpx con MockTransport)."""

import httpx

from app.evaluacion import sandbox
from app.evaluacion.contexto import ArchivoCodigo
from tests.evaluacion.utiles_eval import settings


def arch(ruta, texto="x = 1\n", lenguaje="python", truncado=False):
    return ArchivoCodigo(ruta, lenguaje, texto, None, truncado)


def cliente(manejador):
    return httpx.Client(transport=httpx.MockTransport(manejador))


def cfg(**kw):
    return settings(sandbox_url="http://sandbox:8100", sandbox_token="tok", **kw)


def test_deteccion_de_archivos_de_prueba():
    assert sandbox.es_archivo_de_prueba("tests/test_modelo.py")
    assert sandbox.es_archivo_de_prueba("modelo_test.py")
    assert not sandbox.es_archivo_de_prueba("modelo.py")
    assert not sandbox.es_archivo_de_prueba("test_datos.csv")
    assert not sandbox.es_archivo_de_prueba("contest.py")


def test_sin_pruebas_no_llama_a_la_red():
    def no_debe_llamarse(req):
        raise AssertionError("no debía llamar a la sandbox")

    r = sandbox.ejecutar_pruebas([arch("modelo.py")], cfg(), cliente(no_debe_llamarse))
    assert r.ejecutadas is False and r.motivo == sandbox.MOTIVO_SIN_PRUEBAS
    assert "test_*.py" in r.motivo


def test_sandbox_deshabilitada():
    r = sandbox.ejecutar_pruebas([arch("test_a.py")], settings(sandbox_url=""))
    assert r.ejecutadas is False
    assert r.motivo == "La sandbox de ejecución no está configurada en este servidor"


def test_mapeo_de_respuesta_y_solo_se_envia_python_completo():
    vistos = {}

    def manejador(req):
        vistos["auth"] = req.headers["authorization"]
        vistos["url"] = str(req.url)
        vistos["cuerpo"] = __import__("json").loads(req.content)
        return httpx.Response(
            200,
            json={
                "ok": True, "total": 5, "exitosas": 2, "fallidas": 1, "errores": 1,
                "omitidas": 1, "salida": "salida", "tiempo_agotado": False, "motivo": "",
            },
        )  # fmt: skip

    archivos = [
        arch("src/a.py"),
        arch("tests/test_a.py"),
        arch("grande.py", truncado=True),
        arch("n.ipynb", lenguaje="notebook"),
        arch("app.js", lenguaje="javascript"),
        arch("README.md", lenguaje="markdown"),
    ]
    r = sandbox.ejecutar_pruebas(archivos, cfg(sandbox_timeout_s=30), cliente(manejador))
    assert vistos["auth"] == "Bearer tok"
    assert vistos["url"] == "http://sandbox:8100/ejecutar"
    assert set(vistos["cuerpo"]["archivos"]) == {"src/a.py", "tests/test_a.py"}
    assert vistos["cuerpo"]["timeout_s"] == 30
    assert r.ejecutadas is True
    assert (r.total, r.exitosas, r.fallidas, r.errores, r.omitidas) == (5, 2, 1, 1, 1)
    assert r.tiempo_agotado is False and r.salida == "salida"


def test_tiempo_agotado_se_refleja():
    def manejador(req):
        return httpx.Response(
            200, json={"ok": True, "tiempo_agotado": True, "motivo": "Superó el tiempo"}
        )

    r = sandbox.ejecutar_pruebas([arch("test_a.py")], cfg(), cliente(manejador))
    assert r.ejecutadas is True and r.tiempo_agotado is True and r.total == 0


def test_resultado_no_valido_de_la_sandbox():
    def manejador(req):
        return httpx.Response(
            200, json={"ok": False, "motivo": "La ejecución no produjo un resultado válido"}
        )

    r = sandbox.ejecutar_pruebas([arch("test_a.py")], cfg(), cliente(manejador))
    assert r.ejecutadas is False and "no produjo un resultado válido" in r.motivo


def test_error_de_red_no_lanza():
    def manejador(req):
        raise httpx.ConnectError("sin ruta")

    r = sandbox.ejecutar_pruebas([arch("test_a.py")], cfg(), cliente(manejador))
    assert r.ejecutadas is False and "No se pudo contactar la sandbox" in r.motivo


def test_error_http_y_respuesta_no_json():
    r = sandbox.ejecutar_pruebas(
        [arch("test_a.py")], cfg(), cliente(lambda req: httpx.Response(401, json={}))
    )
    assert r.ejecutadas is False and "HTTP 401" in r.motivo
    r = sandbox.ejecutar_pruebas(
        [arch("test_a.py")], cfg(), cliente(lambda req: httpx.Response(200, text="<html>"))
    )
    assert r.ejecutadas is False and "JSON" in r.motivo

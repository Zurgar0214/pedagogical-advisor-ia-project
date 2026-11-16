"""Pruebas del servicio orquestador (sin Docker): validación, tar, token y límites."""

import http.client
import io
import json
import tarfile
import threading

import pytest
import servidor


def test_ruta_segura():
    assert servidor.ruta_segura("a/b.py") == "a/b.py"
    assert servidor.ruta_segura("./a//b.py") == "a/b.py"
    assert servidor.ruta_segura("a\\b.py") == "a/b.py"
    for mala in ["/etc/passwd", "../x.py", "a/../../x", "C:/x.py", "", "a\x00b", "."]:
        assert servidor.ruta_segura(mala) is None


def test_validar_cuerpo():
    archivos, t = servidor.validar_cuerpo({"archivos": {"./a.py": "x"}, "timeout_s": 10})
    assert archivos == {"a.py": "x"} and t == 10
    malos = [
        None,
        {},
        {"archivos": {}},
        {"archivos": {"../a.py": "x"}},
        {"archivos": {"a.py": 5}},
        {"archivos": {"a.py": "x"}, "timeout_s": 1},
        {"archivos": {"a.py": "x"}, "timeout_s": 500},
        {"archivos": {"a.py": "x"}, "timeout_s": "10"},
        {"archivos": {f"f{i}.py": "x" for i in range(501)}},
    ]
    for m in malos:
        with pytest.raises(servidor.ErrorPeticion):
            servidor.validar_cuerpo(m)


def test_construir_tar():
    datos = servidor.construir_tar({"a/b.py": "héllo"})
    with tarfile.open(fileobj=io.BytesIO(datos)) as t:
        [m] = t.getmembers()
        assert m.name == "a/b.py" and m.isfile()
        assert t.extractfile(m).read().decode() == "héllo"


def test_flags_de_aislamiento():
    cmd = servidor.argumentos_docker("sbx-x", 45, "img:1")
    s = " ".join(cmd)
    for flag in [
        "--network none",
        "--read-only",
        "--cap-drop ALL",
        "--pids-limit 128",
        "--user 65534:65534",
        "no-new-privileges",
        "--memory 512m",
        "--cpus 1",
    ]:
        assert flag in s
    assert cmd[-2:] == ["img:1", "45"]


def test_buscar_resultado_usa_el_nonce():
    n = "ab" * 16
    falso = json.dumps({"total": 99, "exitosas": 99})
    stdout = f"{falso}\nsalida\n{n} {json.dumps({'total': 2})}\n"
    assert servidor.buscar_resultado(stdout, n) == {"total": 2}
    assert servidor.buscar_resultado(falso, n) is None
    assert servidor.buscar_resultado(f"{n} no-json", n) is None


def test_ejecutar_sin_resultado_valido_y_137(monkeypatch):
    class P:
        stdout = b"basura"
        stderr = b"boom"
        returncode = 137

    monkeypatch.setattr(servidor.subprocess, "run", lambda *a, **k: P())
    r = servidor.ejecutar({"a.py": "x"}, 10)
    assert r["ok"] is False and r["total"] == 0
    assert "no produjo un resultado válido" in r["motivo"] and "memoria" in r["motivo"]


def test_ejecutar_tiempo_externo(monkeypatch):
    llamadas = []

    def falso(cmd, **k):
        llamadas.append(cmd)
        if cmd[1] == "run":
            raise servidor.subprocess.TimeoutExpired(cmd, 1)

    monkeypatch.setattr(servidor.subprocess, "run", falso)
    r = servidor.ejecutar({"a.py": "x"}, 10)
    assert r["tiempo_agotado"] is True and r["ok"] is True
    assert llamadas[-1][1:3] == ["rm", "-f"]


@pytest.fixture
def http_local():
    srv = servidor.crear_servidor("127.0.0.1", 0)
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def llamar(puerto, metodo, ruta, cuerpo=None, token=None):
    c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=10)
    h = {}
    if token is not None:
        h["Authorization"] = f"Bearer {token}"
    datos = json.dumps(cuerpo) if cuerpo is not None else None
    c.request(metodo, ruta, body=datos, headers=h)
    r = c.getresponse()
    return r.status, json.loads(r.read() or b"{}")


def test_salud_sin_token(http_local):
    assert llamar(http_local, "GET", "/salud") == (200, {"estado": "ok"})


def test_sin_token_configurado_503(http_local, monkeypatch):
    monkeypatch.delenv("SANDBOX_TOKEN", raising=False)
    assert llamar(http_local, "POST", "/ejecutar", {}, token="x")[0] == 503


def test_token_incorrecto_401_y_validacion_400(http_local, monkeypatch):
    monkeypatch.setenv("SANDBOX_TOKEN", "secreto")
    assert llamar(http_local, "POST", "/ejecutar", {"archivos": {"a.py": "x"}})[0] == 401
    assert llamar(http_local, "POST", "/ejecutar", {"archivos": {"a.py": "x"}}, token="otro")[0] == 401
    cuerpo = {"archivos": {"../a.py": "x"}}
    assert llamar(http_local, "POST", "/ejecutar", cuerpo, token="secreto")[0] == 400


def test_cuerpo_demasiado_grande_413(http_local, monkeypatch):
    monkeypatch.setenv("SANDBOX_TOKEN", "secreto")
    c = http.client.HTTPConnection("127.0.0.1", http_local, timeout=10)
    c.putrequest("POST", "/ejecutar")
    c.putheader("Authorization", "Bearer secreto")
    c.putheader("Content-Length", str(servidor.MAX_CUERPO + 1))
    c.endheaders()
    assert c.getresponse().status == 413


def test_peticion_valida_llega_a_ejecutar(http_local, monkeypatch):
    monkeypatch.setenv("SANDBOX_TOKEN", "secreto")
    monkeypatch.setattr(
        servidor, "ejecutar", lambda a, t: {"ok": True, "total": 1, "archivos": sorted(a), "t": t}
    )
    cuerpo = {"archivos": {"./a.py": "x"}, "timeout_s": 20}
    s, r = llamar(http_local, "POST", "/ejecutar", cuerpo, token="secreto")
    assert s == 200 and r["archivos"] == ["a.py"] and r["t"] == 20

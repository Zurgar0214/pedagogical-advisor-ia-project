"""Pruebas de contención REALES: requieren Docker y la imagen asesor-sandbox-python:1.

Usan `servidor.ejecutar`, que lanza `docker run` con los mismos flags de producción.
Se saltan si Docker no está disponible o la imagen no existe.
"""

import shutil
import subprocess
import time

import pytest
import servidor


def _docker_listo() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        r = subprocess.run(
            ["docker", "image", "inspect", servidor.imagen()],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(not _docker_listo(), reason="Docker o la imagen de la sandbox no disponible"),
]


def correr(codigo: str, timeout_s: int = 20, extra: dict | None = None) -> dict:
    return servidor.ejecutar({"test_x.py": codigo, **(extra or {})}, timeout_s)


def contenedores_sbx() -> list[str]:
    r = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "name=sbx-"], capture_output=True, text=True, check=False
    )
    return r.stdout.split()


def test_a_conteos_correctos():
    r = correr(
        "import pytest\n"
        "def test_ok1(): assert 1 + 1 == 2\n"
        "def test_ok2(): assert True\n"
        "def test_falla(): assert 1 == 2\n"
        "def test_error(nada): pass\n"
        "@pytest.mark.skip\n"
        "def test_omitida(): pass\n"
    )
    assert r["ok"] is True, r
    assert (r["total"], r["exitosas"], r["fallidas"], r["errores"], r["omitidas"]) == (5, 2, 1, 1, 1)
    assert r["tiempo_agotado"] is False and "test_falla" in r["salida"]


def test_sin_pruebas_recolectadas_total_cero():
    r = servidor.ejecutar({"modelo.py": "x = 1\n"}, 20)
    assert r["ok"] is True and r["total"] == 0 and r["codigo_salida"] == 5


def test_b_sin_red():
    r = correr(
        "import socket, pytest\n"
        "def test_red():\n"
        "    with pytest.raises(OSError):\n"
        "        socket.create_connection(('1.1.1.1', 53), timeout=3)\n"
    )
    assert (r["total"], r["exitosas"]) == (1, 1), r


def test_c_bucle_infinito_tiempo_agotado():
    inicio = time.time()
    r = correr("def test_bucle():\n    while True:\n        pass\n", timeout_s=6)
    assert r["tiempo_agotado"] is True
    assert time.time() - inicio < 6 + servidor.MARGEN_EXTERNO_S + 10


def test_d_fork_bomb_contenida():
    r = correr(
        "import os, time\n"
        "def test_fork():\n"
        "    hijos = []\n"
        "    try:\n"
        "        for _ in range(2000):\n"
        "            pid = os.fork()\n"
        "            if pid == 0:\n"
        "                time.sleep(3)\n"
        "                os._exit(0)\n"
        "            hijos.append(pid)\n"
        "    except OSError:\n"
        "        pass\n"
        "    n = len(hijos)\n"
        "    for p in hijos:\n"
        "        try:\n"
        "            os.kill(p, 9)\n"
        "        except OSError:\n"
        "            pass\n"
        "    assert n < 200, n\n"
        "    assert n > 0\n",
        timeout_s=30,
    )
    assert r["ok"] is True, r
    assert (r["total"], r["exitosas"]) == (1, 1), r
    # El host sigue bien y no quedan contenedores huérfanos.
    time.sleep(1)
    assert contenedores_sbx() == []
    assert subprocess.run(["docker", "ps", "-q"], capture_output=True, check=False).returncode == 0


def test_e_escribir_200mb_en_tmp_falla():
    r = correr(
        "import pytest\n"
        "def test_llenar():\n"
        "    bloque = b'x' * (8 * 1024 * 1024)\n"
        "    with pytest.raises(OSError):\n"
        "        for i in range(25):\n"
        "            with open(f'/tmp/relleno_{i}.bin', 'wb') as f:\n"
        "                f.write(bloque)\n"
        "    import glob, os\n"
        "    for f in glob.glob('/tmp/relleno_*.bin'):\n"
        "        os.remove(f)\n",
        timeout_s=30,
    )
    assert (r["total"], r["exitosas"]) == (1, 1), r


def test_f_escribir_fuera_de_tmp_falla():
    r = correr(
        "import pytest\n"
        "@pytest.mark.parametrize('ruta', ['/escrito.txt', '/opt/escrito.txt', '/usr/escrito.txt'])\n"
        "def test_solo_lectura(ruta):\n"
        "    with pytest.raises(OSError):\n"
        "        open(ruta, 'w').write('x')\n"
    )
    assert (r["total"], r["exitosas"]) == (3, 3), r


def test_g_json_falso_sin_nonce_no_altera():
    r = correr(
        "def test_impostor():\n"
        "    print('{\"total\": 99, \"exitosas\": 99, \"fallidas\": 0, \"errores\": 0,"
        " \"omitidas\": 0, \"salida\": \"\", \"codigo_salida\": 0, \"tiempo_agotado\": false}')\n"
        "    assert False\n"
    )
    assert (r["total"], r["exitosas"], r["fallidas"]) == (1, 0, 1), r


def test_usuario_sin_privilegios():
    r = correr("import os\ndef test_uid():\n    assert os.getuid() == 65534\n")
    assert (r["total"], r["exitosas"]) == (1, 1), r

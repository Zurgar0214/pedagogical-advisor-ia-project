"""Servicio orquestador de la sandbox (RNF-04): lanza un contenedor desechable por ejecución.

La API NO toca Docker: le habla a este servicio por HTTP en la red interna de compose.
Solo biblioteca estándar.

Seguridad: este servicio tiene montado el socket de Docker, lo que equivale a poder sobre el host.
Por eso: no publica puertos, exige un token (`SANDBOX_TOKEN`) y solo sabe ejecutar UN comando fijo
(`docker run` con los flags de `argumentos_docker`); el cliente solo aporta archivos de texto.
"""

import hmac
import io
import json
import os
import posixpath
import re
import secrets
import subprocess
import tarfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PUERTO = 8100
MAX_ARCHIVOS = 500
MAX_CUERPO = 5 * 1024 * 1024
TIMEOUT_MIN = 5
TIMEOUT_MAX = 120
MARGEN_EXTERNO_S = 15
MAX_CONCURRENTES = 2

_semaforo = threading.BoundedSemaphore(MAX_CONCURRENTES)


def imagen() -> str:
    return os.environ.get("SANDBOX_IMAGEN", "asesor-sandbox-python:1")


def comando_docker() -> str:
    return os.environ.get("SANDBOX_DOCKER", "docker")


def argumentos_docker(nombre: str, timeout_interno: int, img: str | None = None) -> list[str]:
    """Comando `docker run` con TODOS los flags de aislamiento. Fuente única (también la usan las pruebas)."""
    return [
        comando_docker(),
        "run",
        "-i",
        "--rm",
        "--name",
        nombre,
        "--network",
        "none",
        "--memory",
        "512m",
        "--memory-swap",
        "512m",
        "--cpus",
        "1",
        "--pids-limit",
        "128",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,noexec,size=128m,mode=1777",
        "--user",
        "65534:65534",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--ulimit",
        "nofile=256:256",
        "--ulimit",
        "fsize=67108864",
        img or imagen(),
        str(timeout_interno),
    ]


def ruta_segura(nombre: str) -> str | None:
    """Misma política que `app.evaluacion.contexto.ruta_segura`: sin absolutas, `..` ni unidad."""
    n = nombre.replace("\\", "/")
    if not n or n.startswith("/") or re.match(r"^[A-Za-z]:", n) or "\x00" in n:
        return None
    partes = [p for p in n.split("/") if p not in ("", ".")]
    if not partes or any(p == ".." for p in partes):
        return None
    return posixpath.join(*partes)


class ErrorPeticion(Exception):
    def __init__(self, codigo: int, mensaje: str):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


def validar_cuerpo(datos: object) -> tuple[dict[str, str], int]:
    """Valida el JSON de entrada. Devuelve (archivos normalizados, timeout_s)."""
    if not isinstance(datos, dict):
        raise ErrorPeticion(400, "El cuerpo debe ser un objeto JSON")
    archivos = datos.get("archivos")
    if not isinstance(archivos, dict) or not archivos:
        raise ErrorPeticion(400, "Falta 'archivos' (objeto ruta -> texto)")
    if len(archivos) > MAX_ARCHIVOS:
        raise ErrorPeticion(400, f"Máximo {MAX_ARCHIVOS} archivos")
    timeout_s = datos.get("timeout_s", 60)
    if isinstance(timeout_s, bool) or not isinstance(timeout_s, int):
        raise ErrorPeticion(400, "'timeout_s' debe ser entero")
    if not TIMEOUT_MIN <= timeout_s <= TIMEOUT_MAX:
        raise ErrorPeticion(400, f"'timeout_s' debe estar entre {TIMEOUT_MIN} y {TIMEOUT_MAX}")
    normalizados: dict[str, str] = {}
    for ruta, texto in archivos.items():
        limpia = ruta_segura(ruta) if isinstance(ruta, str) else None
        if limpia is None:
            raise ErrorPeticion(400, f"Ruta no permitida: {ruta!r}")
        if not isinstance(texto, str):
            raise ErrorPeticion(400, f"El contenido de {ruta!r} debe ser texto")
        normalizados[limpia] = texto
    return normalizados, timeout_s


def construir_tar(archivos: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:") as tar:
        for ruta, texto in archivos.items():
            datos = texto.encode("utf-8")
            info = tarfile.TarInfo(ruta)
            info.size = len(datos)
            info.mode = 0o644
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(datos))
    return buf.getvalue()


def _vacio(**extra) -> dict:
    base = {
        "ok": False,
        "total": 0,
        "exitosas": 0,
        "fallidas": 0,
        "errores": 0,
        "omitidas": 0,
        "salida": "",
        "codigo_salida": None,
        "tiempo_agotado": False,
        "motivo": "",
    }
    base.update(extra)
    return base


def buscar_resultado(stdout: str, nonce: str) -> dict | None:
    """Última línea que empieza con `<nonce> ` y cuyo resto es un JSON objeto; None si no hay."""
    prefijo = nonce + " "
    for linea in reversed(stdout.splitlines()):
        if linea.startswith(prefijo):
            try:
                d = json.loads(linea[len(prefijo) :])
            except ValueError:
                continue
            if isinstance(d, dict):
                return d
    return None


def ejecutar(archivos: dict[str, str], timeout_s: int) -> dict:
    """Corre las pruebas en un contenedor desechable (máx. MAX_CONCURRENTES a la vez)."""
    with _semaforo:
        nonce = secrets.token_hex(16)
        nombre = f"sbx-{uuid.uuid4().hex[:12]}"
        entrada = nonce.encode() + b"\n" + construir_tar(archivos)
        cmd = argumentos_docker(nombre, timeout_s)
        try:
            proc = subprocess.run(  # noqa: S603 - comando fijo, el cliente solo aporta archivos
                cmd,
                input=entrada,
                capture_output=True,
                timeout=timeout_s + MARGEN_EXTERNO_S,
                check=False,
            )
        except subprocess.TimeoutExpired:
            subprocess.run(  # noqa: S603
                [comando_docker(), "rm", "-f", nombre], capture_output=True, check=False, timeout=30
            )
            return _vacio(
                ok=True,
                tiempo_agotado=True,
                motivo=f"La ejecución superó el tiempo límite ({timeout_s} s) y se detuvo",
            )
        except OSError as e:
            return _vacio(motivo=f"No se pudo invocar Docker: {e}")

        stdout = proc.stdout.decode("utf-8", errors="replace")
        d = buscar_resultado(stdout, nonce)
        if d is None:
            motivo = "La ejecución no produjo un resultado válido"
            if proc.returncode == 137:
                motivo += " (código 137: probable límite de memoria de 512 MB)"
            detalle = proc.stderr.decode("utf-8", errors="replace").strip()[-500:]
            return _vacio(motivo=motivo, salida=detalle, codigo_salida=proc.returncode)
        resultado = _vacio(ok=True)
        for clave in ("total", "exitosas", "fallidas", "errores", "omitidas"):
            v = d.get(clave, 0)
            resultado[clave] = v if isinstance(v, int) and not isinstance(v, bool) else 0
        resultado["salida"] = str(d.get("salida", ""))[:8000]
        resultado["codigo_salida"] = d.get("codigo_salida")
        resultado["tiempo_agotado"] = bool(d.get("tiempo_agotado", False))
        if resultado["tiempo_agotado"]:
            resultado["motivo"] = f"Las pruebas superaron el tiempo límite ({timeout_s} s)"
        return resultado


class Manejador(BaseHTTPRequestHandler):
    server_version = "SandboxAsesor/1"

    def log_message(self, formato, *args):  # registro mínimo, sin contenido del estudiante
        print(f"{self.address_string()} {formato % args}", flush=True)

    def _responder(self, codigo: int, cuerpo: dict) -> None:
        datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _autorizado(self) -> bool:
        token = os.environ.get("SANDBOX_TOKEN", "")
        recibido = self.headers.get("Authorization", "")
        esperado = f"Bearer {token}"
        return hmac.compare_digest(recibido.encode(), esperado.encode())

    def do_GET(self):  # noqa: N802
        if self.path == "/salud":
            self._responder(200, {"estado": "ok"})
        else:
            self._responder(404, {"detalle": "No encontrado"})

    def do_POST(self):  # noqa: N802
        if self.path != "/ejecutar":
            self._responder(404, {"detalle": "No encontrado"})
            return
        try:
            largo = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            largo = -1
        if largo < 0:
            self._responder(400, {"detalle": "Content-Length inválido"})
            return
        if largo > MAX_CUERPO:
            self._responder(413, {"detalle": f"El cuerpo supera {MAX_CUERPO // (1024 * 1024)} MB"})
            return
        # Se lee el cuerpo (acotado) antes de responder para no cerrar con datos sin leer.
        crudo = self.rfile.read(largo)
        if not os.environ.get("SANDBOX_TOKEN"):
            self._responder(503, {"detalle": "SANDBOX_TOKEN no está configurado; servicio deshabilitado"})
            return
        if not self._autorizado():
            self._responder(401, {"detalle": "No autorizado"})
            return
        try:
            datos = json.loads(crudo or b"null")
            archivos, timeout_s = validar_cuerpo(datos)
        except ValueError:
            self._responder(400, {"detalle": "JSON inválido"})
            return
        except ErrorPeticion as e:
            self._responder(e.codigo, {"detalle": e.mensaje})
            return
        self._responder(200, ejecutar(archivos, timeout_s))


def crear_servidor(host: str = "0.0.0.0", puerto: int = PUERTO) -> ThreadingHTTPServer:  # noqa: S104
    return ThreadingHTTPServer((host, puerto), Manejador)


if __name__ == "__main__":
    print(f"Sandbox escuchando en :{PUERTO} (imagen {imagen()})", flush=True)
    crear_servidor().serve_forever()

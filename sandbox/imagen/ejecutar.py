"""Ejecuta las pruebas del estudiante DENTRO del contenedor desechable (solo biblioteca estándar).

Protocolo:
  - stdin: primera línea = nonce (hex); el resto = un tar sin comprimir con el código y las pruebas.
  - argumento 1 (opcional): timeout interno de pytest en segundos (por defecto 45).
  - stdout: una única línea final `<nonce> <JSON>` con el resultado.

Sobre el nonce: lo recibe este proceso por stdin y NO se pasa por entorno ni por argumentos al
subproceso del estudiante, así que su código no lo ve en condiciones normales. Es una MITIGACIÓN para
que un `print` falso no pueda imitar el resultado, no una garantía (un código malicioso y decidido
podría intentar leer la memoria de este proceso). El docente revisa todas las evaluaciones de
todos modos, y el aislamiento del contenedor (sin red, solo lectura, usuario sin privilegios)
es la barrera real.
"""

import io
import json
import os
import posixpath
import re
import signal
import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

DIR_TRABAJO = Path("/tmp/trabajo")
RUTA_JUNIT = Path("/tmp/resultado.xml")
RUTA_SALIDA = Path("/tmp/salida_pytest.txt")
MAX_BYTES_DESCOMPRIMIDO = 20 * 1024 * 1024
MAX_ENTRADAS = 2000
MAX_SALIDA = 8000
TIMEOUT_POR_DEFECTO = 45


class TarInseguro(Exception):
    """El tar recibido contiene algo que no se debe extraer."""


def ruta_segura(nombre: str) -> str | None:
    """Normaliza la ruta de una entrada; None si es peligrosa (absoluta, `..`, unidad, nula)."""
    n = nombre.replace("\\", "/")
    if not n or n.startswith("/") or re.match(r"^[A-Za-z]:", n) or "\x00" in n:
        return None
    partes = [p for p in n.split("/") if p not in ("", ".")]
    if not partes or any(p == ".." for p in partes):
        return None
    return posixpath.join(*partes)


def extraer_seguro(datos: bytes, destino: Path) -> int:
    """Extrae solo archivos regulares y directorios. Devuelve el número de archivos escritos.

    Rechaza (TarInseguro) rutas absolutas o con `..`, enlaces, dispositivos y fifos, y aplica
    topes de entradas y de bytes descomprimidos.
    """
    destino.mkdir(parents=True, exist_ok=True)
    total = 0
    escritos = 0
    try:
        tar = tarfile.open(fileobj=io.BytesIO(datos), mode="r:")
    except tarfile.TarError as e:
        raise TarInseguro(f"El tar es inválido: {e}") from e
    with tar:
        miembros = tar.getmembers()
        if len(miembros) > MAX_ENTRADAS:
            raise TarInseguro(f"El tar tiene más de {MAX_ENTRADAS} entradas")
        for m in miembros:
            ruta = ruta_segura(m.name)
            if ruta is None:
                raise TarInseguro(f"Ruta no permitida: {m.name!r}")
            if m.issym() or m.islnk():
                raise TarInseguro(f"Enlace no permitido: {m.name!r}")
            if not (m.isfile() or m.isdir()):
                raise TarInseguro(f"Tipo de entrada no permitido: {m.name!r}")
            objetivo = destino / ruta
            if m.isdir():
                objetivo.mkdir(parents=True, exist_ok=True)
                continue
            total += m.size
            if total > MAX_BYTES_DESCOMPRIMIDO:
                raise TarInseguro("El contenido supera el tope de 20 MB descomprimido")
            objetivo.parent.mkdir(parents=True, exist_ok=True)
            f = tar.extractfile(m)
            if f is None:
                raise TarInseguro(f"No se pudo leer: {m.name!r}")
            with f, open(objetivo, "wb") as out:
                out.write(f.read())
            escritos += 1
    return escritos


def parsear_junit(ruta: Path) -> dict[str, int]:
    """Lee el XML de pytest. exitosas = total - fallidas - errores - omitidas."""
    vacio = {"total": 0, "exitosas": 0, "fallidas": 0, "errores": 0, "omitidas": 0}
    try:
        raiz = ET.parse(ruta).getroot()
    except (OSError, ET.ParseError):
        return vacio
    suites = [raiz] if raiz.tag == "testsuite" else list(raiz.iter("testsuite"))
    total = fallidas = errores = omitidas = 0
    for s in suites:
        total += int(s.get("tests", 0))
        fallidas += int(s.get("failures", 0))
        errores += int(s.get("errors", 0))
        omitidas += int(s.get("skipped", 0))
    return {
        "total": total,
        "exitosas": max(total - fallidas - errores - omitidas, 0),
        "fallidas": fallidas,
        "errores": errores,
        "omitidas": omitidas,
    }


def recortar(texto: str, maximo: int = MAX_SALIDA) -> str:
    if len(texto) <= maximo:
        return texto
    cabeza = maximo // 4
    cola = maximo - cabeza
    return texto[:cabeza] + "\n[... salida recortada ...]\n" + texto[-cola:]


def _leer_salida() -> str:
    try:
        with open(RUTA_SALIDA, "rb") as f:
            f.seek(0, os.SEEK_END)
            tam = f.tell()
            # Evita cargar salidas enormes: lee como mucho los últimos 1 MB.
            f.seek(max(tam - 1_000_000, 0))
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def correr_pytest(timeout_s: int) -> tuple[int, bool]:
    """Devuelve (código_salida, tiempo_agotado). La salida queda en un archivo, no en memoria."""
    entorno = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": "/tmp",
        "MPLBACKEND": "Agg",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        f"--junitxml={RUTA_JUNIT}",
    ]
    with open(RUTA_SALIDA, "wb") as salida:
        proc = subprocess.Popen(  # noqa: S603 - comando fijo; el código del estudiante corre en el contenedor aislado
            cmd,
            cwd=DIR_TRABAJO,
            env=entorno,
            stdin=subprocess.DEVNULL,
            stdout=salida,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            return proc.wait(timeout=timeout_s), False
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
            proc.wait()
            return -9, True


def principal(argv: list[str]) -> int:
    try:
        timeout_s = int(argv[1]) if len(argv) > 1 else TIMEOUT_POR_DEFECTO
    except ValueError:
        timeout_s = TIMEOUT_POR_DEFECTO
    entrada = sys.stdin.buffer.read()
    nonce_bytes, _, datos = entrada.partition(b"\n")
    nonce = nonce_bytes.decode("ascii", errors="ignore").strip()
    if not re.fullmatch(r"[0-9a-f]{16,}", nonce):
        print("Nonce inválido", file=sys.stderr)
        return 2

    resultado = {
        "total": 0,
        "exitosas": 0,
        "fallidas": 0,
        "errores": 0,
        "omitidas": 0,
        "salida": "",
        "codigo_salida": None,
        "tiempo_agotado": False,
    }
    try:
        extraer_seguro(datos, DIR_TRABAJO)
    except TarInseguro as e:
        resultado["salida"] = f"Entrega rechazada por la sandbox: {e}"
        resultado["codigo_salida"] = 2
        print(f"\n{nonce} {json.dumps(resultado, ensure_ascii=False)}", flush=True)
        return 0

    codigo, agotado = correr_pytest(timeout_s)
    resultado["codigo_salida"] = codigo
    resultado["tiempo_agotado"] = agotado
    resultado["salida"] = recortar(_leer_salida())
    if codigo != 5 and not agotado:  # 5 = pytest no recolectó pruebas -> total 0
        resultado.update(parsear_junit(RUTA_JUNIT))
    print(f"\n{nonce} {json.dumps(resultado, ensure_ascii=False)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv))

"""Preparación del contexto: texto del informe, código del ZIP (sin ejecutarlo) e imágenes.

El ZIP se lee en memoria con `zipfile`: nunca se extrae a disco con rutas del estudiante ni se
ejecuta nada. Solo se conservan archivos de texto de código, con límites por archivo y totales.
"""

import base64
import json
import posixpath
import re
import stat
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import Settings
from app.evaluacion.contrato import ContextoEvaluacion, EvidenciaContexto
from app.evaluacion.seguridad import neutralizar

# Límites (constantes de módulo para poder ajustarlas en pruebas)
MAX_ENTRADAS_ZIP = 2000
MAX_ARCHIVOS_CODIGO = 300
MAX_BYTES_ARCHIVO = 200_000
MAX_BYTES_TOTAL = 5 * 1024 * 1024
MAX_IMAGENES = 5
MAX_BYTES_IMAGEN = 5 * 1024 * 1024
MIN_CARACTERES_UTILES = 2000  # menos que esto no vale la pena truncar otro archivo

DIRECTORIOS_EXCLUIDOS = {
    "node_modules", ".venv", "venv", "env", "__pycache__", ".git", ".idea", ".vscode",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "site-packages", "dist", "build",
    ".ipynb_checkpoints", "__macosx",
}  # fmt: skip
ARCHIVOS_EXCLUIDOS = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", ".ds_store"}

LENGUAJES = {
    ".py": "python", ".ipynb": "notebook", ".js": "javascript", ".jsx": "javascript",
    ".mjs": "javascript", ".ts": "typescript", ".tsx": "typescript", ".java": "java",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp", ".r": "r",
    ".sql": "sql", ".md": "markdown", ".txt": "texto", ".json": "json", ".yaml": "yaml",
    ".yml": "yaml", ".toml": "toml", ".html": "html", ".css": "css", ".sh": "shell",
    ".cs": "csharp", ".go": "go", ".rs": "rust", ".kt": "kotlin", ".php": "php", ".rb": "ruby",
    ".ini": "config", ".cfg": "config", ".csv": "datos",
}  # fmt: skip
NOMBRES_SIN_EXTENSION = {"readme": "markdown", "dockerfile": "docker", "makefile": "make"}
_PRINCIPALES = {"main", "app", "index", "__main__", "readme", "run", "server"}
_LENGUAJES_FUENTE = {
    "python", "notebook", "java", "javascript", "typescript", "r", "cpp", "c", "sql",
    "csharp", "go", "rust", "kotlin", "php", "ruby",
}  # fmt: skip


@dataclass
class FuenteTexto:
    fuente: str  # 'informe_pdf' | 'codigo:ruta' | 'presentacion:nombre'
    evidencia_id: int | None
    texto_prompt: str  # lo que ve el modelo (con líneas numeradas si es código)
    texto_original: str  # para verificar citas literales
    truncado: bool = False


@dataclass
class ArchivoCodigo:
    ruta: str
    lenguaje: str
    texto: str
    evidencia_id: int | None
    truncado: bool = False
    celdas_python: list[tuple[int, str]] = field(default_factory=list)  # (n.º de celda, código)


@dataclass
class ImagenAdjunta:
    fuente: str
    evidencia_id: int | None
    media_type: str
    datos_b64: str


@dataclass
class ContextoPreparado:
    fuentes: list[FuenteTexto] = field(default_factory=list)  # lo que se envía al modelo
    archivos: list[ArchivoCodigo] = field(default_factory=list)  # TODO el código extraído
    imagenes: list[ImagenAdjunta] = field(default_factory=list)
    repositorios_no_analizados: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    def nombres_fuentes(self) -> set[str]:
        return {f.fuente for f in self.fuentes} | {i.fuente for i in self.imagenes}

    @property
    def hay_evidencias(self) -> bool:
        return bool(self.fuentes or self.imagenes or self.archivos)


# ---------- ZIP ----------


def ruta_segura(nombre: str) -> str | None:
    """Normaliza la ruta de una entrada del ZIP; None si es peligrosa (absoluta, `..`, unidad)."""
    n = nombre.replace("\\", "/")
    if not n or n.startswith("/") or re.match(r"^[A-Za-z]:", n) or "\x00" in n:
        return None
    partes = [p for p in n.split("/") if p not in ("", ".")]
    if not partes or any(p == ".." for p in partes):
        return None
    return posixpath.join(*partes)


def _lenguaje(ruta: str) -> str | None:
    nombre = posixpath.basename(ruta).lower()
    if nombre.endswith(".min.js"):
        return None
    ext = posixpath.splitext(nombre)[1]
    if ext in LENGUAJES:
        return LENGUAJES[ext]
    if not ext:
        return NOMBRES_SIN_EXTENSION.get(nombre)
    return None


def _excluida(ruta: str) -> bool:
    partes = [p.lower() for p in ruta.split("/")]
    if any(p in DIRECTORIOS_EXCLUIDOS for p in partes[:-1]):
        return True
    return partes[-1] in ARCHIVOS_EXCLUIDOS


def _decodificar(datos: bytes) -> str | None:
    if b"\x00" in datos[:4096]:
        return None
    texto = datos.decode("utf-8", errors="replace")
    if texto and texto.count("�") / len(texto) > 0.05:
        return None
    return texto


def _celda_a_python(codigo: str) -> str:
    """Neutraliza magics de IPython (%, !) para poder usar ast.parse."""
    lineas = ["pass" if ln.lstrip().startswith(("%", "!")) else ln for ln in codigo.split("\n")]
    return "\n".join(lineas)


def _notebook(texto: str) -> tuple[str, list[tuple[int, str]]] | None:
    try:
        datos = json.loads(texto)
        celdas = datos["cells"]
    except (ValueError, KeyError, TypeError):
        return None
    partes: list[str] = []
    codigo: list[tuple[int, str]] = []
    for i, celda in enumerate(celdas, start=1):
        if not isinstance(celda, dict):
            continue
        fuente = celda.get("source", "")
        cuerpo = "".join(fuente) if isinstance(fuente, list) else str(fuente)
        tipo = celda.get("cell_type")
        if tipo == "code":
            partes.append(f"### [celda {i} - código]\n{cuerpo}")
            codigo.append((i, _celda_a_python(cuerpo)))
        elif tipo == "markdown":
            partes.append(f"### [celda {i} - markdown]\n{cuerpo}")
    return "\n".join(partes), codigo


def extraer_zip(
    ruta: Path, evidencia_id: int | None, advertencias: list[str]
) -> list[ArchivoCodigo]:
    """Lee el ZIP en memoria y devuelve solo archivos de texto de código."""
    archivos: list[ArchivoCodigo] = []
    omitidos_tipo = 0
    peligrosas: list[str] = []
    total = 0
    try:
        zf = zipfile.ZipFile(ruta)
    except (zipfile.BadZipFile, OSError):
        advertencias.append(f"No se pudo abrir el ZIP de código ({ruta.name}); no se analizó.")
        return []
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_ENTRADAS_ZIP:
            advertencias.append(
                f"El ZIP tiene {len(infos)} entradas; solo se revisaron las primeras "
                f"{MAX_ENTRADAS_ZIP}."
            )
            infos = infos[:MAX_ENTRADAS_ZIP]
        for info in infos:
            if info.is_dir():
                continue
            modo = info.external_attr >> 16
            if modo and stat.S_ISLNK(modo):
                peligrosas.append(info.filename)
                continue
            ruta_arch = ruta_segura(info.filename)
            if ruta_arch is None:
                peligrosas.append(info.filename)
                continue
            if _excluida(ruta_arch):
                continue
            lenguaje = _lenguaje(ruta_arch)
            if lenguaje is None:
                omitidos_tipo += 1
                continue
            if len(archivos) >= MAX_ARCHIVOS_CODIGO:
                advertencias.append(
                    f"Se alcanzó el máximo de {MAX_ARCHIVOS_CODIGO} archivos de código; "
                    "el resto se omitió."
                )
                break
            if total >= MAX_BYTES_TOTAL:
                advertencias.append(
                    "Se alcanzó el tope total de bytes del código; el resto se omitió."
                )
                break
            with zf.open(info) as f:
                datos = f.read(MAX_BYTES_ARCHIVO + 1)
            truncado = len(datos) > MAX_BYTES_ARCHIVO
            datos = datos[:MAX_BYTES_ARCHIVO]
            total += len(datos)
            texto = _decodificar(datos)
            if texto is None:
                omitidos_tipo += 1
                continue
            celdas: list[tuple[int, str]] = []
            if lenguaje == "notebook":
                nb = None if truncado else _notebook(texto)
                if nb is None:
                    advertencias.append(
                        f"El notebook {ruta_arch} no es un JSON válido o es demasiado grande."
                    )
                    continue
                texto, celdas = nb
            elif truncado:
                advertencias.append(
                    f"El archivo {ruta_arch} supera {MAX_BYTES_ARCHIVO} bytes y se truncó."
                )
            archivos.append(
                ArchivoCodigo(ruta_arch, lenguaje, texto, evidencia_id, truncado, celdas)
            )
    if peligrosas:
        advertencias.append(
            "Se ignoraron entradas del ZIP con rutas peligrosas o enlaces simbólicos: "
            + ", ".join(peligrosas[:5])
            + ("..." if len(peligrosas) > 5 else "")
        )
    if omitidos_tipo:
        advertencias.append(
            f"Se omitieron {omitidos_tipo} archivos binarios o de tipo no analizable."
        )
    return archivos


# ---------- Armado del contexto ----------


def _numerar(texto: str) -> str:
    return "\n".join(f"{i:>4}| {ln}" for i, ln in enumerate(texto.split("\n"), start=1))


def _prioridad(a: ArchivoCodigo) -> tuple[int, int, str]:
    base = posixpath.splitext(posixpath.basename(a.ruta).lower())[0]
    if base in _PRINCIPALES:
        grupo = 0
    elif a.lenguaje in _LENGUAJES_FUENTE:
        grupo = 1
    else:
        grupo = 2
    return grupo, a.ruta.count("/"), a.ruta


def _tipo_imagen(datos: bytes) -> str | None:
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if datos.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp"
    if datos[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None


def _informes(evs: list[EvidenciaContexto], tope: int, adv: list[str]) -> list[FuenteTexto]:
    candidatos: list[tuple[EvidenciaContexto, str]] = []
    for ev in evs:
        if ev.tipo == "informe_pdf":
            if ev.texto_extraido and ev.texto_extraido.strip():
                candidatos.append((ev, "informe_pdf"))
            else:
                adv.append(f"El informe ({ev.nombre_original or ev.id}) no tiene texto extraído.")
        elif ev.tipo == "presentacion" and ev.texto_extraido and ev.texto_extraido.strip():
            candidatos.append((ev, f"presentacion:{ev.nombre_original or ev.id}"))
    if sum(1 for _, f in candidatos if f == "informe_pdf") > 1:  # desambiguar fuentes
        candidatos = [
            (e, f"informe_pdf:{e.nombre_original or e.id}") if f == "informe_pdf" else (e, f)
            for e, f in candidatos
        ]
    fuentes: list[FuenteTexto] = []
    restante = tope
    for ev, fuente in candidatos:
        original = ev.texto_extraido or ""
        if restante <= 0:
            adv.append(f"Se omitió {fuente} por el tope de contexto.")
            continue
        trunc = len(original) > restante
        if trunc:
            adv.append(
                f"El texto de {fuente} se recortó a {restante} de {len(original)} caracteres "
                "por el tope de contexto."
            )
        visible = original[:restante]
        restante -= len(visible)
        fuentes.append(FuenteTexto(fuente, ev.id, neutralizar(visible), original, trunc))
    return fuentes


def preparar_contexto(
    contexto: ContextoEvaluacion, settings: Settings, aceptar_imagenes: bool
) -> ContextoPreparado:
    prep = ContextoPreparado()
    adv = prep.advertencias
    tope = settings.ia_max_caracteres_contexto
    evs = contexto.evidencias

    # Código (todo lo extraído sirve para la verificación; al modelo va lo que quepa)
    for ev in evs:
        nombre = ev.nombre_original or str(ev.id)
        if ev.tipo == "codigo_zip":
            if not ev.ruta_archivo or not Path(ev.ruta_archivo).is_file():
                adv.append(f"El archivo ZIP de código ({nombre}) no está disponible.")
                continue
            prep.archivos.extend(extraer_zip(Path(ev.ruta_archivo), ev.id, adv))
        elif ev.tipo == "repo_github":
            prep.repositorios_no_analizados.append(ev.url or ev.nombre_original or f"evidencia {ev.id}")
        elif ev.tipo == "video":
            adv.append(f"El video ({nombre}) no se analizó.")
    if prep.repositorios_no_analizados:
        adv.append(
            "Los repositorios de GitHub no se clonan en esta versión: "
            + ", ".join(prep.repositorios_no_analizados)
        )

    # Informe: hasta 60 % del tope si hay código; todo el tope si no
    tope_informe = int(tope * 0.6) if prep.archivos else tope
    prep.fuentes.extend(_informes(evs, tope_informe, adv))
    usado = sum(len(f.texto_prompt) for f in prep.fuentes)

    # Código priorizado
    omitidos: list[str] = []
    for a in sorted(prep.archivos, key=_prioridad):
        encabezado = len(a.ruta) + 60
        numerado = _numerar(a.texto)
        restante = tope - usado - encabezado
        if restante <= 0 or (len(numerado) > restante and restante < MIN_CARACTERES_UTILES):
            omitidos.append(a.ruta)
            continue
        trunc = a.truncado
        if len(numerado) > restante:
            numerado = numerado[:restante]
            trunc = True
            adv.append(f"El archivo {a.ruta} se recortó por el tope de contexto.")
        usado += len(numerado) + encabezado
        prep.fuentes.append(
            FuenteTexto(f"codigo:{a.ruta}", a.evidencia_id, neutralizar(numerado), a.texto, trunc)
        )
    if omitidos:
        adv.append(
            f"Por el tope de contexto ({tope} caracteres) se omitieron {len(omitidos)} archivos de "
            "código en el prompt (sí se verificaron técnicamente): "
            + ", ".join(omitidos[:8])
            + ("..." if len(omitidos) > 8 else "")
        )

    # Imágenes
    for ev in (e for e in evs if e.tipo == "imagen"):
        nombre = ev.nombre_original or f"imagen_{ev.id}"
        if not aceptar_imagenes:
            adv.append(
                f"La imagen {nombre} no se analizó: el proveedor de IA activo no admite imágenes."
            )
            continue
        if len(prep.imagenes) >= MAX_IMAGENES:
            adv.append(
                f"La imagen {nombre} no se analizó: máximo {MAX_IMAGENES} imágenes por evaluación."
            )
            continue
        if not ev.ruta_archivo or not Path(ev.ruta_archivo).is_file():
            adv.append(f"La imagen {nombre} no está disponible en disco.")
            continue
        p = Path(ev.ruta_archivo)
        if p.stat().st_size > MAX_BYTES_IMAGEN:
            adv.append(f"La imagen {nombre} supera 5 MB y no se analizó.")
            continue
        datos = p.read_bytes()
        tipo = _tipo_imagen(datos)
        if tipo is None:
            adv.append(f"La imagen {nombre} tiene un formato no admitido y no se analizó.")
            continue
        prep.imagenes.append(
            ImagenAdjunta(f"imagen:{nombre}", ev.id, tipo, base64.standard_b64encode(datos).decode())
        )
    return prep

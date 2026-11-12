"""RF-02: carga, validación y almacenamiento de evidencias.

Reglas (docs/API.md, "Reglas de carga de evidencias"):
- El tamaño se controla mientras se lee (no se confía en `Content-Length`).
- El formato se decide por la firma de bytes, no por la extensión ni el Content-Type.
- Nada se descomprime ni se ejecuta; los ZIP solo se inspeccionan.
- La ruta en disco nunca usa el nombre original: `entregas/<entrega_id>/<uuid4><ext>`.
"""

import hashlib
import os
import re
import uuid
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, status
from pypdf import PdfReader

from app.models.entrega import Entrega
from app.models.enums import TipoEvidencia

MB = 1024 * 1024
BLOQUE = 64 * 1024

MIN_CARACTERES_PDF = 200
MAX_ENTRADAS_ZIP = 2000
MAX_DESCOMPRIMIDO_ZIP = 200 * MB
TOP_EXTENSIONES = 5

ESTADOS_EDITABLES = ("borrador", "lista")

_GITHUB = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))"
    r"/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
_UNIDAD_WINDOWS = re.compile(r"^[A-Za-z]:")
_CARACTERES_PROHIBIDOS = set('"<>|:*?')


@dataclass(frozen=True)
class Formato:
    ext: str
    descripcion: str


@dataclass(frozen=True)
class Regla:
    max_bytes: int
    formatos: dict[str, Formato]  # clave = formato detectado por firma


_PDF = {"pdf": Formato(".pdf", "PDF")}
_ZIP = {"zip": Formato(".zip", "ZIP")}

REGLAS: dict[TipoEvidencia, Regla] = {
    TipoEvidencia.informe_pdf: Regla(20 * MB, _PDF),
    TipoEvidencia.codigo_zip: Regla(50 * MB, _ZIP),
    TipoEvidencia.imagen: Regla(
        10 * MB, {"png": Formato(".png", "PNG"), "jpeg": Formato(".jpg", "JPEG")}
    ),
    TipoEvidencia.presentacion: Regla(50 * MB, {**_PDF, "pptx": Formato(".pptx", "PPTX")}),
    TipoEvidencia.video: Regla(
        50 * MB, {"mp4": Formato(".mp4", "MP4"), "webm": Formato(".webm", "WEBM")}
    ),
}


@dataclass
class EvidenciaProcesada:
    ruta_relativa: str | None
    url: str | None
    nombre_original: str | None
    sha256: str | None
    tamano_bytes: int | None
    texto_extraido: str | None
    detalle: dict


def _error(codigo: int, mensaje: str) -> HTTPException:
    return HTTPException(codigo, mensaje)


# ---------------------------------------------------------------- estado de la entrega


def faltantes(entrega: Entrega) -> list[str]:
    tipos = {e.tipo for e in entrega.evidencias}
    falta: list[str] = []
    if TipoEvidencia.informe_pdf.value not in tipos:
        falta.append("informe_pdf")
    if not tipos & {TipoEvidencia.codigo_zip.value, TipoEvidencia.repo_github.value}:
        falta.append("codigo")
    return falta


def recalcular_estado(entrega: Entrega) -> None:
    """Solo mueve entre `borrador` y `lista`; los demás estados no se tocan."""
    if entrega.estado in ESTADOS_EDITABLES:
        entrega.estado = "borrador" if faltantes(entrega) else "lista"


# ---------------------------------------------------------------- firmas


def detectar_formato(cabecera: bytes) -> str | None:
    if cabecera.startswith(b"%PDF"):
        return "pdf"
    if cabecera.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if cabecera.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if cabecera.startswith(b"PK\x03\x04"):
        return "zip"  # para `presentacion` se refina a pptx al inspeccionar el contenedor
    if cabecera[4:8] == b"ftyp":
        return "mp4"
    if cabecera.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"
    return None


def _es_pptx(ruta: Path) -> bool:
    try:
        with zipfile.ZipFile(ruta) as z:
            nombres = z.namelist()
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in nombres and any(n.startswith("ppt/") for n in nombres)


# ---------------------------------------------------------------- inspección


def nombre_seguro(nombre: str | None, ext: str) -> str:
    """Nombre original saneado: sin rutas, sin caracteres de control ni comillas."""
    base = (nombre or "").replace("\\", "/").split("/")[-1]
    base = "".join(c for c in base if c.isprintable() and c not in _CARACTERES_PROHIBIDOS)
    base = base.strip(". ")[:255]
    return base or f"archivo{ext}"


def inspeccionar_pdf(ruta: Path) -> tuple[str, dict]:
    try:
        lector = PdfReader(str(ruta))
        if lector.is_encrypted:
            raise _error(status.HTTP_400_BAD_REQUEST, "El PDF está protegido con contraseña.")
        paginas = len(lector.pages)
        texto = "\n".join((p.extract_text() or "") for p in lector.pages).strip()
    except HTTPException:
        raise
    except Exception:
        raise _error(
            status.HTTP_400_BAD_REQUEST, "El PDF está dañado o no se puede leer."
        ) from None
    if len(texto) < MIN_CARACTERES_PDF:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "El PDF no tiene texto legible (se requieren al menos "
            f"{MIN_CARACTERES_PDF} caracteres). Si es un escaneo, genera un PDF con texto.",
        )
    return texto, {"paginas": paginas, "caracteres_texto": len(texto)}


def _ruta_peligrosa(nombre: str) -> bool:
    if nombre.startswith(("/", "\\")) or _UNIDAD_WINDOWS.match(nombre) or "\x00" in nombre:
        return True
    return ".." in nombre.replace("\\", "/").split("/")


def inspeccionar_zip(ruta: Path) -> dict:
    """Solo lee el directorio central: no extrae ni ejecuta nada."""
    try:
        with zipfile.ZipFile(ruta) as z:
            entradas = z.infolist()
    except zipfile.BadZipFile:
        raise _error(status.HTTP_400_BAD_REQUEST, "El archivo ZIP está dañado.") from None
    if not entradas:
        raise _error(status.HTTP_400_BAD_REQUEST, "El ZIP está vacío.")
    if len(entradas) > MAX_ENTRADAS_ZIP:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            f"El ZIP tiene demasiados archivos (máximo {MAX_ENTRADAS_ZIP}).",
        )
    for e in entradas:
        if _ruta_peligrosa(e.filename):
            raise _error(
                status.HTTP_400_BAD_REQUEST,
                "El ZIP contiene rutas no permitidas (absolutas o con '..').",
            )
    total = sum(e.file_size for e in entradas)
    if total > MAX_DESCOMPRIMIDO_ZIP:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            f"El ZIP descomprimido supera {MAX_DESCOMPRIMIDO_ZIP // MB} MB.",
        )
    archivos = [e for e in entradas if not e.is_dir()]
    exts = Counter(Path(e.filename).suffix.lower() or "(sin extensión)" for e in archivos)
    return {
        "archivos": len(archivos),
        "tamano_descomprimido_bytes": total,
        "extensiones": dict(exts.most_common(TOP_EXTENSIONES)),
    }


def procesar_repo(url: str | None) -> EvidenciaProcesada:
    m = _GITHUB.match((url or "").strip())
    if not m or m["repo"] in (".", ".."):
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "La URL debe tener la forma https://github.com/<usuario>/<repositorio>.",
        )
    owner, repo = m["owner"], m["repo"]
    return EvidenciaProcesada(
        ruta_relativa=None,
        url=f"https://github.com/{owner}/{repo}",
        nombre_original=None,
        sha256=None,
        tamano_bytes=None,
        texto_extraido=None,
        detalle={"owner": owner, "repo": repo},
    )


# ---------------------------------------------------------------- carga


def guardar_archivo(
    storage_dir: Path,
    entrega_id: int,
    tipo: TipoEvidencia,
    flujo: BinaryIO,
    nombre_original: str | None,
) -> EvidenciaProcesada:
    """Lee por bloques, valida y deja el archivo en disco. Si algo falla, no queda nada."""
    regla = REGLAS[tipo]
    permitidos = ", ".join(f.descripcion for f in regla.formatos.values())
    formato_invalido = (
        f"El contenido del archivo no corresponde a un formato aceptado ({permitidos})."
    )

    primer = flujo.read(BLOQUE)
    if not primer:
        raise _error(status.HTTP_400_BAD_REQUEST, "El archivo está vacío.")
    formato = detectar_formato(primer[:64])
    # `.pptx` también empieza con la firma ZIP: se decide al inspeccionar el contenedor.
    es_zip_candidato = formato == "zip" and "pptx" in regla.formatos
    if formato not in regla.formatos and not es_zip_candidato:
        raise _error(status.HTTP_400_BAD_REQUEST, formato_invalido)

    carpeta = storage_dir / "entregas" / str(entrega_id)
    carpeta.mkdir(parents=True, exist_ok=True)
    temporal = carpeta / f"{uuid.uuid4()}.tmp"
    sha = hashlib.sha256()
    tamano = 0
    try:
        with open(temporal, "wb") as destino:
            bloque = primer
            while bloque:
                tamano += len(bloque)
                if tamano > regla.max_bytes:
                    raise _error(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        f"El archivo supera el tamaño máximo de {regla.max_bytes // MB} MB.",
                    )
                sha.update(bloque)
                destino.write(bloque)
                bloque = flujo.read(BLOQUE)

        if es_zip_candidato:
            if not _es_pptx(temporal):
                raise _error(status.HTTP_400_BAD_REQUEST, formato_invalido)
            formato = "pptx"

        texto: str | None = None
        detalle: dict = {}
        if tipo is TipoEvidencia.informe_pdf:
            texto, detalle = inspeccionar_pdf(temporal)
        elif tipo is TipoEvidencia.codigo_zip:
            detalle = inspeccionar_zip(temporal)

        ext = regla.formatos[formato].ext
        final = carpeta / f"{uuid.uuid4()}{ext}"
        os.replace(temporal, final)
    except BaseException:
        temporal.unlink(missing_ok=True)
        raise

    return EvidenciaProcesada(
        ruta_relativa=final.relative_to(storage_dir).as_posix(),
        url=None,
        nombre_original=nombre_seguro(nombre_original, ext),
        sha256=sha.hexdigest(),
        tamano_bytes=tamano,
        texto_extraido=texto,
        detalle=detalle,
    )


def ruta_absoluta(storage_dir: Path, ruta_relativa: str) -> Path | None:
    """Resuelve la ruta dentro de `storage_dir`; None si se sale de él (defensa en profundidad)."""
    raiz = storage_dir.resolve()
    ruta = (raiz / ruta_relativa).resolve()
    return ruta if ruta.is_relative_to(raiz) else None


def borrar_archivo(storage_dir: Path, ruta_relativa: str | None) -> None:
    if not ruta_relativa:
        return
    ruta = ruta_absoluta(storage_dir, ruta_relativa)
    if ruta is not None:
        ruta.unlink(missing_ok=True)

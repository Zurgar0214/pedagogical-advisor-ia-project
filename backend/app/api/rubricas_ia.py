"""RF-04: interpretación de rúbricas con IA. Solo propone; no guarda nada."""

import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import requiere_rol
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.evaluacion.contrato import ErrorEvaluacion, UsoModelo
from app.evaluacion.rubrica_ia import ProveedorNoDisponible, interpretar_rubrica
from app.models.enums import Rol
from app.models.usuario import Usuario
from app.schemas.laboratorio import ValidacionSalida
from app.schemas.rubrica import Rubrica as RubricaContenido
from app.services import auditoria
from app.services.evidencias import MB, inspeccionar_pdf
from app.services.validacion_rubrica import validar_rubrica

router = APIRouter(tags=["rubricas-ia"])

_gestor = requiere_rol(Rol.docente, Rol.admin)

MAX_PDF_BYTES = 10 * MB
MIN_TEXTO = 50
MAX_TEXTO = 60_000


class InterpretacionSalida(BaseModel):
    rubrica: RubricaContenido
    validacion: ValidacionSalida
    observaciones: list[str] = Field(default_factory=list)
    advertencias: list[str] = Field(default_factory=list)
    proveedor: str
    modelo: str
    uso: list[UsoModelo]
    costo_usd_estimado: float


def _texto_de_pdf(contenido: bytes) -> tuple[str, int]:
    """Texto del PDF (inspección reutilizada de evidencias) y número de páginas."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(contenido)
        ruta = Path(tmp.name)
    try:
        texto, detalle = inspeccionar_pdf(ruta)
        return texto, detalle["paginas"]
    finally:
        ruta.unlink(missing_ok=True)


@router.post("/rubricas/interpretar", response_model=InterpretacionSalida)
async def interpretar(
    archivo: Annotated[UploadFile | None, File()] = None,
    texto: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_gestor),
    settings: Settings = Depends(get_settings),
) -> InterpretacionSalida:
    if (archivo is None) == (texto is None):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Envía exactamente uno: un PDF (archivo) o texto."
        )

    advertencias: list[str] = []
    if archivo is not None:
        contenido = await archivo.read(MAX_PDF_BYTES + 1)
        if len(contenido) > MAX_PDF_BYTES:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"El archivo supera el tamaño máximo de {MAX_PDF_BYTES // MB} MB.",
            )
        if not contenido.startswith(b"%PDF"):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "El contenido del archivo no corresponde a un PDF.",
            )
        origen = "pdf"
        documento, _ = await run_in_threadpool(_texto_de_pdf, contenido)
        if len(documento) > MAX_TEXTO:
            documento = documento[:MAX_TEXTO]
            advertencias.append(
                f"El PDF supera {MAX_TEXTO} caracteres de texto; se recortó y "
                "se interpretó solo el inicio."
            )
    else:
        origen = "texto"
        documento = (texto or "").strip()
        if not MIN_TEXTO <= len(documento) <= MAX_TEXTO:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"El texto debe tener entre {MIN_TEXTO} y {MAX_TEXTO} caracteres.",
            )

    try:
        resultado = await run_in_threadpool(interpretar_rubrica, documento, settings)
    except ErrorEvaluacion as e:
        codigo = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if isinstance(e, ProveedorNoDisponible)
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(codigo, str(e)) from None

    inconsistencias = validar_rubrica(resultado.rubrica)
    auditoria.registrar(
        db,
        usuario.id,
        "interpretar_rubrica",
        "rubrica",
        None,
        {
            "origen": origen,
            "caracteres": len(documento),
            "proveedor": resultado.proveedor,
            "modelo": resultado.modelo,
            "criterios": len(resultado.rubrica.criterios),
        },
    )
    db.commit()
    return InterpretacionSalida(
        rubrica=resultado.rubrica,
        validacion=ValidacionSalida(valida=not inconsistencias, inconsistencias=inconsistencias),
        observaciones=resultado.observaciones,
        advertencias=[*resultado.advertencias, *advertencias],
        proveedor=resultado.proveedor,
        modelo=resultado.modelo,
        uso=resultado.uso,
        costo_usd_estimado=round(sum(u.costo_usd_estimado for u in resultado.uso), 8),
    )

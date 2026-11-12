"""Enumeraciones del dominio. En la base de datos se guardan como cadenas."""

from enum import StrEnum


class Rol(StrEnum):
    admin = "admin"
    docente = "docente"
    estudiante = "estudiante"


class TipoEvidencia(StrEnum):
    informe_pdf = "informe_pdf"
    codigo_zip = "codigo_zip"
    repo_github = "repo_github"
    video = "video"
    presentacion = "presentacion"
    imagen = "imagen"


class EstadoEvaluacion(StrEnum):
    borrador = "borrador"  # valor heredado (iteración 1); el flujo actual no lo usa
    procesando = "procesando"
    en_revision = "en_revision"
    aprobada = "aprobada"
    publicada = "publicada"
    error = "error"

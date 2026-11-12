"""Importar todos los modelos aquí registra las tablas en `Base.metadata` (Alembic y pruebas)."""

from app.models.auditoria import Auditoria
from app.models.entrega import Entrega, Evidencia
from app.models.enums import EstadoEvaluacion, Rol, TipoEvidencia
from app.models.evaluacion import AjusteCriterio, Evaluacion
from app.models.informe import Informe
from app.models.laboratorio import Laboratorio, Rubrica, RubricaVersion
from app.models.usuario import Usuario

__all__ = [
    "AjusteCriterio",
    "Auditoria",
    "Entrega",
    "EstadoEvaluacion",
    "Evaluacion",
    "Evidencia",
    "Informe",
    "Laboratorio",
    "Rol",
    "Rubrica",
    "RubricaVersion",
    "TipoEvidencia",
    "Usuario",
]
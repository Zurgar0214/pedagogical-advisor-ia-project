from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import FechaUTC, TipoJSON, ahora_utc
from app.models.enums import EstadoEvaluacion


class Evaluacion(Base):
    __tablename__ = "evaluaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    entrega_id: Mapped[int] = mapped_column(ForeignKey("entregas.id"))
    rubrica_version_id: Mapped[int] = mapped_column(ForeignKey("rubrica_versiones.id"))
    estado: Mapped[str] = mapped_column(String(20), default=EstadoEvaluacion.borrador.value)
    proveedor: Mapped[str | None] = mapped_column(String(50), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parametros: Mapped[dict | None] = mapped_column(TipoJSON, nullable=True)
    resultado_ia: Mapped[dict | None] = mapped_column(TipoJSON, nullable=True)
    verificacion: Mapped[dict | None] = mapped_column(TipoJSON, nullable=True)
    nota_preliminar: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    nota_final: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    revisado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    aprobado_en: Mapped[datetime | None] = mapped_column(FechaUTC, nullable=True)
    publicado_en: Mapped[datetime | None] = mapped_column(FechaUTC, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora_utc)
    # Iteración 3
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_prompt: Mapped[str | None] = mapped_column(String(50), nullable=True)
    modelo_escalamiento: Mapped[str | None] = mapped_column(String(100), nullable=True)
    requiere_revision: Mapped[bool] = mapped_column(Boolean, default=False)
    advertencias: Mapped[list | None] = mapped_column(TipoJSON, nullable=True)
    uso: Mapped[list | None] = mapped_column(TipoJSON, nullable=True)
    costo_usd_estimado: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)

    entrega = relationship("Entrega")
    rubrica_version = relationship("RubricaVersion")
    revisor = relationship("Usuario", foreign_keys=[revisado_por])
    ajustes: Mapped[list["AjusteCriterio"]] = relationship(
        back_populates="evaluacion", order_by="AjusteCriterio.id"
    )


class AjusteCriterio(Base):
    """Historial de ajustes del docente a un criterio (RF-08). Nunca se edita ni se borra."""

    __tablename__ = "ajustes_criterio"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluacion_id: Mapped[int] = mapped_column(ForeignKey("evaluaciones.id"))
    criterio_id: Mapped[str] = mapped_column(String(100))
    nivel_anterior: Mapped[str] = mapped_column(String(200))
    nivel_nuevo: Mapped[str] = mapped_column(String(200))
    justificacion: Mapped[str] = mapped_column(Text)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(FechaUTC, default=ahora_utc)

    evaluacion: Mapped[Evaluacion] = relationship(back_populates="ajustes")
    usuario = relationship("Usuario")
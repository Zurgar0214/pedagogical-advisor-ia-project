from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import FechaUTC, ahora_utc


class Entrega(Base):
    """Portafolio de un estudiante para un laboratorio (única por estudiante y laboratorio)."""

    __tablename__ = "entregas"
    __table_args__ = (UniqueConstraint("estudiante_id", "laboratorio_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    laboratorio_id: Mapped[int] = mapped_column(ForeignKey("laboratorios.id"))
    rubrica_version_id: Mapped[int] = mapped_column(ForeignKey("rubrica_versiones.id"))
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")
    creado_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora_utc)

    evidencias: Mapped[list["Evidencia"]] = relationship(back_populates="entrega")


class Evidencia(Base):
    __tablename__ = "evidencias"

    id: Mapped[int] = mapped_column(primary_key=True)
    entrega_id: Mapped[int] = mapped_column(ForeignKey("entregas.id"))
    tipo: Mapped[str] = mapped_column(String(20))
    ruta_archivo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nombre_original: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tamano_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora_utc)

    entrega: Mapped[Entrega] = relationship(back_populates="evidencias")
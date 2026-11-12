from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import FechaUTC, TipoJSON, ahora_utc


class Laboratorio(Base):
    __tablename__ = "laboratorios"

    id: Mapped[int] = mapped_column(primary_key=True)
    cohorte: Mapped[int] = mapped_column(Integer)  # 1 o 2
    codigo: Mapped[str] = mapped_column(String(50), unique=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    objetivos: Mapped[str] = mapped_column(Text, default="")
    temas: Mapped[list] = mapped_column(TipoJSON, default=list)

    rubrica: Mapped["Rubrica | None"] = relationship(back_populates="laboratorio", uselist=False)


class Rubrica(Base):
    """Rúbrica lógica: una por laboratorio. El contenido vive en `RubricaVersion`."""

    __tablename__ = "rubricas"

    id: Mapped[int] = mapped_column(primary_key=True)
    laboratorio_id: Mapped[int] = mapped_column(ForeignKey("laboratorios.id"), unique=True)

    laboratorio: Mapped[Laboratorio] = relationship(back_populates="rubrica")
    versiones: Mapped[list["RubricaVersion"]] = relationship(
        back_populates="rubrica", order_by="RubricaVersion.numero"
    )


class RubricaVersion(Base):
    """Versión inmutable de una rúbrica: editar crea una versión nueva (RF-03)."""

    __tablename__ = "rubrica_versiones"
    __table_args__ = (UniqueConstraint("rubrica_id", "numero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    rubrica_id: Mapped[int] = mapped_column(ForeignKey("rubricas.id"))
    numero: Mapped[int] = mapped_column(Integer)
    contenido: Mapped[dict] = mapped_column(TipoJSON)  # esquema `Rubrica`
    valida: Mapped[bool] = mapped_column(Boolean, default=False)
    inconsistencias: Mapped[list] = mapped_column(TipoJSON, default=list)
    creado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora_utc)

    rubrica: Mapped[Rubrica] = relationship(back_populates="versiones")
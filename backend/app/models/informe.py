from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import FechaUTC, TipoJSON, ahora_utc
from app.models.usuario import Usuario


class Informe(Base):
    """Informe integral de un estudiante (RF-09). Se construye solo con evaluaciones publicadas."""

    __tablename__ = "informes"

    id: Mapped[int] = mapped_column(primary_key=True)
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    estado: Mapped[str] = mapped_column(String(20), default="procesando")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    generado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    generado_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora_utc)
    evaluaciones_incluidas: Mapped[list | None] = mapped_column(TipoJSON, nullable=True)
    agregado: Mapped[dict | None] = mapped_column(TipoJSON, nullable=True)
    sintesis: Mapped[dict | None] = mapped_column(TipoJSON, nullable=True)
    temas_categoria: Mapped[dict | None] = mapped_column(TipoJSON, nullable=True)
    proveedor: Mapped[str | None] = mapped_column(String(50), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version_prompt: Mapped[str | None] = mapped_column(String(50), nullable=True)
    advertencias: Mapped[list | None] = mapped_column(TipoJSON, nullable=True)
    uso: Mapped[list | None] = mapped_column(TipoJSON, nullable=True)
    costo_usd_estimado: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)

    estudiante: Mapped[Usuario] = relationship(foreign_keys=[estudiante_id])
    generador: Mapped[Usuario] = relationship(foreign_keys=[generado_por])

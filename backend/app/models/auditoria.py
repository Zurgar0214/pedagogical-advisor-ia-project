from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import FechaUTC, TipoJSON, ahora_utc


class Auditoria(Base):
    """Registro de acciones sensibles (RF-08). Nunca guarda contraseñas."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    accion: Mapped[str] = mapped_column(String(60))
    entidad: Mapped[str] = mapped_column(String(60))
    entidad_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detalle: Mapped[dict | None] = mapped_column(TipoJSON, nullable=True)
    fecha: Mapped[datetime] = mapped_column(FechaUTC, default=ahora_utc)
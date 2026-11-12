from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
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

    entrega = relationship("Entrega")
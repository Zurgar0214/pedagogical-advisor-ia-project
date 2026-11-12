from datetime import datetime

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import FechaUTC, ahora_utc
from app.models.enums import Rol


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150))
    correo: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    hash_contrasena: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20), default=Rol.estudiante.value)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora_utc)
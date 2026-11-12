"""Tipos y utilidades comunes de los modelos."""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime
from sqlalchemy.types import TypeDecorator

# JSON genérico: funciona igual en PostgreSQL y SQLite.
TipoJSON = JSON


def ahora_utc() -> datetime:
    return datetime.now(UTC)


class FechaUTC(TypeDecorator):
    """DateTime con zona horaria que siempre devuelve datetimes en UTC (SQLite pierde la zona)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
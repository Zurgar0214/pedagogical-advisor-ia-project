"""Configuración por variables de entorno (los secretos nunca van en el repositorio)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_nombre: str = "Asesor Pedagógico Inteligente"
    app_version: str = "0.1.0"
    database_url: str = "sqlite:///./dev.db"
    secret_key: str = "dev-inseguro-cambiar-en-produccion"
    cors_origins: list[str] = ["http://localhost:5173"]
    storage_dir: str = "./storage"
    ai_provider: str = "claude"  # claude | ollama
    admin_correo: str | None = None
    admin_contrasena: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
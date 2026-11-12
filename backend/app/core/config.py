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
    # Proveedor de IA (RNF-05): claude | ollama | falso (determinista, sin clave)
    ai_provider: str = "falso"
    anthropic_api_key: str | None = None
    ia_modelo_principal: str = "claude-haiku-5-5"
    ia_modelo_escalamiento: str = "claude-sonnet-5-5"
    # criterios con confianza por debajo se reevalúan con el modelo de escalamiento
    ia_umbral_confianza: float = 0.6
    ia_max_caracteres_contexto: int = 120_000  # tope de texto de evidencias enviado al modelo
    ollama_url: str = "http://localhost:11434"
    ollama_modelo: str = "qwen2.5:7b"
    admin_correo: str | None = None
    admin_contrasena: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
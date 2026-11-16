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
    ollama_modelo: str = "qwen2.5-coder:7b"
    ollama_num_ctx: int = 16384  # Ollama recorta el prompt en silencio si no cabe
    # Sandbox de ejecución de pruebas (RNF-04): vacío = deshabilitada
    sandbox_url: str = ""
    sandbox_token: str = ""
    sandbox_timeout_s: int = 60
    admin_correo: str | None = None
    admin_contrasena: str | None = None


SECRETOS_INSEGUROS = {
    "dev-inseguro-cambiar-en-produccion",
    "cambia-esta-clave-larga-y-aleatoria",
    "cambia-esto-por-un-token-largo",
}


def verificar_secretos(s: Settings) -> None:
    """Impide arrancar con secretos de ejemplo fuera del entorno de desarrollo (SQLite).

    Con PostgreSQL (Docker / producción) se exige SECRET_KEY propio de al menos 32 caracteres
    y, si la sandbox está activa, un SANDBOX_TOKEN propio de al menos 32 caracteres.
    """
    if s.database_url.startswith("sqlite"):
        return
    errores = []
    if s.secret_key in SECRETOS_INSEGUROS or len(s.secret_key) < 32:
        errores.append("SECRET_KEY es de ejemplo o tiene menos de 32 caracteres")
    if s.sandbox_url and (s.sandbox_token in SECRETOS_INSEGUROS or len(s.sandbox_token) < 32):
        errores.append("SANDBOX_TOKEN es de ejemplo o tiene menos de 32 caracteres")
    if errores:
        raise RuntimeError(
            "Configuración insegura: " + "; ".join(errores) + ". "
            "Genera valores aleatorios en .env, "
            "p. ej. python -c \"import secrets; print(secrets.token_urlsafe(48))\"."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
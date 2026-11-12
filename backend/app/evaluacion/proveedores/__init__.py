"""Proveedores de IA y fábrica según `settings.ai_provider`."""

import httpx

from app.core.config import Settings
from app.evaluacion.proveedores.base import ErrorProveedor, ProveedorIA
from app.evaluacion.proveedores.claude import ClaudeProveedor
from app.evaluacion.proveedores.falso import FalsoProveedor
from app.evaluacion.proveedores.ollama import OllamaProveedor

PROVEEDORES = ("claude", "ollama", "falso")


def crear_proveedor(settings: Settings) -> ProveedorIA:
    nombre = (settings.ai_provider or "").strip().lower()
    if nombre == "claude":
        return ClaudeProveedor(settings)
    if nombre == "ollama":
        return OllamaProveedor(settings)
    if nombre == "falso":
        return FalsoProveedor(settings)
    raise ErrorProveedor(
        f"Proveedor de IA desconocido: '{settings.ai_provider}'. Usa uno de: {', '.join(PROVEEDORES)}."
    )


def estado_de(settings: Settings, cliente_http: httpx.Client | None = None) -> tuple[bool, str]:
    """(disponible, motivo). Solo revisa configuración; no hace llamadas de pago."""
    nombre = (settings.ai_provider or "").strip().lower()
    if nombre == "claude":
        if not (settings.anthropic_api_key or "").strip():
            return False, "Falta la clave de la API de Anthropic (variable ANTHROPIC_API_KEY)."
        return True, (
            f"Claude configurado (principal {settings.ia_modelo_principal}, "
            f"escalamiento {settings.ia_modelo_escalamiento})."
        )
    if nombre == "ollama":
        url = settings.ollama_url.rstrip("/")
        try:
            http = cliente_http or httpx.Client(timeout=3.0)
            r = http.get(f"{url}/api/tags")
            r.raise_for_status()
        except httpx.HTTPError:
            return False, f"No se pudo conectar con Ollama en {url}."
        return True, f"Ollama disponible en {url} (modelo {settings.ollama_modelo})."
    if nombre == "falso":
        return True, "Proveedor determinista de demostración (no usa un modelo de IA real)."
    return False, f"Proveedor de IA desconocido: '{settings.ai_provider}'."

"""Proveedor Claude (SDK oficial `anthropic`).

Salida estructurada con `output_config.format` (JSON Schema derivado del modelo Pydantic con
`anthropic.transform_schema`) y validación posterior con Pydantic. En Haiku 5.5 y Sonnet 5.5 no se
envían `temperature`/`top_p`/`budget_tokens` ni prefill. Esfuerzo con `output_config.effort`.
El bloque estable (instrucciones + laboratorio + rúbrica) lleva `cache_control` para el caché de prompts.
"""

import time

import anthropic
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.evaluacion.contrato import UsoModelo
from app.evaluacion.precios import costo_estimado
from app.evaluacion.proveedores.base import (
    Bloque,
    BloqueTexto,
    ErrorProveedor,
    ErrorSalidaInvalida,
    ProveedorIA,
)

MAX_TOKENS_SALIDA = 16_000
ESFUERZO = {"evaluacion": "low", "escalamiento": "medium", "informe": "low"}  # costo bajo; escalamiento piensa más
TIMEOUT_S = 180.0


def _a_contenido(bloque: Bloque) -> dict:
    if isinstance(bloque, BloqueTexto):
        return {"type": "text", "text": bloque.texto}
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": bloque.media_type, "data": bloque.datos_b64},
    }


class ClaudeProveedor(ProveedorIA):
    nombre = "claude"
    acepta_imagenes = True

    def __init__(self, settings: Settings, cliente: object | None = None):
        self.modelo_principal = settings.ia_modelo_principal
        self.modelo_escalamiento = settings.ia_modelo_escalamiento
        self._api_key = settings.anthropic_api_key
        self._cliente = cliente

    @property
    def cliente(self):
        if self._cliente is None:
            if not self._api_key:
                raise ErrorProveedor("Falta la variable de entorno ANTHROPIC_API_KEY.")
            self._cliente = anthropic.Anthropic(api_key=self._api_key, timeout=TIMEOUT_S)
        return self._cliente

    def construir_peticion(
        self,
        sistema: str,
        bloques_estables: list[Bloque],
        bloques_variables: list[Bloque],
        esquema: type[BaseModel],
        modelo: str,
        proposito: str,
    ) -> dict:
        """Arma los argumentos de `messages.create` (público para poder probarlo sin red)."""
        estables = [_a_contenido(b) for b in bloques_estables]
        if estables:
            estables[-1] = {**estables[-1], "cache_control": {"type": "ephemeral"}}
        contenido = [*estables, *[_a_contenido(b) for b in bloques_variables]]
        return {
            "model": modelo,
            "max_tokens": MAX_TOKENS_SALIDA,
            "system": [{"type": "text", "text": sistema}],
            "messages": [{"role": "user", "content": contenido}],
            "output_config": {
                "effort": ESFUERZO.get(proposito, "low"),
                "format": {"type": "json_schema", "schema": anthropic.transform_schema(esquema)},
            },
        }

    def generar_estructurado(self, sistema, bloques_estables, bloques_variables, esquema, modelo, proposito):
        peticion = self.construir_peticion(
            sistema, bloques_estables, bloques_variables, esquema, modelo, proposito
        )
        t0 = time.monotonic()
        try:
            r = self.cliente.messages.create(**peticion)
        except ErrorProveedor:
            raise
        except anthropic.AuthenticationError as e:
            raise ErrorProveedor("La clave de la API de Anthropic es inválida o fue revocada.") from e
        except anthropic.PermissionDeniedError as e:
            raise ErrorProveedor("La clave de Anthropic no tiene permiso para este modelo.") from e
        except anthropic.RateLimitError as e:
            raise ErrorProveedor("Anthropic limitó la tasa de solicitudes; intenta más tarde.") from e
        except anthropic.APITimeoutError as e:
            raise ErrorProveedor("La solicitud a Anthropic superó el tiempo de espera.") from e
        except anthropic.APIConnectionError as e:
            raise ErrorProveedor("No se pudo conectar con la API de Anthropic.") from e
        except anthropic.APIStatusError as e:
            raise ErrorProveedor(f"La API de Anthropic respondió con error {e.status_code}.") from e
        duracion = time.monotonic() - t0

        u = r.usage
        entrada = getattr(u, "input_tokens", 0) or 0
        salida = getattr(u, "output_tokens", 0) or 0
        lectura = getattr(u, "cache_read_input_tokens", 0) or 0
        escritura = getattr(u, "cache_creation_input_tokens", 0) or 0
        uso = UsoModelo(
            proveedor=self.nombre,
            modelo=modelo,
            proposito=proposito,
            tokens_entrada=entrada,
            tokens_salida=salida,
            tokens_cache_lectura=lectura,
            tokens_cache_escritura=escritura,
            costo_usd_estimado=costo_estimado(modelo, entrada, salida, lectura, escritura),
            duracion_s=round(duracion, 3),
        )

        # Revisar stop_reason ANTES de leer el contenido
        if r.stop_reason == "refusal":
            raise ErrorProveedor("El modelo se negó a responder (rechazo de seguridad).")
        texto = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "")
        if r.stop_reason == "max_tokens":
            raise ErrorSalidaInvalida(
                "La respuesta del modelo se cortó por el límite de tokens.", uso, texto
            )
        try:
            return esquema.model_validate_json(texto), uso
        except ValidationError as e:
            raise ErrorSalidaInvalida(
                f"La salida del modelo no cumple el esquema: {e.error_count()} errores. {e}", uso, texto
            ) from e

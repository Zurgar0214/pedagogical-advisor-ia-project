"""Proveedor local Ollama vía HTTP (`/api/chat` con `format` = JSON Schema). Costo 0."""

import time

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.evaluacion.contrato import UsoModelo
from app.evaluacion.proveedores.base import (
    Bloque,
    BloqueTexto,
    ErrorProveedor,
    ErrorSalidaInvalida,
    ProveedorIA,
)

TIMEOUT_S = 600.0
# Ollama usa por defecto un contexto pequeño y RECORTA el prompt sin avisar: se fija `num_ctx` (OLLAMA_NUM_CTX).


class OllamaProveedor(ProveedorIA):
    nombre = "ollama"
    acepta_imagenes = False

    def __init__(self, settings: Settings, cliente: httpx.Client | None = None):
        self.url = settings.ollama_url.rstrip("/")
        self.modelo_principal = settings.ollama_modelo
        self.modelo_escalamiento = settings.ollama_modelo
        self._cliente = cliente
        self.num_ctx = settings.ollama_num_ctx

    def _http(self) -> httpx.Client:
        if self._cliente is None:
            self._cliente = httpx.Client(timeout=TIMEOUT_S)
        return self._cliente

    @staticmethod
    def _texto(bloques: list[Bloque]) -> str:
        return "\n\n".join(b.texto for b in bloques if isinstance(b, BloqueTexto))

    def construir_peticion(
        self, sistema, bloques_estables, bloques_variables, esquema: type[BaseModel], modelo: str
    ) -> dict:
        return {
            "model": modelo,
            "stream": False,
            "messages": [
                {"role": "system", "content": sistema},
                {
                    "role": "user",
                    "content": self._texto(bloques_estables) + "\n\n" + self._texto(bloques_variables),
                },
            ],
            "format": esquema.model_json_schema(),
            "options": {"temperature": 0, "num_ctx": self.num_ctx},
        }

    def generar_estructurado(self, sistema, bloques_estables, bloques_variables, esquema, modelo, proposito):
        cuerpo = self.construir_peticion(sistema, bloques_estables, bloques_variables, esquema, modelo)
        t0 = time.monotonic()
        try:
            r = self._http().post(f"{self.url}/api/chat", json=cuerpo)
            r.raise_for_status()
            datos = r.json()
        except httpx.TimeoutException as e:
            raise ErrorProveedor("Ollama superó el tiempo de espera.") from e
        except httpx.HTTPStatusError as e:
            raise ErrorProveedor(f"Ollama respondió con error {e.response.status_code}.") from e
        except (httpx.HTTPError, ValueError) as e:
            raise ErrorProveedor(f"No se pudo conectar con Ollama en {self.url}.") from e
        uso = UsoModelo(
            proveedor=self.nombre,
            modelo=modelo,
            proposito=proposito,
            tokens_entrada=int(datos.get("prompt_eval_count") or 0),
            tokens_salida=int(datos.get("eval_count") or 0),
            costo_usd_estimado=0.0,
            duracion_s=round(time.monotonic() - t0, 3),
        )
        if uso.tokens_entrada >= self.num_ctx - 8:
            raise ErrorProveedor(
                f"El prompt ({uso.tokens_entrada} tokens) no cabe en el contexto de Ollama "
                f"(num_ctx={self.num_ctx}); sube OLLAMA_NUM_CTX o baja IA_MAX_CARACTERES_CONTEXTO."
            )
        texto = (datos.get("message") or {}).get("content") or ""
        try:
            return esquema.model_validate_json(texto), uso
        except ValidationError as e:
            raise ErrorSalidaInvalida(
                f"La salida de Ollama no cumple el esquema: {e}", uso, texto
            ) from e

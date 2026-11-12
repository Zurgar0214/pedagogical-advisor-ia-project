"""Interfaz común de los proveedores de IA (RNF-05). Solo aquí se toca un SDK o una API de modelo."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import BaseModel

from app.evaluacion.contrato import UsoModelo


@dataclass(frozen=True)
class BloqueTexto:
    texto: str


@dataclass(frozen=True)
class BloqueImagen:
    media_type: str
    datos_b64: str


Bloque = BloqueTexto | BloqueImagen


class ErrorProveedor(Exception):
    """Fallo del proveedor (clave inválida, red, rechazo del modelo...). Mensaje en español."""


class ErrorSalidaInvalida(ErrorProveedor):
    """El modelo respondió pero la salida no valida contra el esquema Pydantic (reintentable)."""

    def __init__(self, mensaje: str, uso: UsoModelo | None = None, crudo: str | None = None):
        super().__init__(mensaje)
        self.uso = uso
        self.crudo = crudo


class ProveedorIA(ABC):
    nombre: str
    acepta_imagenes: bool = False
    modelo_principal: str
    modelo_escalamiento: str

    @abstractmethod
    def generar_estructurado[T: BaseModel](
        self,
        sistema: str,
        bloques_estables: list[Bloque],
        bloques_variables: list[Bloque],
        esquema: type[T],
        modelo: str,
        proposito: str,
    ) -> tuple[T, UsoModelo]:
        """Devuelve (objeto validado con `esquema`, uso). Lanza ErrorProveedor/ErrorSalidaInvalida."""

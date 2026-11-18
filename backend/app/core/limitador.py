"""Límite de intentos de inicio de sesión fallidos, por correo (defensa contra fuerza bruta).

Se cuenta por correo y no por IP: en una sala de clase todos salen por la misma IP pública y
un límite por IP bloquearía al grupo entero. El estado vive en memoria del proceso (la API corre
con un solo proceso de uvicorn); un reinicio lo limpia, lo cual es aceptable para este riesgo.
"""

import threading
import time
from dataclasses import dataclass, field


@dataclass
class _Registro:
    fallos: list[float] = field(default_factory=list)
    bloqueado_hasta: float = 0.0


class LimitadorLogin:
    def __init__(self, reloj=time.monotonic) -> None:
        self._reloj = reloj
        self._registros: dict[str, _Registro] = {}
        self._candado = threading.Lock()

    def segundos_bloqueo(self, correo: str) -> int:
        """Segundos que faltan para desbloquear la cuenta (0 si no está bloqueada)."""
        with self._candado:
            r = self._registros.get(correo)
            if r is None:
                return 0
            restante = r.bloqueado_hasta - self._reloj()
            return int(restante) + 1 if restante > 0 else 0

    def registrar_fallo(
        self, correo: str, max_intentos: int, ventana_s: int, bloqueo_s: int
    ) -> None:
        ahora = self._reloj()
        with self._candado:
            r = self._registros.setdefault(correo, _Registro())
            r.fallos = [t for t in r.fallos if ahora - t < ventana_s]
            r.fallos.append(ahora)
            if len(r.fallos) >= max_intentos:
                r.bloqueado_hasta = ahora + bloqueo_s
                r.fallos.clear()
            # Evita crecimiento sin límite con correos inventados
            if len(self._registros) > 10_000:
                self._purgar(ahora, ventana_s)

    def registrar_exito(self, correo: str) -> None:
        with self._candado:
            self._registros.pop(correo, None)

    def reiniciar(self) -> None:
        with self._candado:
            self._registros.clear()

    def _purgar(self, ahora: float, ventana_s: int) -> None:
        for correo in list(self._registros):
            r = self._registros[correo]
            if r.bloqueado_hasta <= ahora and all(ahora - t >= ventana_s for t in r.fallos):
                del self._registros[correo]


limitador_login = LimitadorLogin()

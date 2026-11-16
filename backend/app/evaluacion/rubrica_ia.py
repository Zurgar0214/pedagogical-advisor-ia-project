"""Interpretación de rúbricas con IA (RF-04). Lo implementa `ia-evaluacion`.

Modelo principal con esfuerzo bajo, sin escalamiento. Validación de negocio con 1 reintento que envía
los errores. NO normaliza pesos: si no suman 100 el validador de rúbricas lo marca (regla de oro 6).
"""

from collections import Counter

from app.core.config import Settings
from app.evaluacion import prompts_rubrica as prompts
from app.evaluacion.contrato import ErrorEvaluacion, UsoModelo
from app.evaluacion.esquema_rubrica import RubricaPropuesta, a_rubrica
from app.evaluacion.proveedores import crear_proveedor, estado_de
from app.evaluacion.proveedores.base import ErrorProveedor, ErrorSalidaInvalida, ProveedorIA
from app.evaluacion.seguridad import detectar_inyeccion
from app.schemas.rubrica import Rubrica as RubricaContenido

VERSION_PROMPT = prompts.VERSION_PROMPT
PROPOSITO = "rubrica"
MAX_INTENTOS = 2  # 1 llamada + 1 reintento con los errores
MIN_NIVELES = 2


class ProveedorNoDisponible(ErrorEvaluacion):
    """El proveedor de IA no está configurado o no responde (el endpoint lo mapea a 503)."""


class ResultadoInterpretacion:
    def __init__(
        self,
        rubrica: RubricaContenido,
        observaciones: list[str],
        advertencias: list[str],
        uso: list[UsoModelo],
        proveedor: str,
        modelo: str,
        version_prompt: str,
    ):
        self.rubrica = rubrica
        self.observaciones = observaciones
        self.advertencias = advertencias
        self.uso = uso
        self.proveedor = proveedor
        self.modelo = modelo
        self.version_prompt = version_prompt


def _duplicados(valores: list[str]) -> list[str]:
    return [v for v, n in Counter(valores).items() if n > 1]


def _validar(r: RubricaPropuesta) -> list[str]:
    """Errores de negocio (no de pesos: eso lo reporta el validador de rúbricas)."""
    errores: list[str] = []
    if not r.criterios:
        errores.append("La rúbrica debe tener al menos 1 criterio.")
    for cid in _duplicados([c.id for c in r.competencias]):
        errores.append(f"Id de competencia duplicado: '{cid}'.")
    for cid in _duplicados([c.id for c in r.criterios]):
        errores.append(f"Id de criterio duplicado: '{cid}'.")
    competencias = {c.id for c in r.competencias}
    for k in r.criterios:
        if k.competencia_id not in competencias:
            errores.append(
                f"El criterio '{k.nombre}' referencia la competencia inexistente '{k.competencia_id}'."
            )
        if len(k.niveles) < MIN_NIVELES:
            errores.append(
                f"El criterio '{k.nombre}' debe tener al menos {MIN_NIVELES} niveles de desempeño."
            )
        for n in k.niveles:
            if n.valor < 0 or n.valor > 5:
                errores.append(
                    f"El nivel '{n.nombre}' del criterio '{k.nombre}' tiene valor {n.valor} "
                    "fuera de 0-5 (convierte linealmente la escala)."
                )
    return errores


def _interpretar_con(proveedor: ProveedorIA, texto: str) -> ResultadoInterpretacion:
    modelo = proveedor.modelo_principal
    estables = prompts.bloques_estables()
    variables = prompts.bloques_variables(texto)
    advertencias = detectar_inyeccion(texto, "el documento de la rúbrica")
    usos: list[UsoModelo] = []

    errores: list[str] = []
    previa: str | None = None
    final: RubricaPropuesta | None = None
    for intento in range(1, MAX_INTENTOS + 1):
        bloques = variables if intento == 1 else [*variables, *prompts.bloque_reintento(errores, previa)]
        try:
            salida, uso = proveedor.generar_estructurado(
                prompts.SISTEMA, estables, bloques, RubricaPropuesta, modelo, PROPOSITO
            )
        except ErrorSalidaInvalida as e:
            if e.uso is not None:
                usos.append(e.uso.model_copy(update={"intentos": intento}))
            errores = [str(e)[:1500]]
            previa = e.crudo
            continue
        except ErrorProveedor as e:
            raise ErrorEvaluacion(f"El modelo de IA falló al interpretar la rúbrica: {e}") from e
        usos.append(uso.model_copy(update={"intentos": intento}))
        errores = _validar(salida)
        if not errores:
            final = salida
            break
        previa = salida.model_dump_json()

    if final is None:
        raise ErrorEvaluacion(
            "La IA no produjo una rúbrica válida tras reintentar: " + " ".join(errores)[:800]
        )
    return ResultadoInterpretacion(
        a_rubrica(final),
        list(final.observaciones),
        advertencias,
        usos,
        proveedor.nombre,
        modelo,
        VERSION_PROMPT,
    )


def interpretar_rubrica(texto: str, settings: Settings) -> ResultadoInterpretacion:
    """Lanza `app.evaluacion.contrato.ErrorEvaluacion` con mensaje en español si no se puede."""
    disponible, motivo = estado_de(settings)
    if not disponible:
        raise ProveedorNoDisponible(f"El proveedor de IA no está disponible: {motivo}")
    try:
        proveedor = crear_proveedor(settings)
    except ErrorProveedor as e:
        raise ProveedorNoDisponible(str(e)) from e
    return _interpretar_con(proveedor, texto)

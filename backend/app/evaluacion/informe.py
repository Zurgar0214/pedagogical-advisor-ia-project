"""Síntesis con IA del informe integral y la taxonomía del mapa mental. Lo implementa `ia-evaluacion`.

Modelo principal con esfuerzo bajo, sin escalamiento. Validación de negocio con 1 reintento que envía
los errores; relaciones inválidas tras reintentar se descartan con advertencia.
"""

from app.core.config import Settings
from app.evaluacion import prompts_informe as prompts
from app.evaluacion.contrato import ErrorEvaluacion, UsoModelo
from app.evaluacion.proveedores import crear_proveedor, estado_de
from app.evaluacion.proveedores.base import ErrorProveedor, ErrorSalidaInvalida, ProveedorIA
from app.evaluacion.seguridad import detectar_inyeccion
from app.informes.contrato import CATEGORIAS_IA, AgregadoInforme, SintesisInforme

VERSION_PROMPT = prompts.VERSION_PROMPT
PROPOSITO = "informe"
MAX_INTENTOS = 2  # 1 llamada + 1 reintento con los errores


class ResultadoSintesis:
    """Contenedor del resultado: síntesis validada, uso por llamada, advertencias y versión de prompt."""

    def __init__(
        self,
        sintesis: SintesisInforme,
        uso: list[UsoModelo],
        advertencias: list[str],
        proveedor: str,
        modelo: str,
        version_prompt: str,
    ):
        self.sintesis = sintesis
        self.uso = uso
        self.advertencias = advertencias
        self.proveedor = proveedor
        self.modelo = modelo
        self.version_prompt = version_prompt


def _norm(texto: str) -> str:
    return " ".join(texto.lower().split())


# ---------- Validación de negocio ----------


def _validar(
    s: SintesisInforme, agregado: AgregadoInforme
) -> tuple[list[str], list[str], SintesisInforme]:
    """(errores esenciales, errores de relaciones, síntesis con relaciones válidas y temas canónicos)."""
    canon = {_norm(t.tema): t.tema for t in agregado.temas}
    esenciales: list[str] = []

    vistos: set[str] = set()
    clasif = []
    for c in s.clasificacion:
        clave = _norm(c.tema)
        if clave not in canon:
            esenciales.append(f"La clasificación incluye un tema que no existe en el agregado: '{c.tema}'.")
            continue
        if clave in vistos:
            esenciales.append(f"El tema '{canon[clave]}' está clasificado más de una vez.")
            continue
        vistos.add(clave)
        if c.categoria not in CATEGORIAS_IA:
            esenciales.append(
                f"Categoría inválida '{c.categoria}' para el tema '{canon[clave]}'; "
                f"usa exactamente una de: {'; '.join(CATEGORIAS_IA)}."
            )
        clasif.append(c.model_copy(update={"tema": canon[clave]}))
    faltan = [t for k, t in canon.items() if k not in vistos]
    if faltan:
        esenciales.append("Faltan temas por clasificar: " + ", ".join(faltan) + ".")

    err_rel: list[str] = []
    rel_ok = []
    pares: set[tuple[str, str, str]] = set()
    for r in s.relaciones:
        o, d = _norm(r.origen), _norm(r.destino)
        if o not in canon or d not in canon:
            err_rel.append(
                f"Relación con tema inexistente: '{r.origen}' -> '{r.destino}' (usa solo temas del agregado)."
            )
        elif o == d:
            err_rel.append(f"Relación de un tema consigo mismo: '{r.origen}'.")
        elif (o, d, r.tipo) in pares:
            err_rel.append(f"Relación duplicada: '{r.origen}' -> '{r.destino}' ({r.tipo}).")
        else:
            pares.add((o, d, r.tipo))
            rel_ok.append(r.model_copy(update={"origen": canon[o], "destino": canon[d]}))

    valida = s.model_copy(update={"clasificacion": clasif, "relaciones": rel_ok})
    return esenciales, err_rel, valida


def _plan_cubre_brecha(s: SintesisInforme, agregado: AgregadoInforme) -> bool:
    brechas = {_norm(b.nombre) for b in agregado.brechas if b.nombre.strip()}
    for a in s.plan:
        t = _norm(a.tema)
        if any(t == b or t in b or b in t for b in brechas):
            return True
    return False


def _advertencias_inyeccion(agregado: AgregadoInforme) -> list[str]:
    """Busca intentos de inyección en los textos de estudiante/evaluaciones que viajan al modelo."""
    avisos: list[str] = []
    for t in agregado.temas:
        textos = [t.tema, *t.que_fortalecer]
        for a in t.aprendizajes:
            textos.extend([a.que_aprendio, a.como_aplico])
        avisos.extend(detectar_inyeccion("\n".join(textos), f"el tema '{t.tema}'"))
    for lab in agregado.laboratorios:
        textos = [lab.titulo, *lab.fortalezas, *lab.debilidades, *lab.recomendaciones]
        avisos.extend(detectar_inyeccion("\n".join(textos), f"el laboratorio {lab.codigo}"))
    return avisos


# ---------- Orquestación ----------


def _sintetizar_con(
    proveedor: ProveedorIA, agregado: AgregadoInforme, settings: Settings
) -> ResultadoSintesis:
    modelo = proveedor.modelo_principal
    estables = prompts.bloques_estables()
    variables = prompts.bloques_variables(agregado)
    usos: list[UsoModelo] = []
    advertencias = _advertencias_inyeccion(agregado)

    errores: list[str] = []
    previa: str | None = None
    final: SintesisInforme | None = None
    for intento in range(1, MAX_INTENTOS + 1):
        bloques = variables if intento == 1 else [*variables, *prompts.bloque_reintento(errores, previa)]
        try:
            salida, uso = proveedor.generar_estructurado(
                prompts.SISTEMA, estables, bloques, SintesisInforme, modelo, PROPOSITO
            )
        except ErrorSalidaInvalida as e:
            if e.uso is not None:
                usos.append(e.uso.model_copy(update={"intentos": intento}))
            errores = [str(e)[:1500]]
            previa = e.crudo
            continue
        except ErrorProveedor as e:
            raise ErrorEvaluacion(f"El modelo de IA falló al sintetizar el informe: {e}") from e
        usos.append(uso.model_copy(update={"intentos": intento}))
        esenciales, err_rel, valida = _validar(salida, agregado)
        if not esenciales and (not err_rel or intento == MAX_INTENTOS):
            if err_rel:
                advertencias.append(
                    "Se descartaron relaciones entre temas inválidas tras reintentar: "
                    + " ".join(err_rel)[:600]
                )
            final = valida
            break
        errores = [*esenciales, *err_rel]
        previa = salida.model_dump_json()

    if final is None:
        raise ErrorEvaluacion(
            "La IA no produjo una síntesis válida del informe tras reintentar: " + " ".join(errores)[:800]
        )
    if agregado.brechas and not _plan_cubre_brecha(final, agregado):
        advertencias.append(
            "El plan de fortalecimiento no menciona ninguna de las brechas detectadas; revísalo."
        )
    return ResultadoSintesis(final, usos, advertencias, proveedor.nombre, modelo, VERSION_PROMPT)


def sintetizar(agregado: AgregadoInforme, settings: Settings) -> ResultadoSintesis:
    """Lanza `app.evaluacion.contrato.ErrorEvaluacion` con mensaje en español si no se puede."""
    disponible, motivo = estado_de(settings)
    if not disponible:
        raise ErrorEvaluacion(f"El proveedor de IA no está disponible: {motivo}")
    try:
        proveedor = crear_proveedor(settings)
    except ErrorProveedor as e:
        raise ErrorEvaluacion(str(e)) from e
    return _sintetizar_con(proveedor, agregado, settings)

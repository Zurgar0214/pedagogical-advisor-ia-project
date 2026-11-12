"""Punto de entrada del pipeline de evaluación (RF-06, RNF-02, RNF-03, RNF-05).

contexto -> verificación técnica -> evaluación (modelo principal) -> reglas de negocio (1 reintento)
-> escalamiento de los criterios dudosos (modelo de escalamiento) -> resultado trazable.
El LLM nunca calcula la nota: solo elige niveles.
"""

from app.core.config import Settings
from app.evaluacion import prompts
from app.evaluacion.contexto import ContextoPreparado, preparar_contexto
from app.evaluacion.contrato import (
    ContextoEvaluacion,
    ErrorEvaluacion,
    EvaluacionCriterio,
    EvidenciaCitada,
    ResultadoEvaluacion,
    ResultadoIA,
    UsoModelo,
    VerificacionTecnica,
)
from app.evaluacion.esquemas import CriterioSalida, SalidaCriterios, SalidaEvaluacion
from app.evaluacion.proveedores import crear_proveedor, estado_de
from app.evaluacion.proveedores.base import (
    ErrorProveedor,
    ErrorSalidaInvalida,
    ProveedorIA,
)
from app.evaluacion.reglas import MAX_FRAGMENTO, validar_criterios
from app.evaluacion.seguridad import detectar_inyeccion
from app.evaluacion.verificacion import verificar
from app.schemas.rubrica import Criterio, Rubrica

VERSION_PROMPT = prompts.VERSION_PROMPT
MAX_INTENTOS = 2  # 1 llamada + 1 reintento con los errores


class _ValidacionFallida(Exception):
    def __init__(self, errores: list[str]):
        super().__init__("; ".join(errores))
        self.errores = errores


def estado_proveedor(settings: Settings) -> tuple[bool, str]:
    """(disponible, motivo en español). No hace llamadas de pago; solo revisa configuración."""
    return estado_de(settings)


def evaluar(contexto: ContextoEvaluacion, settings: Settings) -> ResultadoEvaluacion:
    """Evalúa una entrega. Ver reglas en `app.evaluacion.contrato`."""
    disponible, motivo = estado_proveedor(settings)
    if not disponible:
        raise ErrorEvaluacion(f"El proveedor de IA no está disponible: {motivo}")
    try:
        proveedor = crear_proveedor(settings)
    except ErrorProveedor as e:
        raise ErrorEvaluacion(str(e)) from e
    return ejecutar_pipeline(contexto, settings, proveedor)


# ---------- Llamada con reintento ----------


def _llamar(
    proveedor: ProveedorIA,
    modelo: str,
    proposito: str,
    esquema: type[SalidaCriterios],
    estables,
    variables,
    validar,
    usos: list[UsoModelo],
) -> tuple[SalidaCriterios, list[str]]:
    """Llama al modelo; si la salida no valida, reintenta UNA vez enviándole los errores."""
    errores: list[str] = []
    previa: str | None = None
    for intento in range(1, MAX_INTENTOS + 1):
        bloques = variables if intento == 1 else [*variables, *prompts.bloque_reintento(errores, previa)]
        try:
            salida, uso = proveedor.generar_estructurado(
                prompts.SISTEMA, estables, bloques, esquema, modelo, proposito
            )
        except ErrorSalidaInvalida as e:
            if e.uso is not None:
                usos.append(e.uso.model_copy(update={"intentos": intento}))
            errores = [str(e)[:1500]]
            previa = e.crudo
            continue
        usos.append(uso.model_copy(update={"intentos": intento}))
        errores, avisos = validar(salida)
        if not errores:
            return salida, avisos
        previa = salida.model_dump_json()
    raise _ValidacionFallida(errores)


# ---------- Escalamiento ----------


def _valor_maximo(c: Criterio) -> float:
    return max((n.valor for n in c.niveles), default=0.0)


def _nivel_alto(c: Criterio, nivel: str) -> bool:
    valores = {n.nombre: n.valor for n in c.niveles}
    maximo = _valor_maximo(c)
    return maximo > 0 and valores.get(nivel, 0.0) >= 0.75 * maximo


def _criterios_a_escalar(
    elegidos: dict[str, CriterioSalida], rubrica: Rubrica, ver: VerificacionTecnica, umbral: float
) -> dict[str, str]:
    motivos: dict[str, str] = {}
    for crit in rubrica.criterios:
        c = elegidos[crit.id]
        partes = []
        if c.confianza < umbral:
            partes.append(f"confianza baja ({c.confianza:.2f} < {umbral:.2f})")
        if not c.evidencias:
            partes.append("sin evidencias citadas")
        if ver.errores_sintaxis and _nivel_alto(crit, c.nivel):
            partes.append(
                f"nivel alto ('{c.nivel}') pese a {len(ver.errores_sintaxis)} errores de sintaxis"
            )
        if partes:
            motivos[crit.id] = "; ".join(partes)
    return motivos


# ---------- Pipeline ----------


def _completar_evidencias(c: CriterioSalida, preparado: ContextoPreparado) -> list[EvidenciaCitada]:
    ids = {f.fuente: f.evidencia_id for f in preparado.fuentes}
    ids.update({i.fuente: i.evidencia_id for i in preparado.imagenes})
    return [
        EvidenciaCitada(
            evidencia_id=e.evidencia_id if e.evidencia_id is not None else ids.get(e.fuente),
            fuente=e.fuente,
            ubicacion=e.ubicacion,
            fragmento=e.fragmento[:MAX_FRAGMENTO],
        )
        for e in c.evidencias
    ]


def _a_criterio(c: CriterioSalida, modelo: str, escalado: bool, prep: ContextoPreparado):
    datos = c.model_dump(exclude={"evidencias"})
    return EvaluacionCriterio(
        **datos, evidencias=_completar_evidencias(c, prep), modelo=modelo, escalado=escalado
    )


def ejecutar_pipeline(
    contexto: ContextoEvaluacion, settings: Settings, proveedor: ProveedorIA
) -> ResultadoEvaluacion:
    rubrica = contexto.rubrica
    ids = [c.id for c in rubrica.criterios]
    if not ids or any(not c.niveles for c in rubrica.criterios):
        raise ErrorEvaluacion("La rúbrica no tiene criterios con niveles; no se puede evaluar.")

    preparado = preparar_contexto(contexto, settings, proveedor.acepta_imagenes)
    if not preparado.hay_evidencias:
        raise ErrorEvaluacion(
            "La entrega no tiene evidencias analizables (informe con texto, código o imágenes)."
        )
    verificacion = verificar(preparado)

    estables = prompts.bloques_estables(contexto)
    usos: list[UsoModelo] = []
    advertencias = [*preparado.advertencias, *verificacion.notas]
    modelo_principal = proveedor.modelo_principal

    # 1) Evaluación con el modelo principal
    try:
        salida, avisos = _llamar(
            proveedor,
            modelo_principal,
            "evaluacion",
            SalidaEvaluacion,
            estables,
            prompts.bloques_variables_evaluacion(preparado, verificacion),
            lambda s: validar_criterios(s.criterios, rubrica, ids, preparado),
            usos,
        )
    except ErrorProveedor as e:
        raise ErrorEvaluacion(f"El modelo de IA falló: {e}") from e
    except _ValidacionFallida as e:
        raise ErrorEvaluacion(
            "La IA no produjo una evaluación válida tras reintentar: " + " ".join(e.errores)[:800]
        ) from e
    assert isinstance(salida, SalidaEvaluacion)
    advertencias.extend(avisos)
    elegidos = {c.criterio_id: c for c in salida.criterios}
    modelos = {i: modelo_principal for i in ids}
    inyeccion = list(salida.advertencias_inyeccion)

    # 2) Escalamiento solo de los criterios dudosos
    escalados: list[str] = []
    escalamiento_fallido = False
    motivos = _criterios_a_escalar(elegidos, rubrica, verificacion, settings.ia_umbral_confianza)
    if motivos:
        modelo_esc = proveedor.modelo_escalamiento
        previos = [_a_criterio(elegidos[i], modelo_principal, False, preparado) for i in motivos]
        try:
            salida_esc, avisos_esc = _llamar(
                proveedor,
                modelo_esc,
                "escalamiento",
                SalidaCriterios,
                estables,
                prompts.bloques_variables_escalamiento(preparado, verificacion, motivos, previos),
                lambda s: validar_criterios(s.criterios, rubrica, list(motivos), preparado),
                usos,
            )
        except (ErrorProveedor, _ValidacionFallida) as e:
            escalamiento_fallido = True
            advertencias.append(
                "El escalamiento a un modelo superior falló "
                f"({', '.join(motivos)}); se conserva la evaluación inicial. Detalle: {e}"[:600]
            )
        else:
            advertencias.extend(avisos_esc)
            inyeccion.extend(salida_esc.advertencias_inyeccion)
            for c in salida_esc.criterios:
                elegidos[c.criterio_id] = c
                modelos[c.criterio_id] = modelo_esc
                escalados.append(c.criterio_id)

    # 3) Ensamblado en el orden de la rúbrica
    criterios = [
        _a_criterio(elegidos[i], modelos[i], i in escalados, preparado) for i in ids
    ]
    resultado = ResultadoIA(
        criterios=criterios,
        resumen=salida.resumen,
        fortalezas=salida.fortalezas,
        debilidades=salida.debilidades,
        recomendaciones=salida.recomendaciones,
        aprendizajes=salida.aprendizajes,
    )

    # 4) Seguridad y revisión humana
    detectadas: list[str] = []
    for f in preparado.fuentes:
        detectadas.extend(detectar_inyeccion(f.texto_original, f.fuente))
    reportadas = [f"El modelo reportó una posible inyección de prompts: {t}" for t in inyeccion if t]
    hay_inyeccion = bool(detectadas or reportadas)
    advertencias.extend(detectadas)
    advertencias.extend(r for r in reportadas if r not in advertencias)

    sin_evidencia = [c.criterio_id for c in criterios if not c.evidencias]
    if sin_evidencia:
        advertencias.append(
            "Criterios sin evidencias citadas (requieren revisión docente): " + ", ".join(sin_evidencia)
        )
    baja_confianza = [
        c.criterio_id for c in criterios if c.confianza < settings.ia_umbral_confianza
    ]
    if baja_confianza:
        advertencias.append(
            "Criterios con confianza baja tras el escalamiento: " + ", ".join(baja_confianza)
        )

    return ResultadoEvaluacion(
        resultado=resultado,
        verificacion=verificacion,
        niveles_elegidos={c.criterio_id: c.nivel for c in criterios},
        uso=usos,
        proveedor=proveedor.nombre,
        modelo_principal=modelo_principal,
        criterios_escalados=escalados,
        requiere_revision=bool(escalamiento_fallido or hay_inyeccion or sin_evidencia),
        advertencias=advertencias,
        version_prompt=VERSION_PROMPT,
    )


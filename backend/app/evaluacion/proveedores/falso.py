"""Proveedor determinista sin red: para pruebas y demos sin clave de API.

Lee las etiquetas que arma `prompts.py` (rúbrica, temas, evidencias, verificación) y decide niveles
con señales simples: hay informe, hay código, hay errores de sintaxis. Cita fragmentos reales.
"""

import json
import re

from app.core.config import Settings
from app.evaluacion.contrato import UsoModelo
from app.evaluacion.proveedores.base import BloqueTexto, ProveedorIA
from app.informes.contrato import AgregadoInforme, SintesisInforme

MODELO_FALSO = "falso-determinista-v1"
CONFIANZA = 0.75
CONFIANZA_SIN_EVIDENCIA = 0.4
_PREFIJO_LINEA = re.compile(r"^\s*(\d+)\| ?(.*)$")


def _json_tag(tag: str, texto: str, defecto):
    m = re.search(rf"<{tag}>\n(.*?)\n</{tag}>", texto, re.DOTALL)
    if not m:
        return defecto
    try:
        return json.loads(m.group(1))
    except ValueError:
        return defecto


def _primera_linea_con_texto(cuerpo: str) -> tuple[int, str] | None:
    for i, ln in enumerate(cuerpo.split("\n"), start=1):
        m = _PREFIJO_LINEA.match(ln)
        numero, contenido = (int(m.group(1)), m.group(2)) if m else (i, ln)
        if contenido.strip() and not contenido.startswith("### ["):
            return numero, contenido.strip()[:200]
    return None


# El orden resuelve empates: lo más específico primero.
_PALABRAS_CATEGORIA: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Ética y responsabilidad en IA", ("ética", "etica", "sesgo", "equidad", "privacidad", "responsab")),
    ("IA generativa y modelos de lenguaje", ("generativ", "llm", "prompt", "gpt", "difusión", "difusion")),
    ("Procesamiento de lenguaje natural", ("lenguaje natural", "nlp", "texto", "token", "embedding")),
    ("Visión por computador", ("visión", "vision", "imagen", "imágenes")),
    ("Aprendizaje por refuerzo", ("refuerzo", "q-learning", "agente", "recompensa")),
    (
        "Redes neuronales y aprendizaje profundo",
        ("neuronal", "profundo", "deep", "perceptr", "cnn", "rnn", "transformer"),
    ),
    (
        "Aprendizaje no supervisado",
        ("no supervisado", "cluster", "agrupa", "k-means", "kmeans", "pca", "dimensionalidad"),
    ),
    (
        "Aprendizaje supervisado",
        ("regresi", "clasificaci", "supervisado", "árbol", "arbol", "svm", "knn", "logística"),
    ),
    (
        "Datos y evaluación de modelos",
        ("evaluación", "evaluacion", "métrica", "metrica", "validación", "validacion", "sobreajuste", "datos"),
    ),
    ("Búsqueda y optimización", ("búsqueda", "busqueda", "optimiz", "gradiente", "heurística", "genétic")),
    ("Fundamentos de IA", ("fundamentos", "introducción", "introduccion", "historia", "lógica")),
)
MAX_PASOS_PLAN_FALSO = 5


def categoria_por_palabras(tema: str) -> str:
    t = tema.lower()
    for categoria, palabras in _PALABRAS_CATEGORIA:
        if any(p in t for p in palabras):
            return categoria
    return "Otros"


class FalsoProveedor(ProveedorIA):
    nombre = "falso"
    acepta_imagenes = False

    def __init__(self, settings: Settings | None = None):
        self.modelo_principal = MODELO_FALSO
        self.modelo_escalamiento = MODELO_FALSO

    def _sintesis(self, texto: str, modelo: str, proposito: str):
        agregado = AgregadoInforme.model_validate(_json_tag("datos_informe", texto, {}))
        temas = [t.tema for t in agregado.temas]
        clasif = [{"tema": t, "categoria": categoria_por_palabras(t)} for t in temas]
        por_cat: dict[str, list[str]] = {}
        for c in clasif:
            por_cat.setdefault(c["categoria"], []).append(c["tema"])
        relaciones = [
            {
                "origen": a,
                "destino": b,
                "tipo": "complementa",
                "explicacion": f"[Demostración] Ambos temas pertenecen a la categoría '{cat}'.",
            }
            for cat, ts in por_cat.items()
            for a, b in zip(ts, ts[1:], strict=False)
        ][:30]
        plan = [
            {
                "prioridad": min(i + 1, 5),
                "tema": b.nombre,
                "objetivo": f"[Demostración] Cerrar la brecha en '{b.nombre}'.",
                "actividades": [f"[Demostración] Repasar y practicar '{b.nombre}': {b.detalle}"[:300]],
                "recursos": ["[Demostración] Material del curso"],
                "indicador_logro": "[Demostración] Superar 3,5 en la próxima evaluación del tema.",
                "plazo_semanas": 2 + i,
            }
            for i, b in enumerate(agregado.brechas[:MAX_PASOS_PLAN_FALSO])
        ]
        if not plan:
            plan.append(
                {
                    "prioridad": 1,
                    "tema": temas[0] if temas else "Consolidación general",
                    "objetivo": "[Demostración] Consolidar lo aprendido sin brechas detectadas.",
                    "actividades": ["[Demostración] Resolver un ejercicio integrador del curso."],
                    "recursos": [],
                    "indicador_logro": "[Demostración] Mantener el nivel actual.",
                    "plazo_semanas": 4,
                }
            )
        tendencia = f"{agregado.tendencia:+.1f}" if agregado.tendencia is not None else "no disponible"
        cohortes = "; ".join(f"cohorte {k}: {v:.2f}" for k, v in sorted(agregado.promedio_cohorte.items()))
        datos = {
            "resumen": (
                f"[Demostración, no es análisis de IA real] {agregado.estudiante}: promedio general "
                f"{agregado.promedio_general:.1f} (nivel {agregado.nivel_general}) con "
                f"{len(agregado.laboratorios)} de {agregado.laboratorios_totales} laboratorios evaluados."
            ),
            "evolucion": (
                f"[Demostración, no es análisis de IA real] Promedios por cohorte: "
                f"{cohortes or 'sin datos'}; tendencia: {tendencia}."
            ),
            "plan": plan,
            "clasificacion": clasif,
            "relaciones": relaciones,
        }
        salida = SintesisInforme.model_validate(datos)
        uso = UsoModelo(
            proveedor=self.nombre,
            modelo=modelo,
            proposito=proposito,
            tokens_entrada=len(texto) // 4,
            tokens_salida=len(json.dumps(datos, ensure_ascii=False)) // 4,
        )
        return salida, uso

    def generar_estructurado(self, sistema, bloques_estables, bloques_variables, esquema, modelo, proposito):
        texto = "\n\n".join(
            b.texto for b in [*bloques_estables, *bloques_variables] if isinstance(b, BloqueTexto)
        )
        if esquema is SintesisInforme:
            return self._sintesis(texto, modelo, proposito)
        rubrica = _json_tag("rubrica", texto, {"criterios": []})["criterios"]
        temas = _json_tag("temas", texto, [])
        verificacion = _json_tag("verificacion_tecnica", texto, {})
        reevaluar = _json_tag("criterios_a_reevaluar", texto, None)
        evidencias = re.findall(
            r'<evidencia_estudiante fuente="([^"]+)"[^>]*>\n(.*?)\n</evidencia_estudiante>',
            texto,
            re.DOTALL,
        )
        informe = next(((f, c) for f, c in evidencias if f.startswith(("informe_pdf", "presentacion"))), None)
        codigo = next(((f, c) for f, c in evidencias if f.startswith("codigo:")), None)
        errores_sintaxis = len(verificacion.get("errores_sintaxis", []))

        if not evidencias:
            fraccion = 0.0
        elif informe and codigo:
            fraccion = 0.75
        else:
            fraccion = 0.5
        if errores_sintaxis:
            fraccion = max(0.0, fraccion - 0.4)

        citas = []
        if informe:
            linea = _primera_linea_con_texto(informe[1])
            if linea:
                citas.append(
                    {"fuente": informe[0], "ubicacion": "inicio del texto", "fragmento": linea[1]}
                )
        if codigo:
            linea = _primera_linea_con_texto(codigo[1])
            if linea:
                citas.append(
                    {
                        "fuente": codigo[0],
                        "ubicacion": f"línea {linea[0]}",
                        "fragmento": linea[1],
                    }
                )

        criterios = []
        for c in rubrica:
            if reevaluar is not None and c["criterio_id"] not in reevaluar:
                continue
            niveles = c["niveles_de_menor_a_mayor"]
            idx = round(fraccion * (len(niveles) - 1))
            nivel = niveles[idx]["nombre"]
            criterios.append(
                {
                    "criterio_id": c["criterio_id"],
                    "nivel": nivel,
                    "confianza": CONFIANZA if citas else CONFIANZA_SIN_EVIDENCIA,
                    "justificacion": (
                        f"Evaluación determinista de demostración: nivel '{nivel}' según la "
                        f"presencia de evidencias ({len(citas)} fuentes citadas) y "
                        f"{errores_sintaxis} errores de sintaxis."
                    ),
                    "evidencias": citas,
                    "fortalezas": ["Entrega con evidencias analizables."] if citas else [],
                    "debilidades": (
                        ["Hay errores de sintaxis en el código."] if errores_sintaxis else []
                    ),
                    "recomendaciones": ["Revisar y ampliar la evidencia de este criterio."],
                }
            )
        nivel_dominio = (
            "inicial" if fraccion < 0.25 else "basico" if fraccion < 0.5 else
            "competente" if fraccion < 0.75 else "avanzado"
        )  # fmt: skip
        datos = {
            "criterios": criterios,
            "advertencias_inyeccion": [],
            "resumen": "Resultado de demostración generado por el proveedor determinista.",
            "fortalezas": ["Entrega recibida con evidencias."] if citas else [],
            "debilidades": ["Errores de sintaxis detectados."] if errores_sintaxis else [],
            "recomendaciones": ["Usar un proveedor de IA real para una evaluación pedagógica."],
            "aprendizajes": [
                {
                    "tema": t,
                    "que_aprendio": "Se evidencia un acercamiento al tema.",
                    "como_aplico": "Aplicación inferida de forma determinista.",
                    "que_fortalecer": "Profundizar con ejemplos propios.",
                    "nivel_dominio": nivel_dominio,
                    "criterios_relacionados": [c["criterio_id"] for c in rubrica],
                }
                for t in temas
            ],
        }
        salida = esquema.model_validate({k: v for k, v in datos.items() if k in esquema.model_fields})
        uso = UsoModelo(
            proveedor=self.nombre,
            modelo=modelo,
            proposito=proposito,
            tokens_entrada=len(texto) // 4,
            tokens_salida=len(json.dumps(datos, ensure_ascii=False)) // 4,
        )
        return salida, uso


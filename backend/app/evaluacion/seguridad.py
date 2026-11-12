"""Defensa contra inyección de prompts: el contenido del estudiante es DATOS, nunca instrucciones."""

import re

ETIQUETA = "evidencia_estudiante"

_PATRONES = [
    r"ignor[ae]\w*\s+(?:\w+\s+){0,2}(?:instrucciones|indicaciones|reglas)",
    r"ignore\s+(?:\w+\s+){0,2}(?:instructions|prompts?|rules)",
    r"olvida\s+(?:todo|las\s+instrucciones)",
    r"disregard\s+(?:\w+\s+){0,2}instructions",
    r"(?:system|developer)\s*prompt",
    r"prompt\s+del\s+sistema",
    r"(?:asigna|otorga|pon|dame|da)\w*\s+(?:\w+\s+){0,3}(?:nota|calificaci[oó]n|nivel)\s+"
    r"(?:m[aá]xim\w*|m[aá]s\s+alto|5(?:[.,]0)?\b|sobresaliente|excelente)",
    r"nota\s+(?:final\s+)?(?:debe\s+ser|es|=)\s*5",
    r"eres\s+ahora\s+(?:un|una|el)",
    r"you\s+are\s+now\s+(?:a|an|the)",
    r"(?:give|assign|grade)\s+(?:this\s+)?(?:\w+\s+){0,2}(?:highest|maximum|full|top)\s+(?:score|grade|level|marks)",
    r"instrucciones\s+(?:para|dirigidas?\s+a)\s+(?:la\s+)?(?:ia|inteligencia\s+artificial|evaluador)",
    r"</?\s*(?:system|instrucciones|evidencia_estudiante|rubrica|laboratorio)\s*>",
]
_REGEX = [re.compile(p, re.IGNORECASE) for p in _PATRONES]


def neutralizar(texto: str) -> str:
    """Impide que el estudiante cierre o abra las etiquetas de delimitación."""
    return re.sub(rf"<(/?)\s*({ETIQUETA})", r"&lt;\1\2", texto, flags=re.IGNORECASE)


def detectar_inyeccion(texto: str, fuente: str, maximo: int = 3) -> list[str]:
    """Devuelve advertencias en español por cada patrón sospechoso encontrado en `texto`."""
    hallazgos: list[str] = []
    for rx in _REGEX:
        m = rx.search(texto)
        if m:
            fragmento = " ".join(m.group(0).split())[:120]
            hallazgos.append(
                f"Posible inyección de prompts en {fuente}: el contenido incluye "
                f"«{fragmento}». Se trató como dato y no se obedeció."
            )
            if len(hallazgos) >= maximo:
                break
    return hallazgos

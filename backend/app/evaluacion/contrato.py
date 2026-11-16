"""Contrato interno entre el pipeline de IA (`app.evaluacion`) y la API (`app.api`).

Lo define el orquestador. Ni el agente de IA ni el de backend lo cambian sin escalar.

Flujo:
    API arma `ContextoEvaluacion` desde la BD
      -> `app.evaluacion.servicio.evaluar(contexto, settings)` devuelve `ResultadoEvaluacion`
      -> API calcula la nota con `app.services.calculo_nota.calcular_nota(rubrica, resultado.niveles_elegidos)`
         (la nota NUNCA la calcula el LLM) y persiste todo para trazabilidad.

Reglas:
- `evaluar` no toca la base de datos ni la red salvo para llamar al proveedor de IA.
- `evaluar` no ejecuta código del estudiante por sí mismo: las pruebas corren solo en el servicio sandbox (contenedor aislado).
- `niveles_elegidos` contiene TODOS los criterios de la rúbrica y solo nombres de nivel existentes.
- Si el modelo falla tras los reintentos, `evaluar` lanza `ErrorEvaluacion` con un mensaje en español.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.rubrica import Rubrica

# ---------- Entrada ----------


class LaboratorioContexto(BaseModel):
    codigo: str
    titulo: str
    descripcion: str = ""
    objetivos: str = ""
    temas: list[str] = Field(default_factory=list)


class EvidenciaContexto(BaseModel):
    id: int
    tipo: str  # TipoEvidencia
    nombre_original: str | None = None
    ruta_archivo: str | None = None  # ruta ABSOLUTA en disco, o None (repo_github)
    url: str | None = None
    texto_extraido: str | None = None  # informe PDF ya extraído en la carga


class ContextoEvaluacion(BaseModel):
    laboratorio: LaboratorioContexto
    rubrica: Rubrica
    evidencias: list[EvidenciaContexto]


# ---------- Salida ----------


class EvidenciaCitada(BaseModel):
    evidencia_id: int | None = None
    fuente: str = Field(description="p. ej. 'informe_pdf' o 'codigo:src/modelo.py'")
    ubicacion: str = Field(default="", description="p. ej. 'página 3' o 'líneas 10-25'")
    fragmento: str = Field(default="", description="Cita breve y literal (máx. ~300 caracteres)")


class EvaluacionCriterio(BaseModel):
    criterio_id: str
    nivel: str = Field(description="Nombre EXACTO de un nivel del criterio")
    confianza: float = Field(ge=0, le=1)
    justificacion: str
    evidencias: list[EvidenciaCitada] = Field(default_factory=list)
    fortalezas: list[str] = Field(default_factory=list)
    debilidades: list[str] = Field(default_factory=list)
    recomendaciones: list[str] = Field(default_factory=list)
    modelo: str = ""  # lo rellena el pipeline, no el LLM
    escalado: bool = False  # lo rellena el pipeline


NivelDominio = Literal["inicial", "basico", "competente", "avanzado"]


class Aprendizaje(BaseModel):
    """Insumo para el informe integral (RF-09) y el mapa mental (RF-10)."""

    tema: str
    que_aprendio: str
    como_aplico: str
    que_fortalecer: str
    nivel_dominio: NivelDominio
    criterios_relacionados: list[str] = Field(default_factory=list)


class ResultadoIA(BaseModel):
    criterios: list[EvaluacionCriterio]
    resumen: str
    fortalezas: list[str] = Field(default_factory=list)
    debilidades: list[str] = Field(default_factory=list)
    recomendaciones: list[str] = Field(default_factory=list)
    aprendizajes: list[Aprendizaje] = Field(default_factory=list)


class HallazgoCodigo(BaseModel):
    archivo: str
    linea: int | None = None
    regla: str = ""  # p. ej. 'sintaxis', 'F401'
    mensaje: str


class ResultadoPruebas(BaseModel):
    ejecutadas: bool = False
    motivo: str = ""  # por qué no se ejecutaron
    total: int = 0
    exitosas: int = 0
    fallidas: int = 0
    salida: str = ""
    errores: int = 0
    omitidas: int = 0
    tiempo_agotado: bool = False


class VerificacionTecnica(BaseModel):
    archivos_analizados: int = 0
    archivos_por_lenguaje: dict[str, int] = Field(default_factory=dict)
    errores_sintaxis: list[HallazgoCodigo] = Field(default_factory=list)
    hallazgos_estaticos: list[HallazgoCodigo] = Field(default_factory=list)
    pruebas: ResultadoPruebas = Field(default_factory=ResultadoPruebas)
    repositorios_no_analizados: list[str] = Field(default_factory=list)
    notas: list[str] = Field(default_factory=list)


class UsoModelo(BaseModel):
    proveedor: str
    modelo: str
    proposito: str  # 'evaluacion' | 'escalamiento' | ...
    tokens_entrada: int = 0
    tokens_salida: int = 0
    tokens_cache_lectura: int = 0
    tokens_cache_escritura: int = 0
    costo_usd_estimado: float = 0.0
    duracion_s: float = 0.0
    intentos: int = 1


class ResultadoEvaluacion(BaseModel):
    resultado: ResultadoIA
    verificacion: VerificacionTecnica
    niveles_elegidos: dict[str, str]  # criterio_id -> nombre de nivel
    uso: list[UsoModelo]
    proveedor: str
    modelo_principal: str
    criterios_escalados: list[str] = Field(default_factory=list)
    requiere_revision: bool = False
    advertencias: list[str] = Field(default_factory=list)
    version_prompt: str


class ErrorEvaluacion(Exception):
    """La evaluación no pudo completarse; el mensaje es apto para mostrar al docente."""

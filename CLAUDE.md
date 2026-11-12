# Asesor Pedagógico Inteligente — Proyecto Final IA (U. de Manizales)

Plataforma web que recibe los laboratorios de un estudiante (cohortes 1 y 2), los evalúa con IA contra su rúbrica,
calcula una nota 0,0–5,0 **en el backend**, genera un informe integral y un mapa mental interactivo de competencias,
y deja todo sujeto a revisión y aprobación docente. Entrega final: **URL pública funcional**.

- Enunciado original: [Proyecto_Final_IA_Asesor_Pedagogico_V3_Rubricas_Verificacion.md](Proyecto_Final_IA_Asesor_Pedagogico_V3_Rubricas_Verificacion.md) — es la fuente de verdad.
- Matriz de requisitos con IDs y criterios de aceptación: [docs/REQUISITOS.md](docs/REQUISITOS.md)
- Arquitectura y decisiones: [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md)
- Cómo trabajan los agentes (harness): [docs/HARNESS.md](docs/HARNESS.md)
- Bitácora de uso de IA (entregable obligatorio): [docs/BITACORA_IA.md](docs/BITACORA_IA.md)

Idioma: todo (código de dominio, UI, docs, commits) en **español**. Identificadores técnicos pueden ir en inglés.

## Reglas de oro (no negociables — vienen del enunciado)

1. **La nota la calcula el backend**, nunca el LLM. El LLM solo devuelve, por criterio, nivel de desempeño + evidencias + justificación;
   el backend aplica ponderaciones y reglas de la rúbrica.
2. **Toda salida de LLM se valida con Pydantic / JSON Schema.** Si no valida → reintento acotado → si falla, marcar para revisión humana.
3. **El código del estudiante solo se ejecuta en sandbox**: contenedor aislado, sin red por defecto, límites de CPU/memoria/tiempo, usuario sin privilegios.
4. **Trazabilidad completa** por evaluación: evidencias analizadas, versión de la rúbrica, modelo y parámetros usados, resultados de pruebas, justificaciones.
5. **Nada se publica al estudiante sin aprobación docente** (estados: borrador → en_revision → aprobada → publicada).
6. **Rúbricas: ponderaciones deben sumar 100 %.** Detectar inconsistencias y bloquear la evaluación hasta corregirlas.
7. **Proveedor de IA configurable** (nube o local) detrás de una interfaz; ningún módulo llama al SDK directamente salvo el adaptador.
8. Secretos solo por variables de entorno; nunca en el repositorio.

## Forma de trabajo

- El orquestador (sesión principal) planifica, divide en tareas pequeñas, delega a los subagentes de `.claude/agents/`
  y **verifica** cada resultado antes de darlo por hecho. Ver protocolo de escalamiento en [docs/HARNESS.md](docs/HARNESS.md).
- Cada tarea referencia un ID de requisito (p. ej. `RF-04`) y cierra con su criterio de aceptación comprobado.
- Al terminar cada bloque de trabajo relevante, añadir una entrada a [docs/BITACORA_IA.md](docs/BITACORA_IA.md).
- Las decisiones técnicas nuevas se registran en la sección "Decisiones" de [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

# Matriz de requisitos

Extraída del enunciado. Estado: ⬜ pendiente · 🟨 en curso · ✅ verificado.
Una fila solo pasa a ✅ cuando su criterio de aceptación se comprobó (prueba automatizada o verificación manual registrada).

## Funcionales (obligatorios)

| ID | Requisito | Criterio de aceptación | Estado |
|----|-----------|------------------------|--------|
| RF-01 | Entrada por laboratorio: descripción/objetivos, rúbrica y solución del estudiante | Un laboratorio no puede evaluarse si falta alguno de los tres elementos | ✅ solo se evalúan entregas `lista` (descripción, rúbrica válida, informe y código) |
| RF-02 | Portafolio académico por estudiante, cohorte (1 y 2) y laboratorio | Cada entrega guarda PDF con texto legible, código (URL GitHub o ZIP) y rúbrica; video/presentación opcionales | ✅ portafolio por cohorte; PDF con texto legible, ZIP o GitHub, opcionales; verificado de punta a punta |
| RF-03 | Asociar cada evidencia a su actividad y conservar la versión de rúbrica usada | Editar una rúbrica crea versión nueva; evaluaciones antiguas siguen apuntando a la versión original | ✅ versiones inmutables; la entrega conserva la versión fijada; verificado de punta a punta |
| RF-04 | Gestión de rúbricas: cargar, interpretar (IA) y parametrizar competencias, criterios, descriptores, niveles y ponderaciones | Rúbrica cargada desde PDF/texto queda estructurada y editable en la UI | 🟨 editor visual de rúbricas listo; falta interpretarlas desde PDF/texto con IA |
| RF-05 | Validación de rúbricas | Detecta pesos ≠ 100 %, niveles sin descriptor, criterios sin competencia, escalas incoherentes; bloquea evaluación hasta corregir | ✅ validación en vivo y en servidor; una rúbrica inválida bloquea las entregas |
| RF-06 | Evaluación inteligente por criterio con evidencias citadas | Cada criterio tiene nivel, evidencias concretas (archivo/página/línea), justificación, fortalezas, debilidades, recomendaciones | 🟨 pipeline completo con evidencias citadas, fortalezas, debilidades, recomendaciones y aprendizajes; verificado con el proveedor de demostración; falta probar con Claude real |
| RF-07 | Nota preliminar 0,0–5,0 calculada por el backend | Función determinista y con pruebas unitarias; mismo input → misma nota | ✅ `calculo_nota.py`; las notas preliminar y final se calculan en el backend |
| RF-08 | Revisión y aprobación docente | Docente puede ajustar nivel/nota por criterio con justificación; queda auditado quién y cuándo | ✅ ajuste por criterio con justificación e historial, aprobación y publicación; verificado de punta a punta |
| RF-09 | Informe integrado del aprendizaje (ambas cohortes) | Incluye notas, competencias, niveles de dominio, evolución, brechas y plan de fortalecimiento; visible y descargable (PDF) | ⬜ |
| RF-10 | Mapa mental interactivo de competencias en IA | Nodos = temáticas/conceptos; por nodo: laboratorios, evidencias, nivel de dominio, aspectos a profundizar; navegación, zoom, exploración y descarga (PNG/SVG/JSON) | ⬜ |
| RF-11 | Presentación del proyecto y equipo | Página con abstract (objetivos, funcionalidades, tecnologías, aportes) y foto, nombre y rol de cada integrante | 🟨 página lista; falta la foto |

## Ingeniería y confiabilidad

| ID | Requisito | Criterio de aceptación | Estado |
|----|-----------|------------------------|--------|
| RNF-01 | Uso intensivo de IA documentado | `docs/BITACORA_IA.md` con herramientas, aportes, limitaciones y decisiones | 🟨 |
| RNF-02 | Salidas de IA estructuradas y validadas (Pydantic/JSON Schema) | Ninguna salida de LLM entra a la BD sin pasar por su esquema | ✅ salidas del modelo validadas con Pydantic + reglas de negocio con reintento |
| RNF-03 | Verificación objetiva del código: sintaxis, análisis estático, pruebas | Resultados de lint/pruebas forman parte de la evidencia de la evaluación | 🟨 sintaxis (ast) y análisis estático (ruff) sin ejecutar código; faltan las pruebas unitarias en sandbox |
| RNF-04 | Sandbox: aislado, sin red, límites de recursos y tiempo | Prueba que demuestre que código malicioso (red, fork bomb, bucle infinito) es contenido | ⬜ |
| RNF-05 | Proveedor de IA configurable (local o nube), justificado con requisitos, límites y costos | Cambiar de proveedor solo requiere configuración; costos documentados | 🟨 adaptadores Claude, Ollama y demostración, configurables por `.env`; Claude y Ollama probados solo con clientes simulados |
| RNF-06 | Despliegue con URL pública, autenticación, gestión de usuarios, persistencia y almacenamiento seguro | URL accesible; roles (admin, docente, estudiante); archivos fuera de la raíz pública | 🟨 auth JWT, roles, usuarios y PostgreSQL listos y probados en Docker; falta despliegue público |
| RNF-07 | Trazabilidad por evaluación | Se guarda: evidencias, versión de rúbrica, modelo/parámetros, resultados de pruebas, justificaciones, ajustes docentes | ✅ se guardan evidencias, versión de rúbrica, proveedor, modelos, prompt, uso, costo, verificación, ajustes y auditoría |
| RNF-08 | Protección de información académica | Un estudiante solo ve lo suyo y solo cuando está publicado | 🟨 404 a estudiantes sobre entregas y archivos ajenos; archivos guardados con nombre UUID fuera de rutas públicas |
| RNF-09 | Análisis multimodal (recomendado) | Texto/PDF y código obligatorios; imágenes/diagramas por modelo de visión; video/audio opcional | ⬜ |
| RNF-10 | Calidad: arquitectura, usabilidad, estabilidad | Pruebas automatizadas pasando en CI; UI responsive | ⬜ |

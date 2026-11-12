# Arquitectura

> Estado: **stack confirmado el 2026-11-12**. Equipo: Juan Diego Varón Valencia (único integrante).

## Vista general

```
[Frontend web]  ──HTTPS──▶  [API backend]  ──▶ [Base de datos]
  - portafolio                 - auth y roles         (usuarios, rúbricas versionadas,
  - rúbricas                   - rúbricas/validador    entregas, evaluaciones, auditoría)
  - revisión docente           - motor de nota   ──▶ [Almacenamiento de archivos]
  - informe / mapa mental      - cola de trabajos      (PDF, ZIP, imágenes — privado)
                                    │
                                    ▼
                          [Worker de evaluación] ──▶ [Sandbox de ejecución]
                           - extracción PDF/código     contenedor sin red,
                           - orquestador de modelos    límites CPU/RAM/tiempo
                           - validación Pydantic
                                    │
                                    ▼
                          [Adaptador de proveedor IA]  → Claude API (nube) | Ollama (local)
```

## Stack

| Capa | Elección | Por qué |
|------|-----------|---------|
| Backend | Python + FastAPI + Pydantic v2 | El enunciado pide Pydantic/JSON Schema; ecosistema de análisis de código Python (ruff, pytest) |
| BD | PostgreSQL (SQLAlchemy + Alembic) | Persistencia relacional, versionado de rúbricas, JSONB para resultados |
| Cola | Tareas en segundo plano (RQ/Celery + Redis, o BackgroundTasks al inicio) | Las evaluaciones tardan minutos |
| Frontend | React (Vite o Next.js) + Tailwind | Mapa mental con React Flow / Cytoscape.js; descarga PNG/SVG |
| Informe PDF | WeasyPrint o generación en el frontend | Descarga del informe integral |
| Sandbox | Docker con `--network none`, `--memory`, `--cpus`, `--pids-limit`, timeout, usuario no root, FS de solo lectura | Requisito RNF-04 |
| IA nube | Claude API (SDK oficial `anthropic`) | Estructura validada, visión para diagramas, PDFs nativos |
| IA local | Ollama (modelo abierto) | Requisito RNF-05 (modelos locales) |
| Despliegue | VPS con Docker Compose (o Railway/Render + BD gestionada) | Necesitamos Docker para el sandbox → un VPS es lo más simple |

## Orquestación de modelos en la evaluación

La misma idea del harness de desarrollo aplicada al producto: modelos baratos hacen el volumen, un modelo potente
interviene solo cuando hace falta.

| Paso | Modelo sugerido | Salida (Pydantic) |
|------|-----------------|-------------------|
| 1. Interpretar rúbrica desde PDF/texto | Sonnet 5.5 | `RubricaEstructurada` (competencias, criterios, niveles, pesos) |
| 2. Extraer y resumir evidencias (PDF, código, imágenes) | Haiku 5.5 (visión cuando haya imágenes) | `Evidencia[]` con referencia a archivo/página/línea |
| 3. Verificación técnica del código | Sin LLM: sandbox (sintaxis, ruff/pylint, pytest) | `ResultadoVerificacion` |
| 4. Evaluar cada criterio | Sonnet 5.5 | `EvaluacionCriterio` (nivel, evidencias citadas, justificación, confianza) |
| 5. Escalamiento | Opus 5.5 / Fable 5.2 solo si: confianza baja, evidencias contradictorias o desacuerdo con verificación técnica | `EvaluacionCriterio` revisada |
| 6. Nota | **Backend, determinista** | `nota = Σ(peso_i × valor_nivel_i)` escalada a 0,0–5,0 |
| 7. Informe integral y mapa mental | Sonnet 5.5 sobre evaluaciones ya aprobadas | `InformeIntegral`, `MapaMental` (nodos/aristas) |

Antes de fijar la cascada conviene medir la alternativa simple (un solo modelo potente con esfuerzo bajo) en 3–5
laboratorios reales y comparar calidad y costo por evaluación completa. El resultado va a "Decisiones".

## Decisiones

| Fecha | Decisión | Alternativas | Motivo |
|-------|----------|--------------|--------|
| 2026-11-12 | Desarrollo con harness orquestador + subagentes (ver HARNESS.md) | Una sola sesión | Ahorro de tokens y trabajo en paralelo por componente |
| 2026-11-12 | Stack: FastAPI + Pydantic v2 + PostgreSQL + React (Vite) + Docker Compose en VPS | Next.js, Django, PaaS | Pydantic exigido; Docker necesario para el sandbox; un solo servidor simplifica el despliegue |
| 2026-11-12 | Errores de validación responden 400 (no 422 de FastAPI) con `detail` en español | 422 por defecto | Contrato único y legible para el frontend |
| 2026-11-12 | Token JWT en `sessionStorage` del navegador | Cookie httpOnly | Prototipo simple; revisar antes de producción |

## Equipo (RF-11)

| Nombre | Rol | Foto |
|--------|-----|------|
| Juan Diego Varón Valencia | Ingeniero de software full-stack e IA (único integrante): requisitos, arquitectura, dirección de agentes de IA, verificación y despliegue | pendiente |

## Pendientes de decidir

- Hosting y dominio para la URL pública.
- Proveedor de IA por defecto y presupuesto de API.
- Foto del integrante para RF-11.
- Laboratorios reales de cohortes 1 y 2 para pruebas (con sus rúbricas).

## Modelo de datos (v1)

| Tabla | Campos clave | Notas |
|-------|--------------|-------|
| `usuarios` | id, nombre, correo (único), hash_contrasena (argon2), rol, activo, creado_en | Roles: admin, docente, estudiante |
| `laboratorios` | id, cohorte (1 o 2), codigo (único), titulo, descripcion, objetivos, temas (JSON) | Elemento 1 de RF-01 |
| `rubricas` | id, laboratorio_id | Una rúbrica lógica por laboratorio |
| `rubrica_versiones` | id, rubrica_id, numero, contenido (JSON con el esquema `Rubrica`), valida, inconsistencias (JSON), creado_por, creado_en | **Inmutables**: editar crea una versión nueva (RF-03) |
| `entregas` | id, estudiante_id, laboratorio_id, rubrica_version_id, estado, creado_en | Única por (estudiante, laboratorio); conserva la versión de rúbrica usada |
| `evidencias` | id, entrega_id, tipo, ruta_archivo o url, nombre_original, sha256, tamano_bytes, creado_en | Tipos: informe_pdf, codigo_zip, repo_github, video, presentacion, imagen |
| `evaluaciones` | id, entrega_id, rubrica_version_id, estado, proveedor, modelo, parametros (JSON), resultado_ia (JSON), verificacion (JSON), nota_preliminar, nota_final, revisado_por, aprobado_en, publicado_en, creado_en | Estados: borrador → en_revision → aprobada → publicada (RNF-07) |
| `auditoria` | id, usuario_id, accion, entidad, entidad_id, detalle (JSON), fecha | Ajustes docentes y acciones sensibles (RF-08) |

Las migraciones se manejan con Alembic; el contenedor de la API aplica `alembic upgrade head` al arrancar.

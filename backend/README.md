# Backend — Asesor Pedagógico Inteligente

FastAPI + Pydantic v2 + SQLAlchemy 2. Por defecto usa SQLite (`dev.db`); no requiere Docker ni PostgreSQL.

## Instalar
```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # Linux/Mac: .venv/bin/python
cp .env.example .env
```

## Correr
```bash
.venv/Scripts/python -m uvicorn app.main:app --reload
# http://localhost:8000/api/salud  ·  docs en /docs
```

## Base de datos y migraciones (Alembic)
```bash
.venv/Scripts/python -m alembic upgrade head      # crea/actualiza las tablas (usa DATABASE_URL)
.venv/Scripts/python -m alembic revision --autogenerate -m "descripcion"
```
El contenedor ejecuta `alembic upgrade head` antes de uvicorn (`entrypoint.sh`, fin de linea LF).

## Autenticacion y usuarios (RNF-06)
- Contrato en `docs/API.md`: `/api/auth/login`, `/api/auth/yo`, `/api/usuarios`.
- Contrasenas con argon2; JWT HS256 de 8 h firmado con `SECRET_KEY` (cambiala en produccion).
- Al arrancar, si no hay usuarios se crea un admin con `ADMIN_CORREO` y `ADMIN_CONTRASENA` (si faltan, solo se registra un aviso).
- Dependencias: `usuario_actual` (401) y `requiere_rol(Rol.admin, ...)` (403) en `app/api/deps.py`.
- Errores de validacion devuelven 400 con `{"detail": ...}` en espanol.
- Acciones sensibles (login, alta de usuario, cambios de rol/activo/contrasena) quedan en la tabla `auditoria`.

## Laboratorios, rúbricas y portafolio (Iteración 2: RF-01, RF-02, RF-03, RF-05)
- Contrato en `docs/API.md` ("Iteración 2"). Routers: `app/api/laboratorios.py`, `estudiantes.py`, `entregas.py`.
- **Rúbricas versionadas**: `POST /api/laboratorios/{id}/rubrica/versiones` siempre crea una versión nueva (aunque sea
  inválida) y guarda `valida` + `inconsistencias` con `validar_rubrica`. La vigente es la de número más alto; las
  anteriores y las entregas que apuntan a ellas no cambian. `GET .../rubrica` lista las versiones en orden ascendente.
  Una entrega solo se puede crear si la rúbrica vigente existe y es válida (si no, 400).
- **Privacidad**: un estudiante que pide una entrega o evidencia ajena recibe 404.
- **Evidencias** (`app/services/evidencias.py`): el tamaño se controla mientras se lee (413 y se borra el temporal);
  el formato se decide por la firma de bytes, no por la extensión ni el Content-Type; los ZIP se inspeccionan con
  `zipfile` sin extraer nunca; los PDF se leen con `pypdf` (>= 200 caracteres de texto, que se guarda en
  `evidencias.texto_extraido`). `detalle` por tipo: PDF `{paginas, caracteres_texto}`; ZIP
  `{archivos, tamano_descomprimido_bytes, extensiones: {".py": 12, ...}}` (top 5); repo `{owner, repo}`.
- **Almacenamiento**: `STORAGE_DIR` (por defecto `./storage`; `/app/storage` en Docker, volumen `storage`).
  Ruta `entregas/<entrega_id>/<uuid4><ext>`, nunca el nombre original; se guarda el SHA-256.
- Estado de la entrega: `borrador` -> `lista` (PDF + ZIP o repo) se recalcula al cargar/borrar evidencias; con la
  entrega en `en_evaluacion`/`evaluada` no se puede cargar ni borrar (409).
- Auditoría: laboratorio creado/editado, versión de rúbrica creada, entrega creada, evidencia cargada/eliminada.
- Migración `0002`: `evidencias.texto_extraido` y `evidencias.detalle`; las entregas `pendiente` pasan a `borrador`.

## Evaluaciones y revisión docente (Iteración 3: RF-06, RF-07, RF-08, RNF-07)
- Contrato en `docs/API.md` ("Iteración 3"). Router `app/api/evaluaciones.py`; lógica en `app/services/evaluaciones.py`.
  El pipeline de IA vive en `app/evaluacion/` (interfaz `contrato.py`); la API solo llama a `servicio.evaluar` y `servicio.estado_proveedor`.
- `POST /api/entregas/{id}/evaluaciones` crea la evaluación `procesando` (202), pone la entrega en `en_evaluacion` y encola
  `ejecutar_evaluacion` con `BackgroundTasks`. La tarea abre **su propia sesión** (`get_session_factory`, sustituible en pruebas),
  arma el `ContextoEvaluacion` con la **versión de rúbrica fijada en la entrega** y rutas absolutas desde `STORAGE_DIR`, y persiste
  resultado, verificación, uso, costo, proveedor, modelos, `version_prompt` y `parametros` (umbral y modelos). Pasa a `en_revision`
  y la entrega a `evaluada`. Si hay `ErrorEvaluacion` o cualquier excepción: evaluación `error` (mensaje en español, sin trazas;
  el detalle va al log) y la entrega vuelve a `lista`. Inicio y fin quedan en `auditoria`.
- **La nota nunca viene del LLM**: `nota_preliminar` = `calcular_nota` con los niveles de la IA; `nota_final` = `calcular_nota` con
  el nivel del último ajuste docente de cada criterio.
- **Ajustes (RF-08)**: `PATCH .../criterios/{criterio_id}` valida que el nivel exista (400), justificación >= 10 caracteres (400),
  solo en `en_revision` (409). Cada ajuste es una fila de `ajustes_criterio` (nivel anterior/nuevo, justificación, usuario, fecha):
  el historial no se edita ni se borra; manda el último. También se audita. Flujo: `en_revision` -> `aprobar` -> `publicar`; fuera de orden, 409.
- **Estudiante**: ve una evaluación solo si es suya y está `publicada` (si no, 404). Recibe una vista recortada
  (`EvaluacionEstudiante`) sin `uso`, `costo_usd_estimado`, `confianza`, `nivel_ia`, `nota_preliminar`, `advertencias`,
  `requiere_revision`, `error`, `modelo` ni `escalado` por criterio.
- `GET /api/ia/configuracion` usa `estado_proveedor` (si falla, `disponible=false`) y nunca expone claves.
- Migración `0003`: columnas nuevas en `evaluaciones` (`error`, `version_prompt`, `modelo_escalamiento`, `requiere_revision`,
  `advertencias`, `uso`, `costo_usd_estimado`) y tabla `ajustes_criterio`. Verificada upgrade/downgrade/upgrade en SQLite.
- Pruebas: `tests/test_iteracion3.py` sustituye el pipeline con un doble (`monkeypatch` de `servicio.evaluar`), así que no depende de la IA.

## Informe integral y mapa mental (Iteración 4: RF-09, RF-10)
- Contrato en `docs/API.md` ("Iteración 4") e interfaz interna `app/informes/contrato.py`. Router `app/api/informes.py`;
  orquestación en `app/services/informes.py`; modelo `Informe` (tabla `informes`, migración `0004`, verificada upgrade/downgrade/upgrade).
- **Solo evaluaciones publicadas**, la más reciente por entrega (`evaluaciones_publicadas`). Los niveles finales se obtienen con
  `services.evaluaciones.niveles_finales` (IA + último ajuste docente), la misma lógica de la vista de evaluación.
- `app/informes/agregacion.py` (pura): promedio de competencia ponderado por `peso`, niveles con `nivel_por_valor` sobre el promedio ya
  redondeado a 2 decimales (mitad hacia arriba), temas normalizados (minúsculas, espacios simples), tendencia, brechas. La IA nunca toca notas.
- `app/informes/mapa.py` (pura): raíz -> categoría -> tema -> laboratorio; ids slug sin tildes (`cat:...`, `tema:...`, `lab:CODIGO`);
  temas sin categoría o con categoría fuera de `CATEGORIAS_IA` van a «Otros»; relaciones de la IA solo entre temas existentes (sin duplicados ni autorrelaciones).
- `app/informes/pdf.py`: `reportlab` (Helvetica, cubre tildes y ñ; los caracteres fuera de Latin-1 se sustituyen). Portada, resumen, notas,
  competencias, gráfico de evolución, temas, brechas, plan y pie de IA.
- `POST /api/estudiantes/{id}/informes` valida (400 sin publicadas, 409 si ya hay uno `procesando`), crea el informe `procesando` y encola
  `ejecutar_informe` (`BackgroundTasks`, sesión propia). Llama a `app.evaluacion.informe.sintetizar`; error -> `error` con mensaje en español.
  Auditoría: `informe_iniciado`, `informe_generado`, `informe_fallido`.
- Estudiante: solo su informe (otro -> 404) y vista sin `uso`, `costo_usd_estimado` ni `advertencias`. Mapa y PDF devuelven 409 si el informe no está `listo`;
  el PDF sale con `Content-Disposition: attachment`.
- Pruebas: `tests/test_informes_puros.py` (agregación y mapa con datos a mano) y `tests/test_iteracion4.py` (API; `sintetizar` sustituido con un doble).

## Probar
```bash
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m pytest
```

## Módulos de dominio puros
- `app/services/validacion_rubrica.py` (RF-05): lista de inconsistencias en español; vacía = válida.
- `app/services/calculo_nota.py` (RF-07): nota determinista con `Decimal`, sin LLM.

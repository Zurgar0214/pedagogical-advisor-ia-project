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

## Probar
```bash
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m pytest
```

## Módulos de dominio puros
- `app/services/validacion_rubrica.py` (RF-05): lista de inconsistencias en español; vacía = válida.
- `app/services/calculo_nota.py` (RF-07): nota determinista con `Decimal`, sin LLM.

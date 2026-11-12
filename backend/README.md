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
```nEl contenedor ejecuta `alembic upgrade head` antes de uvicorn (`entrypoint.sh`, fin de linea LF).

## Autenticacion y usuarios (RNF-06)
- Contrato en `docs/API.md`: `/api/auth/login`, `/api/auth/yo`, `/api/usuarios`.
- Contrasenas con argon2; JWT HS256 de 8 h firmado con `SECRET_KEY` (cambiala en produccion).
- Al arrancar, si no hay usuarios se crea un admin con `ADMIN_CORREO` y `ADMIN_CONTRASENA` (si faltan, solo se registra un aviso).
- Dependencias: `usuario_actual` (401) y `requiere_rol(Rol.admin, ...)` (403) en `app/api/deps.py`.
- Errores de validacion devuelven 400 con `{"detail": ...}` en espanol.
- Acciones sensibles (login, alta de usuario, cambios de rol/activo/contrasena) quedan en la tabla `auditoria`.

## Probar
```bash
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m pytest
```

## Módulos de dominio puros
- `app/services/validacion_rubrica.py` (RF-05): lista de inconsistencias en español; vacía = válida.
- `app/services/calculo_nota.py` (RF-07): nota determinista con `Decimal`, sin LLM.

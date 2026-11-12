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

## Probar
```bash
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m pytest
```

## Módulos de dominio puros
- `app/services/validacion_rubrica.py` (RF-05): lista de inconsistencias en español; vacía = válida.
- `app/services/calculo_nota.py` (RF-07): nota determinista con `Decimal`, sin LLM.

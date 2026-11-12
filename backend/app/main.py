import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import api_router
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.usuarios import crear_admin_inicial

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        with SessionLocal() as db:
            crear_admin_inicial(db, get_settings())
    except SQLAlchemyError:
        log.exception("No se pudo crear el admin inicial (¿falta `alembic upgrade head`?).")
    yield


def _mensaje_validacion(error: dict) -> str:
    campo = ".".join(str(p) for p in error["loc"] if p not in ("body", "query", "path"))
    tipo = error["type"]
    if tipo == "string_too_short":
        minimo = error.get("ctx", {}).get("min_length")
        detalle = f"debe tener al menos {minimo} caracteres"
    elif tipo == "missing":
        detalle = "es obligatorio"
    elif tipo == "string_pattern_mismatch":
        detalle = "tiene un formato inválido"
    elif tipo in ("enum", "literal_error"):
        detalle = "tiene un valor no permitido"
    else:
        detalle = "no es válido"
    return f"{campo}: {detalle}" if campo else detalle.capitalize()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_nombre, version=settings.app_version, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Contrato: errores de validación -> 400 con {"detail": "<mensaje en español>"}.
        detalle = "; ".join(_mensaje_validacion(e) for e in exc.errors())
        return JSONResponse(status_code=400, content={"detail": detalle})

    app.include_router(api_router)
    return app


app = create_app()
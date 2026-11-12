from fastapi import APIRouter

from app.api import salud

api_router = APIRouter(prefix="/api")
api_router.include_router(salud.router)

from fastapi import APIRouter

from app.api import auth, salud, usuarios

api_router = APIRouter(prefix="/api")
api_router.include_router(salud.router)
api_router.include_router(auth.router)
api_router.include_router(usuarios.router)
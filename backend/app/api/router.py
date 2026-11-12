from fastapi import APIRouter

from app.api import auth, entregas, estudiantes, laboratorios, salud, usuarios

api_router = APIRouter(prefix="/api")
api_router.include_router(salud.router)
api_router.include_router(auth.router)
api_router.include_router(usuarios.router)
api_router.include_router(laboratorios.router)
api_router.include_router(estudiantes.router)
api_router.include_router(entregas.router)
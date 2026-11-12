from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter()


class Salud(BaseModel):
    estado: str
    version: str


@router.get("/salud", response_model=Salud)
def salud() -> Salud:
    return Salud(estado="ok", version=get_settings().app_version)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.seguridad import hashear_contrasena
from app.db.session import Base, get_db
from app.main import app
from app.models.usuario import Usuario
from app.schemas.rubrica import Competencia, Criterio, NivelDesempeno, Rubrica


def niveles(*valores: float) -> list[NivelDesempeno]:
    return [NivelDesempeno(nombre=f"N{v}", descriptor=f"Descriptor {v}", valor=v) for v in valores]


def hacer_rubrica(pesos: list[float], valores: tuple[float, ...] = (0, 2.5, 5)) -> Rubrica:
    return Rubrica(
        version=1,
        competencias=[Competencia(id="c1", nombre="Competencia 1")],
        criterios=[
            Criterio(
                id=f"k{i}",
                nombre=f"Criterio {i}",
                competencia_id="c1",
                peso=p,
                niveles=niveles(*valores),
            )
            for i, p in enumerate(pesos, start=1)
        ],
    )


@pytest.fixture
def rubrica_valida() -> Rubrica:
    return hacer_rubrica([40, 60])


# ---- Base de datos y cliente HTTP para pruebas de la API (SQLite en memoria) ----

CONTRASENA = "clave-segura-1"


@pytest.fixture
def fabrica_sesion():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def db(fabrica_sesion):
    with fabrica_sesion() as sesion:
        yield sesion


@pytest.fixture
def cliente(fabrica_sesion):
    def _get_db():
        with fabrica_sesion() as sesion:
            yield sesion

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def crear_usuario(db, correo, rol="estudiante", activo=True, contrasena=CONTRASENA) -> Usuario:
    usuario = Usuario(
        nombre=f"Usuario {correo}",
        correo=correo,
        hash_contrasena=hashear_contrasena(contrasena),
        rol=rol,
        activo=activo,
    )
    db.add(usuario)
    db.commit()
    return usuario


def cabecera(cliente, correo, contrasena=CONTRASENA) -> dict:
    r = cliente.post("/api/auth/login", json={"correo": correo, "contrasena": contrasena})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin(db):
    return crear_usuario(db, "admin@u.co", "admin")


@pytest.fixture
def h_admin(cliente, admin):
    return cabecera(cliente, "admin@u.co")
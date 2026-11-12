from datetime import timedelta

import jwt
from sqlalchemy import select

from app.core.config import get_settings
from app.core.seguridad import crear_token
from app.models.auditoria import Auditoria
from tests.conftest import CONTRASENA, cabecera, crear_usuario


def test_login_correcto(cliente, admin):
    r = cliente.post("/api/auth/login", json={"correo": "ADMIN@u.co ", "contrasena": CONTRASENA})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["access_token"]
    assert cuerpo["usuario"]["correo"] == "admin@u.co"
    assert cuerpo["usuario"]["rol"] == "admin"
    assert cuerpo["usuario"]["creado_en"].endswith("Z")
    assert "hash_contrasena" not in cuerpo["usuario"]


def test_token_expira_en_8_horas(cliente, admin):
    token = cabecera(cliente, "admin@u.co")["Authorization"].split()[1]
    carga = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    assert carga["exp"] - carga["iat"] == 8 * 3600


def test_login_falla_con_mismo_mensaje(cliente, db, admin):
    crear_usuario(db, "off@u.co", activo=False)
    respuestas = [
        cliente.post("/api/auth/login", json={"correo": "admin@u.co", "contrasena": "incorrecta"}),
        cliente.post("/api/auth/login", json={"correo": "nadie@u.co", "contrasena": CONTRASENA}),
        cliente.post("/api/auth/login", json={"correo": "off@u.co", "contrasena": CONTRASENA}),
    ]
    assert all(r.status_code == 401 for r in respuestas)
    assert len({r.json()["detail"] for r in respuestas}) == 1


def test_yo(cliente, admin, h_admin):
    r = cliente.get("/api/auth/yo", headers=h_admin)
    assert r.status_code == 200
    assert r.json()["id"] == admin.id


def test_sin_token_401(cliente):
    r = cliente.get("/api/auth/yo")
    assert r.status_code == 401
    assert "detail" in r.json()


def test_token_invalido_401(cliente):
    r = cliente.get("/api/auth/yo", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401


def test_token_firmado_con_otra_clave_401(cliente, admin):
    otra_clave = "otra-clave-distinta-de-32-bytes!!"
    falso = jwt.encode({"sub": str(admin.id), "exp": 9999999999}, otra_clave, "HS256")
    r = cliente.get("/api/auth/yo", headers={"Authorization": f"Bearer {falso}"})
    assert r.status_code == 401


def test_token_expirado_401(cliente, admin):
    token = crear_token(admin.id, expira_en=timedelta(seconds=-5))
    r = cliente.get("/api/auth/yo", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_de_usuario_desactivado_401(cliente, db, admin, h_admin):
    admin.activo = False
    db.merge(admin)
    db.commit()
    assert cliente.get("/api/auth/yo", headers=h_admin).status_code == 401


def test_login_queda_en_auditoria(cliente, db, admin):
    cabecera(cliente, "admin@u.co")
    eventos = db.scalars(select(Auditoria).where(Auditoria.accion == "login")).all()
    assert len(eventos) == 1
    assert eventos[0].usuario_id == admin.id
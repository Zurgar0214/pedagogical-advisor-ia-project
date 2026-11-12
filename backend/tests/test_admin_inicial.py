import logging

from sqlalchemy import func, select

from app.core.config import Settings
from app.core.seguridad import verificar_contrasena
from app.models.auditoria import Auditoria
from app.models.usuario import Usuario
from app.services.usuarios import crear_admin_inicial
from tests.conftest import crear_usuario


def _config(correo, contrasena):
    return Settings(_env_file=None, admin_correo=correo, admin_contrasena=contrasena)


def test_crea_admin_si_no_hay_usuarios(db):
    admin = crear_admin_inicial(db, _config("Root@U.co", "clave-inicial-1"))
    assert admin is not None
    guardado = db.scalar(select(Usuario))
    assert guardado.correo == "root@u.co" and guardado.rol == "admin" and guardado.activo
    assert verificar_contrasena("clave-inicial-1", guardado.hash_contrasena)
    assert db.scalar(select(Auditoria.id).where(Auditoria.accion == "usuario_creado"))


def test_no_crea_si_ya_hay_usuarios(db):
    crear_usuario(db, "otro@u.co")
    assert crear_admin_inicial(db, _config("root@u.co", "clave-inicial-1")) is None
    assert db.scalar(select(func.count()).select_from(Usuario)) == 1


def test_no_crea_ni_falla_sin_variables_y_avisa(db, caplog):
    with caplog.at_level(logging.WARNING):
        assert crear_admin_inicial(db, _config(None, None)) is None
    assert db.scalar(select(func.count()).select_from(Usuario)) == 0
    assert "ADMIN_CORREO" in caplog.text


def test_lifespan_crea_admin(fabrica_sesion, monkeypatch):
    from fastapi.testclient import TestClient

    import app.main as main

    monkeypatch.setattr(main, "SessionLocal", fabrica_sesion)
    monkeypatch.setattr(main, "get_settings", lambda: _config("root@u.co", "clave-inicial-1"))
    with TestClient(main.app):
        pass
    with fabrica_sesion() as s:
        assert s.scalar(select(Usuario.correo)) == "root@u.co"
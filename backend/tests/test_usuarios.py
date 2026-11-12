from sqlalchemy import select

from app.models.auditoria import Auditoria
from app.models.usuario import Usuario
from tests.conftest import CONTRASENA, cabecera, crear_usuario

NUEVO = {"nombre": "Ana Pérez", "correo": "ana@u.co", "contrasena": "12345678", "rol": "estudiante"}


def test_estudiante_y_docente_reciben_403(cliente, db):
    crear_usuario(db, "est@u.co", "estudiante")
    crear_usuario(db, "doc@u.co", "docente")
    for correo in ("est@u.co", "doc@u.co"):
        h = cabecera(cliente, correo)
        assert cliente.get("/api/usuarios", headers=h).status_code == 403
        assert cliente.post("/api/usuarios", json=NUEVO, headers=h).status_code == 403
        assert cliente.patch("/api/usuarios/1", json={"nombre": "x"}, headers=h).status_code == 403


def test_usuarios_sin_sesion_401(cliente):
    assert cliente.get("/api/usuarios").status_code == 401


def test_crear_usuario(cliente, db, h_admin):
    r = cliente.post("/api/usuarios", json=NUEVO, headers=h_admin)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["correo"] == "ana@u.co" and cuerpo["rol"] == "estudiante" and cuerpo["activo"]
    assert "hash_contrasena" not in cuerpo and "contrasena" not in cuerpo
    guardado = db.scalar(select(Usuario).where(Usuario.correo == "ana@u.co"))
    assert guardado.hash_contrasena.startswith("$argon2")
    # El nuevo usuario puede iniciar sesión.
    assert cabecera(cliente, "ana@u.co", "12345678")


def test_correo_duplicado_409(cliente, h_admin):
    assert cliente.post("/api/usuarios", json=NUEVO, headers=h_admin).status_code == 201
    r = cliente.post("/api/usuarios", json={**NUEVO, "correo": "ANA@u.co"}, headers=h_admin)
    assert r.status_code == 409
    assert "correo" in r.json()["detail"]


def test_contrasena_corta_400(cliente, h_admin):
    r = cliente.post("/api/usuarios", json={**NUEVO, "contrasena": "corta"}, headers=h_admin)
    assert r.status_code == 400
    assert isinstance(r.json()["detail"], str) and "contrasena" in r.json()["detail"]


def test_rol_invalido_400(cliente, h_admin):
    r = cliente.post("/api/usuarios", json={**NUEVO, "rol": "rector"}, headers=h_admin)
    assert r.status_code == 400


def test_listar_con_filtro_por_rol(cliente, db, h_admin):
    crear_usuario(db, "e1@u.co", "estudiante")
    crear_usuario(db, "d1@u.co", "docente")
    todos = cliente.get("/api/usuarios", headers=h_admin).json()
    assert len(todos) == 3
    docentes = cliente.get("/api/usuarios?rol=docente", headers=h_admin).json()
    assert [u["correo"] for u in docentes] == ["d1@u.co"]


def test_patch_usuario_y_auditoria(cliente, db, h_admin):
    est = crear_usuario(db, "e1@u.co", "estudiante")
    r = cliente.patch(
        f"/api/usuarios/{est.id}",
        json={"nombre": "Nuevo", "rol": "docente", "activo": False, "contrasena": "otra-clave-99"},
        headers=h_admin,
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert (cuerpo["nombre"], cuerpo["rol"], cuerpo["activo"]) == ("Nuevo", "docente", False)
    # Desactivado: ya no puede entrar.
    r = cliente.post("/api/auth/login", json={"correo": "e1@u.co", "contrasena": "otra-clave-99"})
    assert r.status_code == 401

    eventos = db.scalars(select(Auditoria).where(Auditoria.entidad_id == est.id)).all()
    acciones = {e.accion for e in eventos}
    esperadas = {"usuario_rol_cambiado", "usuario_activo_cambiado", "usuario_contrasena_cambiada"}
    assert esperadas <= acciones
    assert "otra-clave-99" not in str([e.detalle for e in eventos])


def test_creacion_queda_en_auditoria_sin_contrasena(cliente, db, admin, h_admin):
    cliente.post("/api/usuarios", json=NUEVO, headers=h_admin)
    ev = db.scalars(select(Auditoria).where(Auditoria.accion == "usuario_creado")).one()
    assert ev.usuario_id == admin.id
    assert NUEVO["contrasena"] not in str(ev.detalle)


def test_patch_cambiar_contrasena_permite_login(cliente, db, h_admin):
    est = crear_usuario(db, "e1@u.co")
    cliente.patch(f"/api/usuarios/{est.id}", json={"contrasena": "nueva-clave-1"}, headers=h_admin)
    assert cabecera(cliente, "e1@u.co", "nueva-clave-1")
    r = cliente.post("/api/auth/login", json={"correo": "e1@u.co", "contrasena": CONTRASENA})
    assert r.status_code == 401


def test_patch_usuario_inexistente_404(cliente, h_admin):
    r = cliente.patch("/api/usuarios/999", json={"nombre": "x"}, headers=h_admin)
    assert r.status_code == 404


def test_admin_no_puede_desactivarse_a_si_mismo(cliente, admin, h_admin):
    r = cliente.patch(f"/api/usuarios/{admin.id}", json={"activo": False}, headers=h_admin)
    assert r.status_code == 400


def test_admin_no_puede_quitarse_el_rol(cliente, admin, h_admin):
    r = cliente.patch(f"/api/usuarios/{admin.id}", json={"rol": "docente"}, headers=h_admin)
    assert r.status_code == 400
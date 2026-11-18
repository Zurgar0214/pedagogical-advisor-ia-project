"""Límite de intentos de inicio de sesión fallidos por correo."""

from app.core.limitador import LimitadorLogin
from tests.conftest import CONTRASENA


def _login(cliente, correo, contrasena):
    return cliente.post("/api/auth/login", json={"correo": correo, "contrasena": contrasena})


def test_bloquea_tras_cinco_fallos_aunque_la_clave_sea_correcta(cliente, admin):
    for _ in range(5):
        assert _login(cliente, "admin@u.co", "incorrecta").status_code == 401
    r = _login(cliente, "admin@u.co", CONTRASENA)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0


def test_correo_inexistente_se_bloquea_igual(cliente, admin):
    for _ in range(5):
        _login(cliente, "nadie@u.co", "x")
    assert _login(cliente, "nadie@u.co", "x").status_code == 429


def test_bloqueo_es_por_correo(cliente, admin, db):
    for _ in range(5):
        _login(cliente, "nadie@u.co", "x")
    assert _login(cliente, "admin@u.co", CONTRASENA).status_code == 200


def test_exito_reinicia_el_contador(cliente, admin):
    for _ in range(4):
        _login(cliente, "admin@u.co", "incorrecta")
    assert _login(cliente, "admin@u.co", CONTRASENA).status_code == 200
    for _ in range(4):
        assert _login(cliente, "admin@u.co", "incorrecta").status_code == 401
    assert _login(cliente, "admin@u.co", CONTRASENA).status_code == 200


def test_bloqueo_expira_y_ventana_descarta_fallos_viejos():
    ahora = [0.0]
    lim = LimitadorLogin(reloj=lambda: ahora[0])
    for _ in range(4):
        lim.registrar_fallo("a@u.co", 5, 900, 300)
    ahora[0] = 1000.0  # fuera de la ventana: los 4 fallos ya no cuentan
    lim.registrar_fallo("a@u.co", 5, 900, 300)
    assert lim.segundos_bloqueo("a@u.co") == 0
    for _ in range(4):
        lim.registrar_fallo("a@u.co", 5, 900, 300)
    assert lim.segundos_bloqueo("a@u.co") > 0
    ahora[0] += 301
    assert lim.segundos_bloqueo("a@u.co") == 0

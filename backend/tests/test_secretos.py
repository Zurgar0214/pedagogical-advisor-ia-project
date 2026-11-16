import pytest

from app.core.config import Settings, verificar_secretos

PG = "postgresql+psycopg://u:p@db/x"
FUERTE = "x" * 40


def test_sqlite_permite_secretos_de_desarrollo():
    verificar_secretos(Settings(database_url="sqlite:///./dev.db", secret_key="dev-inseguro-cambiar-en-produccion"))


@pytest.mark.parametrize("clave", ["dev-inseguro-cambiar-en-produccion", "cambia-esta-clave-larga-y-aleatoria", "corta"])
def test_postgres_rechaza_secret_key_insegura(clave):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        verificar_secretos(Settings(database_url=PG, secret_key=clave))


def test_postgres_rechaza_token_de_sandbox_de_ejemplo():
    with pytest.raises(RuntimeError, match="SANDBOX_TOKEN"):
        verificar_secretos(
            Settings(database_url=PG, secret_key=FUERTE, sandbox_url="http://sandbox:8100", sandbox_token="cambia-esto-por-un-token-largo")
        )


def test_postgres_con_secretos_propios_arranca():
    verificar_secretos(Settings(database_url=PG, secret_key=FUERTE, sandbox_url="http://sandbox:8100", sandbox_token=FUERTE))
    verificar_secretos(Settings(database_url=PG, secret_key=FUERTE))  # sandbox deshabilitada

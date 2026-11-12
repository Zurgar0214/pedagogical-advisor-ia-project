from fastapi.testclient import TestClient

from app.main import app


def test_salud():
    r = TestClient(app).get("/api/salud")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estado"] == "ok"
    assert cuerpo["version"]

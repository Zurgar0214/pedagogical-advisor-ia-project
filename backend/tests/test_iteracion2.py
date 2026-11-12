"""Iteración 2: laboratorios, rúbricas versionadas, entregas, evidencias y portafolio."""

import hashlib
from pathlib import Path
from urllib.parse import unquote

import pytest
from sqlalchemy import select

from app.api.deps import get_storage_dir
from app.main import app
from app.models.auditoria import Auditoria
from app.services import evidencias as svc
from tests.conftest import cabecera, crear_usuario
from tests.utiles import (
    pdf_bytes,
    pdf_con_texto,
    pdf_sin_texto,
    png_bytes,
    zip_bytes,
)

# ---------------------------------------------------------------- fixtures y ayudas


@pytest.fixture
def storage(tmp_path: Path):
    app.dependency_overrides[get_storage_dir] = lambda: tmp_path
    yield tmp_path


@pytest.fixture
def h_docente(cliente, db):
    crear_usuario(db, "doc@u.co", "docente")
    return cabecera(cliente, "doc@u.co")


@pytest.fixture
def est1(db):
    return crear_usuario(db, "e1@u.co", "estudiante")


@pytest.fixture
def h_est1(cliente, est1):
    return cabecera(cliente, "e1@u.co")


@pytest.fixture
def est2(db):
    return crear_usuario(db, "e2@u.co", "estudiante")


@pytest.fixture
def h_est2(cliente, est2):
    return cabecera(cliente, "e2@u.co")


def rubrica_json(pesos=(40, 60)) -> dict:
    return {
        "competencias": [{"id": "c1", "nombre": "Competencia 1"}],
        "criterios": [
            {
                "id": f"k{i}",
                "nombre": f"Criterio {i}",
                "descripcion": "Qué se evalúa",
                "competencia_id": "c1",
                "peso": peso,
                "niveles": [
                    {"nombre": "Bajo", "descriptor": "Poco", "valor": 1},
                    {"nombre": "Alto", "descriptor": "Mucho", "valor": 5},
                ],
            }
            for i, peso in enumerate(pesos, start=1)
        ],
    }


def crear_lab(cliente, h, codigo="C1-LAB01", cohorte=1):
    r = cliente.post(
        "/api/laboratorios",
        headers=h,
        json={
            "cohorte": cohorte,
            "codigo": codigo,
            "titulo": "Regresión lineal",
            "descripcion": "d",
            "objetivos": "o",
            "temas": ["regresión"],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def crear_version(cliente, h, lab_id, pesos=(40, 60)):
    return cliente.post(
        f"/api/laboratorios/{lab_id}/rubrica/versiones", headers=h, json=rubrica_json(pesos)
    )


@pytest.fixture
def lab(cliente, h_docente):
    lab = crear_lab(cliente, h_docente)
    assert crear_version(cliente, h_docente, lab["id"]).status_code == 201
    return lab


def crear_entrega(cliente, h, lab_id, **extra):
    return cliente.post("/api/entregas", headers=h, json={"laboratorio_id": lab_id, **extra})


@pytest.fixture
def entrega(cliente, h_est1, lab, storage):
    r = crear_entrega(cliente, h_est1, lab["id"])
    assert r.status_code == 201, r.text
    return r.json()


def subir(cliente, h, entrega_id, tipo, contenido, nombre="archivo.bin"):
    return cliente.post(
        f"/api/entregas/{entrega_id}/evidencias",
        headers=h,
        data={"tipo": tipo},
        files={"archivo": (nombre, contenido, "application/octet-stream")},
    )


def subir_repo(cliente, h, entrega_id, url):
    return cliente.post(
        f"/api/entregas/{entrega_id}/evidencias", headers=h, data={"tipo": "repo_github", "url": url}
    )


def acciones(db) -> list[str]:
    return [a.accion for a in db.scalars(select(Auditoria).order_by(Auditoria.id))]


# ---------------------------------------------------------------- laboratorios (RF-01)


def test_listar_estudiantes_solo_activos_ordenados(cliente, db, h_docente, h_est1):
    crear_usuario(db, "z@u.co", "estudiante")
    crear_usuario(db, "inactivo@u.co", "estudiante", activo=False)
    r = cliente.get("/api/estudiantes", headers=h_docente)
    assert r.status_code == 200
    nombres = [e["nombre"] for e in r.json()]
    assert nombres == sorted(nombres)
    assert {e["correo"] for e in r.json()} == {"e1@u.co", "z@u.co"}
    assert set(r.json()[0]) == {"id", "nombre", "correo"}


def test_listar_estudiantes_prohibido_a_estudiante(cliente, h_est1):
    assert cliente.get("/api/estudiantes", headers=h_est1).status_code == 403


def test_endpoints_requieren_sesion(cliente):
    for ruta in ("/api/laboratorios", "/api/portafolio", "/api/entregas", "/api/estudiantes"):
        assert cliente.get(ruta).status_code == 401


def test_crear_laboratorio_permisos_y_auditoria(cliente, db, h_docente, h_est1, h_admin):
    cuerpo = {"cohorte": 1, "codigo": "C1-LAB01", "titulo": "T", "descripcion": "", "objetivos": "", "temas": []}
    assert cliente.post("/api/laboratorios", headers=h_est1, json=cuerpo).status_code == 403
    r = cliente.post("/api/laboratorios", headers=h_docente, json=cuerpo)
    assert r.status_code == 201
    assert r.json()["rubrica_vigente"] is None
    assert cliente.post("/api/laboratorios", headers=h_admin, json={**cuerpo, "codigo": "X"}).status_code == 201
    assert "laboratorio_creado" in acciones(db)


def test_laboratorio_codigo_repetido_409_y_cohorte_invalida_400(cliente, h_docente):
    crear_lab(cliente, h_docente)
    cuerpo = {"cohorte": 1, "codigo": "C1-LAB01", "titulo": "T"}
    assert cliente.post("/api/laboratorios", headers=h_docente, json=cuerpo).status_code == 409
    assert cliente.post("/api/laboratorios", headers=h_docente, json={**cuerpo, "cohorte": 3}).status_code == 400


def test_listar_filtrar_y_editar_laboratorio(cliente, db, h_docente, h_est1):
    a = crear_lab(cliente, h_docente, "C2-LAB01", cohorte=2)
    crear_lab(cliente, h_docente, "C1-LAB02", cohorte=1)
    crear_lab(cliente, h_docente, "C1-LAB01", cohorte=1)
    todos = cliente.get("/api/laboratorios", headers=h_est1).json()
    assert [x["codigo"] for x in todos] == ["C1-LAB01", "C1-LAB02", "C2-LAB01"]
    assert [x["codigo"] for x in cliente.get("/api/laboratorios?cohorte=2", headers=h_est1).json()] == ["C2-LAB01"]

    assert cliente.patch(f"/api/laboratorios/{a['id']}", headers=h_est1, json={"titulo": "x"}).status_code == 403
    r = cliente.patch(f"/api/laboratorios/{a['id']}", headers=h_docente, json={"titulo": "Nuevo"})
    assert r.status_code == 200 and r.json()["titulo"] == "Nuevo" and r.json()["codigo"] == "C2-LAB01"
    assert cliente.patch(f"/api/laboratorios/{a['id']}", headers=h_docente, json={"codigo": "C1-LAB01"}).status_code == 409
    assert cliente.get("/api/laboratorios/999", headers=h_docente).status_code == 404
    assert "laboratorio_editado" in acciones(db)


# ---------------------------------------------------------------- rúbricas (RF-03, RF-05)


def test_version_nueva_no_altera_las_anteriores_ni_las_entregas(cliente, db, h_docente, h_est1, lab, storage):
    entrega = crear_entrega(cliente, h_est1, lab["id"]).json()
    v1 = entrega["rubrica_version"]["id"]
    contenido_v1 = cliente.get(f"/api/rubrica-versiones/{v1}", headers=h_est1).json()

    r = crear_version(cliente, h_docente, lab["id"], pesos=(30, 30, 40))
    assert r.status_code == 201
    assert r.json()["numero"] == 2 and r.json()["valida"] is True
    assert r.json()["contenido"]["version"] == 2
    assert r.json()["creado_por"]["nombre"]

    # La versión 1 sigue intacta y la entrega sigue apuntando a ella.
    assert cliente.get(f"/api/rubrica-versiones/{v1}", headers=h_est1).json() == contenido_v1
    assert cliente.get(f"/api/entregas/{entrega['id']}", headers=h_est1).json()["rubrica_version"] == {"id": v1, "numero": 1}

    info = cliente.get(f"/api/laboratorios/{lab['id']}/rubrica", headers=h_est1).json()
    assert info["vigente"]["numero"] == 2
    assert [v["numero"] for v in info["versiones"]] == [1, 2]
    assert all("contenido" not in v for v in info["versiones"])
    assert cliente.get(f"/api/laboratorios/{lab['id']}", headers=h_est1).json()["rubrica_vigente"] == {
        "version_id": r.json()["id"],
        "numero": 2,
        "valida": True,
    }
    assert acciones(db).count("rubrica_version_creada") == 2


def test_rubrica_sin_version_devuelve_vigente_null(cliente, h_docente):
    lab = crear_lab(cliente, h_docente)
    r = cliente.get(f"/api/laboratorios/{lab['id']}/rubrica", headers=h_docente)
    assert r.json() == {"vigente": None, "versiones": []}


def test_rubrica_invalida_se_guarda_con_inconsistencias_y_bloquea_entregas(cliente, h_docente, h_est1, storage):
    lab = crear_lab(cliente, h_docente)
    r = crear_version(cliente, h_docente, lab["id"], pesos=(40, 40))
    assert r.status_code == 201
    assert r.json()["valida"] is False
    assert any("100" in i for i in r.json()["inconsistencias"])
    assert cliente.get(f"/api/laboratorios/{lab['id']}", headers=h_docente).json()["rubrica_vigente"]["valida"] is False

    bloqueo = crear_entrega(cliente, h_est1, lab["id"])
    assert bloqueo.status_code == 400
    assert "inconsistencias" in bloqueo.json()["detail"]

    # Corregir = nueva versión válida; ahora sí se puede entregar.
    assert crear_version(cliente, h_docente, lab["id"]).json()["numero"] == 2
    assert crear_entrega(cliente, h_est1, lab["id"]).status_code == 201


def test_entrega_sin_rubrica_400(cliente, h_docente, h_est1):
    lab = crear_lab(cliente, h_docente)
    r = crear_entrega(cliente, h_est1, lab["id"])
    assert r.status_code == 400 and "rúbrica" in r.json()["detail"]


def test_validar_rubrica_sin_guardar(cliente, h_docente, h_est1, lab):
    r = cliente.post("/api/rubricas/validar", headers=h_docente, json=rubrica_json((50, 20)))
    assert r.status_code == 200 and r.json()["valida"] is False and r.json()["inconsistencias"]
    assert cliente.post("/api/rubricas/validar", headers=h_docente, json=rubrica_json()).json() == {
        "valida": True,
        "inconsistencias": [],
    }
    assert cliente.post("/api/rubricas/validar", headers=h_est1, json=rubrica_json()).status_code == 403
    # No guardó nada: sigue la versión 1.
    assert cliente.get(f"/api/laboratorios/{lab['id']}", headers=h_docente).json()["rubrica_vigente"]["numero"] == 1


def test_crear_version_prohibido_a_estudiante_y_version_inexistente(cliente, h_docente, h_est1, lab):
    assert crear_version(cliente, h_est1, lab["id"]).status_code == 403
    assert crear_version(cliente, h_docente, 999).status_code == 404
    assert cliente.get("/api/rubrica-versiones/999", headers=h_docente).status_code == 404


# ---------------------------------------------------------------- entregas y privacidad


def test_estudiante_crea_entrega_propia_y_duplicada_da_409(cliente, db, h_est1, est1, lab, storage):
    r = crear_entrega(cliente, h_est1, lab["id"], estudiante_id=9999)  # se ignora
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["estado"] == "borrador"
    assert cuerpo["estudiante"]["id"] == est1.id
    assert cuerpo["faltantes"] == ["informe_pdf", "codigo"]
    assert cuerpo["evidencias"] == []
    assert cuerpo["laboratorio"]["codigo"] == "C1-LAB01"
    assert crear_entrega(cliente, h_est1, lab["id"]).status_code == 409
    assert "entrega_creada" in acciones(db)


def test_docente_crea_entrega_para_estudiante(cliente, h_docente, est1, lab, storage):
    assert crear_entrega(cliente, h_docente, lab["id"]).status_code == 400
    assert crear_entrega(cliente, h_docente, lab["id"], estudiante_id=9999).status_code == 404
    r = crear_entrega(cliente, h_docente, lab["id"], estudiante_id=est1.id)
    assert r.status_code == 201 and r.json()["estudiante"]["id"] == est1.id


def test_docente_no_puede_crear_entrega_para_un_no_estudiante(cliente, db, h_docente, lab):
    otro = crear_usuario(db, "otro@u.co", "docente")
    assert crear_entrega(cliente, h_docente, lab["id"], estudiante_id=otro.id).status_code == 400


def test_estudiante_recibe_404_sobre_entrega_y_evidencia_ajena(cliente, h_est1, h_est2, entrega, storage):
    ev = subir(cliente, h_est1, entrega["id"], "informe_pdf", pdf_con_texto(), "i.pdf").json()
    for metodo, ruta in (
        ("get", f"/api/entregas/{entrega['id']}"),
        ("get", f"/api/evidencias/{ev['id']}/archivo"),
        ("delete", f"/api/entregas/{entrega['id']}/evidencias/{ev['id']}"),
    ):
        assert getattr(cliente, metodo)(ruta, headers=h_est2).status_code == 404, ruta
    assert subir_repo(cliente, h_est2, entrega["id"], "https://github.com/a/b").status_code == 404
    # No aparece en su listado y el dueño sí la ve.
    assert cliente.get("/api/entregas", headers=h_est2).json() == []
    assert len(cliente.get("/api/entregas", headers=h_est1).json()) == 1


def test_listado_de_entregas_con_filtros_para_docente(cliente, h_docente, est1, est2, lab, storage):
    crear_entrega(cliente, h_docente, lab["id"], estudiante_id=est1.id)
    crear_entrega(cliente, h_docente, lab["id"], estudiante_id=est2.id)
    assert len(cliente.get("/api/entregas", headers=h_docente).json()) == 2
    assert len(cliente.get(f"/api/entregas?estudiante_id={est1.id}", headers=h_docente).json()) == 1
    assert len(cliente.get(f"/api/entregas?laboratorio_id={lab['id']}&estado=borrador", headers=h_docente).json()) == 2
    assert cliente.get("/api/entregas?estado=lista", headers=h_docente).json() == []


# ---------------------------------------------------------------- portafolio


def test_portafolio_con_ambas_cohortes(cliente, h_docente, h_est1, est1, est2, lab, storage):
    lab2 = crear_lab(cliente, h_docente, "C2-LAB01", cohorte=2)
    crear_entrega(cliente, h_est1, lab["id"])

    r = cliente.get("/api/portafolio", headers=h_est1)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estudiante"] == {"id": est1.id, "nombre": est1.nombre, "correo": "e1@u.co"}
    assert [c["cohorte"] for c in cuerpo["cohortes"]] == [1, 2]
    c1, c2 = cuerpo["cohortes"]
    assert c1["laboratorios"][0]["laboratorio"]["id"] == lab["id"]
    assert c1["laboratorios"][0]["entrega"]["estado"] == "borrador"
    assert "evidencias" not in c1["laboratorios"][0]["entrega"]
    assert c2["laboratorios"][0]["laboratorio"]["id"] == lab2["id"]
    assert c2["laboratorios"][0]["entrega"] is None

    # El estudiante ignora estudiante_id y ve siempre el propio.
    assert cliente.get(f"/api/portafolio?estudiante_id={est2.id}", headers=h_est1).json()["estudiante"]["id"] == est1.id
    # Docente: obligatorio y puede ver el de cualquiera, también con cohortes vacías.
    assert cliente.get("/api/portafolio", headers=h_docente).status_code == 400
    vacio = cliente.get(f"/api/portafolio?estudiante_id={est2.id}", headers=h_docente).json()
    assert [c["cohorte"] for c in vacio["cohortes"]] == [1, 2]
    assert all(item["entrega"] is None for c in vacio["cohortes"] for item in c["laboratorios"])


def test_portafolio_sin_laboratorios_trae_ambas_cohortes_vacias(cliente, h_est1):
    cuerpo = cliente.get("/api/portafolio", headers=h_est1).json()
    assert cuerpo["cohortes"] == [
        {"cohorte": 1, "laboratorios": []},
        {"cohorte": 2, "laboratorios": []},
    ]


# ---------------------------------------------------------------- evidencias


def test_pdf_valido_guarda_texto_detalle_hash_y_ruta(cliente, db, h_est1, entrega, storage):
    contenido = pdf_con_texto()
    r = subir(cliente, h_est1, entrega["id"], "informe_pdf", contenido, "../../Mi informe.pdf")
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["tipo"] == "informe_pdf"
    assert ev["nombre_original"] == "Mi informe.pdf"
    assert ev["sha256"] == hashlib.sha256(contenido).hexdigest()
    assert ev["tamano_bytes"] == len(contenido)
    assert ev["detalle"]["paginas"] == 1 and ev["detalle"]["caracteres_texto"] >= 200
    assert ev["url"] is None

    from app.models.entrega import Evidencia

    fila = db.get(Evidencia, ev["id"])
    assert fila.texto_extraido and "informe de laboratorio" in fila.texto_extraido
    assert fila.ruta_archivo.startswith(f"entregas/{entrega['id']}/") and fila.ruta_archivo.endswith(".pdf")
    assert "informe" not in fila.ruta_archivo.lower()  # nunca el nombre original
    assert (storage / fila.ruta_archivo).read_bytes() == contenido
    assert "evidencia_cargada" in acciones(db)


def test_segundo_pdf_409(cliente, h_est1, entrega, storage):
    assert subir(cliente, h_est1, entrega["id"], "informe_pdf", pdf_con_texto()).status_code == 201
    r = subir(cliente, h_est1, entrega["id"], "informe_pdf", pdf_con_texto())
    assert r.status_code == 409
    assert list((storage / "entregas" / str(entrega["id"])).iterdir()).__len__() == 1


def test_pdf_sin_texto_400_y_no_deja_archivo(cliente, h_est1, entrega, storage):
    r = subir(cliente, h_est1, entrega["id"], "informe_pdf", pdf_sin_texto(), "escaneo.pdf")
    assert r.status_code == 400
    assert "no tiene texto legible" in r.json()["detail"]
    carpeta = storage / "entregas" / str(entrega["id"])
    assert not carpeta.exists() or not list(carpeta.iterdir())


def test_extension_pdf_pero_contenido_no_pdf_400(cliente, h_est1, entrega, storage):
    r = subir(cliente, h_est1, entrega["id"], "informe_pdf", b"MZ esto es un ejecutable" * 50, "informe.pdf")
    assert r.status_code == 400
    r = subir(cliente, h_est1, entrega["id"], "imagen", pdf_con_texto(), "foto.png")
    assert r.status_code == 400
    assert subir(cliente, h_est1, entrega["id"], "informe_pdf", b"", "vacio.pdf").status_code == 400


def test_pdf_dañado_400(cliente, h_est1, entrega, storage):
    r = subir(cliente, h_est1, entrega["id"], "informe_pdf", b"%PDF-1.4\nbasura sin estructura", "x.pdf")
    assert r.status_code == 400


def test_zip_valido_detalle_y_no_se_extrae(cliente, h_est1, entrega, storage):
    datos = zip_bytes({"a.py": b"x=1", "b.py": b"y=2", "docs/leeme.md": b"hola", "datos/": b""})
    r = subir(cliente, h_est1, entrega["id"], "codigo_zip", datos, "codigo.zip")
    assert r.status_code == 201, r.text
    detalle = r.json()["detalle"]
    assert detalle["archivos"] == 3
    assert detalle["tamano_descomprimido_bytes"] == 3 + 3 + 4
    assert detalle["extensiones"] == {".py": 2, ".md": 1}
    archivos = [p for p in (storage / "entregas").rglob("*") if p.is_file()]
    assert len(archivos) == 1 and archivos[0].suffix == ".zip"


def test_zip_con_ruta_peligrosa_400(cliente, h_est1, entrega, storage):
    for nombre in ("../evil.py", "/etc/passwd", "a/../../b.py", "C:/x.py"):
        r = subir(cliente, h_est1, entrega["id"], "codigo_zip", zip_bytes({nombre: b"x"}), "c.zip")
        assert r.status_code == 400, nombre
        assert "rutas no permitidas" in r.json()["detail"]
    assert not [p for p in (storage / "entregas").rglob("*") if p.is_file()]


def test_zip_con_demasiadas_entradas_o_no_zip_400(cliente, h_est1, entrega, storage, monkeypatch):
    monkeypatch.setattr(svc, "MAX_ENTRADAS_ZIP", 2)
    r = subir(cliente, h_est1, entrega["id"], "codigo_zip", zip_bytes({"a": b"1", "b": b"2", "c": b"3"}))
    assert r.status_code == 400
    assert subir(cliente, h_est1, entrega["id"], "codigo_zip", b"PK\x03\x04 truncado").status_code == 400
    monkeypatch.setattr(svc, "MAX_DESCOMPRIMIDO_ZIP", 5)
    assert subir(cliente, h_est1, entrega["id"], "codigo_zip", zip_bytes({"a": b"123456789"})).status_code == 400


def test_tamano_excedido_413_aborta_y_borra_temporal(cliente, h_est1, entrega, storage, monkeypatch):
    monkeypatch.setitem(svc.REGLAS, svc.TipoEvidencia.imagen, svc.Regla(1024, svc.REGLAS[svc.TipoEvidencia.imagen].formatos))
    r = subir(cliente, h_est1, entrega["id"], "imagen", png_bytes(5000), "grande.png")
    assert r.status_code == 413
    carpeta = storage / "entregas" / str(entrega["id"])
    assert not carpeta.exists() or not list(carpeta.iterdir())
    assert subir(cliente, h_est1, entrega["id"], "imagen", png_bytes(500), "ok.png").status_code == 201


def test_limite_real_de_imagen_10mb_da_413(cliente, h_est1, entrega, storage):
    r = subir(cliente, h_est1, entrega["id"], "imagen", png_bytes(10 * 1024 * 1024), "enorme.png")
    assert r.status_code == 413


def test_repo_github_valido_e_invalido(cliente, h_est1, entrega, storage):
    for url, esperado in (
        ("https://github.com/octo-cat/mi_repo", ("octo-cat", "mi_repo")),
        ("https://github.com/octo-cat/mi.repo.git", ("octo-cat", "mi.repo")),
        ("https://github.com/octo-cat/otro/", ("octo-cat", "otro")),
    ):
        r = subir_repo(cliente, h_est1, entrega["id"], url)
        assert r.status_code == 201, url
        assert r.json()["detalle"] == {"owner": esperado[0], "repo": esperado[1]}
        assert r.json()["url"] == f"https://github.com/{esperado[0]}/{esperado[1]}"
        assert r.json()["sha256"] is None
    for malo in (
        "http://github.com/a/b",
        "https://gitlab.com/a/b",
        "https://github.com/a",
        "https://github.com/a/b/tree/main",
        "https://github.com/a/b?x=1",
        "https://evil.com/https://github.com/a/b",
        "no es una url",
        "",
    ):
        assert subir_repo(cliente, h_est1, entrega["id"], malo).status_code == 400, malo
    assert cliente.post(
        f"/api/entregas/{entrega['id']}/evidencias", headers=h_est1, data={"tipo": "repo_github"}
    ).status_code == 400


def test_tipo_invalido_y_archivo_faltante_400(cliente, h_est1, entrega, storage):
    assert subir(cliente, h_est1, entrega["id"], "exe", b"x").status_code == 400
    r = cliente.post(f"/api/entregas/{entrega['id']}/evidencias", headers=h_est1, data={"tipo": "imagen"})
    assert r.status_code == 400


def test_imagen_presentacion_y_video_por_firma(cliente, h_est1, entrega, storage):
    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 50
    mp4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 50
    webm = b"\x1a\x45\xdf\xa3" + b"\x00" * 50
    pptx = zip_bytes({"[Content_Types].xml": b"<x/>", "ppt/presentation.xml": b"<p/>"})
    assert subir(cliente, h_est1, entrega["id"], "imagen", png_bytes(), "a.txt").status_code == 201
    assert subir(cliente, h_est1, entrega["id"], "imagen", jpeg).status_code == 201
    assert subir(cliente, h_est1, entrega["id"], "video", mp4).status_code == 201
    assert subir(cliente, h_est1, entrega["id"], "video", webm).status_code == 201
    assert subir(cliente, h_est1, entrega["id"], "presentacion", pdf_bytes(["x"])).status_code == 201
    assert subir(cliente, h_est1, entrega["id"], "presentacion", pptx, "p.pptx").status_code == 201
    # Un ZIP cualquiera no es una presentación; un MP4 no es una imagen.
    assert subir(cliente, h_est1, entrega["id"], "presentacion", zip_bytes()).status_code == 400
    assert subir(cliente, h_est1, entrega["id"], "imagen", mp4).status_code == 400


def test_estado_borrador_lista_borrador_al_borrar(cliente, db, h_est1, entrega, storage):
    def estado():
        return cliente.get(f"/api/entregas/{entrega['id']}", headers=h_est1).json()

    assert estado()["estado"] == "borrador"
    pdf = subir(cliente, h_est1, entrega["id"], "informe_pdf", pdf_con_texto()).json()
    e = estado()
    assert e["estado"] == "borrador" and e["faltantes"] == ["codigo"]

    repo = subir_repo(cliente, h_est1, entrega["id"], "https://github.com/a/b").json()
    e = estado()
    assert e["estado"] == "lista" and e["faltantes"] == [] and len(e["evidencias"]) == 2

    r = cliente.delete(f"/api/entregas/{entrega['id']}/evidencias/{repo['id']}", headers=h_est1)
    assert r.status_code == 204
    assert estado()["estado"] == "borrador" and estado()["faltantes"] == ["codigo"]

    # Con ZIP en lugar de repo también queda lista; y borrar el PDF borra el archivo físico.
    assert subir(cliente, h_est1, entrega["id"], "codigo_zip", zip_bytes()).status_code == 201
    assert estado()["estado"] == "lista"
    from app.models.entrega import Evidencia

    ruta = storage / db.get(Evidencia, pdf["id"]).ruta_archivo
    assert ruta.is_file()
    assert cliente.delete(f"/api/entregas/{entrega['id']}/evidencias/{pdf['id']}", headers=h_est1).status_code == 204
    assert not ruta.exists()
    assert estado()["estado"] == "borrador" and estado()["faltantes"] == ["informe_pdf"]
    # Tras borrar se puede volver a subir un PDF.
    assert subir(cliente, h_est1, entrega["id"], "informe_pdf", pdf_con_texto()).status_code == 201
    assert acciones(db).count("evidencia_eliminada") == 2


def test_borrar_evidencia_inexistente_o_de_otra_entrega_404(cliente, h_est1, h_docente, entrega, lab, est2, storage):
    otra = crear_entrega(cliente, h_docente, lab["id"], estudiante_id=est2.id).json()
    ev = subir(cliente, h_docente, otra["id"], "imagen", png_bytes()).json()
    assert cliente.delete(f"/api/entregas/{entrega['id']}/evidencias/{ev['id']}", headers=h_est1).status_code == 404
    assert cliente.delete(f"/api/entregas/{entrega['id']}/evidencias/999", headers=h_est1).status_code == 404


def test_no_se_modifican_evidencias_si_la_entrega_esta_en_evaluacion(cliente, db, h_est1, entrega, storage):
    ev = subir(cliente, h_est1, entrega["id"], "imagen", png_bytes()).json()
    from app.models.entrega import Entrega

    fila = db.get(Entrega, entrega["id"])
    fila.estado = "en_evaluacion"
    db.commit()
    assert subir(cliente, h_est1, entrega["id"], "imagen", png_bytes()).status_code == 409
    assert cliente.delete(f"/api/entregas/{entrega['id']}/evidencias/{ev['id']}", headers=h_est1).status_code == 409


def test_docente_carga_evidencia_en_entrega_de_estudiante(cliente, h_docente, entrega, storage):
    assert subir(cliente, h_docente, entrega["id"], "imagen", png_bytes()).status_code == 201


# ---------------------------------------------------------------- descarga


def test_descarga_autorizada_con_nombre_saneado(cliente, h_est1, h_docente, h_est2, entrega, storage):
    contenido = pdf_con_texto()
    ev = subir(cliente, h_est1, entrega["id"], "informe_pdf", contenido, "a/b\\informe final.pdf").json()
    for h in (h_est1, h_docente):
        r = cliente.get(f"/api/evidencias/{ev['id']}/archivo", headers=h)
        assert r.status_code == 200
        assert r.content == contenido
        disposicion = r.headers["content-disposition"]
        assert disposicion.startswith("attachment")
        assert unquote(disposicion).endswith("filename*=utf-8''informe final.pdf")
    assert cliente.get(f"/api/evidencias/{ev['id']}/archivo", headers=h_est2).status_code == 404
    assert cliente.get(f"/api/evidencias/{ev['id']}/archivo").status_code == 401
    assert cliente.get("/api/evidencias/999/archivo", headers=h_docente).status_code == 404


def test_descarga_de_repo_no_tiene_archivo_404(cliente, h_est1, entrega, storage):
    ev = subir_repo(cliente, h_est1, entrega["id"], "https://github.com/a/b").json()
    assert cliente.get(f"/api/evidencias/{ev['id']}/archivo", headers=h_est1).status_code == 404


def test_nombre_seguro():
    assert svc.nombre_seguro("../../x/y.pdf", ".pdf") == "y.pdf"
    assert svc.nombre_seguro("a\\b\\c.zip", ".zip") == "c.zip"
    assert svc.nombre_seguro(None, ".png") == "archivo.png"
    assert svc.nombre_seguro("..", ".png") == "archivo.png"
    assert svc.nombre_seguro("a\x00b\n.pdf", ".pdf") == "ab.pdf"

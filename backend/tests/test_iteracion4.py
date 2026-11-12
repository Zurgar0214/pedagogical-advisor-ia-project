# ruff: noqa: F811, F401
"""Iteración 4: informe integral (RF-09), mapa mental (RF-10) y PDF.

La síntesis con IA se sustituye por un doble (`sintetizar` devuelve un `ResultadoSintesis` armado
a mano): estas pruebas no dependen de `app.evaluacion`.
"""

import io

import pytest
from pypdf import PdfReader
from sqlalchemy import select

from app.api.deps import get_session_factory
from app.evaluacion import informe as sintesis_mod
from app.evaluacion import servicio
from app.evaluacion.contrato import Aprendizaje, ErrorEvaluacion, UsoModelo
from app.evaluacion.informe import ResultadoSintesis
from app.informes.contrato import (
    AccionPlan,
    AgregadoInforme,
    ClasificacionTema,
    RelacionTemas,
    SintesisInforme,
)
from app.main import app
from app.models.auditoria import Auditoria
from app.models.informe import Informe
from app.models.usuario import Usuario
from tests.test_iteracion2 import (
    acciones,
    crear_entrega,
    crear_lab,
    crear_version,
    est1,
    est2,
    h_docente,
    h_est1,
    h_est2,
    storage,
    subir,
)
from tests.test_iteracion3 import NIVELES_IA, ajustar, evaluar_entrega, resultado_falso
from tests.utiles import pdf_con_texto, zip_bytes

CAMPOS_INTERNOS = {"uso", "costo_usd_estimado", "advertencias"}


def sintesis_falsa(agregado: AgregadoInforme, relaciones=True) -> ResultadoSintesis:
    temas = [t.tema for t in agregado.temas]
    return ResultadoSintesis(
        sintesis=SintesisInforme(
            resumen="Resumen del progreso con acentos: razón, diseño y ñandú.",
            evolucion="Evolución estable.",
            plan=[
                AccionPlan(
                    prioridad=1,
                    tema=temas[0] if temas else "general",
                    objetivo="Mejorar",
                    actividades=["Practicar", "Revisar"],
                    recursos=["Libro"],
                    indicador_logro="Nota mayor a 4",
                    plazo_semanas=4,
                )
            ],
            clasificacion=[
                ClasificacionTema(tema=t, categoria="Aprendizaje supervisado") for t in temas
            ],
            relaciones=[
                RelacionTemas(
                    origen=temas[0], destino=temas[1], tipo="complementa", explicacion="se apoyan"
                )
            ]
            if relaciones and len(temas) > 1
            else [],
        ),
        uso=[
            UsoModelo(
                proveedor="falso", modelo="m-informe", proposito="informe", costo_usd_estimado=0.003
            )
        ],
        advertencias=["Advertencia interna del informe"],
        proveedor="falso",
        modelo="m-informe",
        version_prompt="informe-test",
    )


@pytest.fixture
def pipeline4(monkeypatch, fabrica_sesion):
    """Dobles del pipeline de evaluación y de la síntesis; registra los agregados recibidos."""
    visto = {"agregados": [], "falla": None}

    def evaluar(contexto, settings):
        r = resultado_falso(contexto, NIVELES_IA)
        r.resultado.aprendizajes = [
            Aprendizaje(
                tema="Regresión",
                que_aprendio="Ajustar modelos",
                como_aplico="En el laboratorio",
                que_fortalecer="Validación",
                nivel_dominio="competente",
                criterios_relacionados=["k1", "k2"],
            )
        ]
        return r

    def sintetizar(agregado, settings):
        visto["agregados"].append(agregado)
        if visto["falla"] is not None:
            raise visto["falla"]
        return sintesis_falsa(agregado)

    monkeypatch.setattr(servicio, "evaluar", evaluar)
    monkeypatch.setattr(sintesis_mod, "sintetizar", sintetizar)
    app.dependency_overrides[get_session_factory] = lambda: fabrica_sesion
    return visto


def crear_lab_con_rubrica(cliente, h_docente, codigo, cohorte=1, temas=("regresión",)):
    r = cliente.post(
        "/api/laboratorios",
        headers=h_docente,
        json={
            "cohorte": cohorte,
            "codigo": codigo,
            "titulo": f"Laboratorio {codigo}",
            "descripcion": "d",
            "objetivos": "o",
            "temas": list(temas),
        },
    )
    assert r.status_code == 201, r.text
    lab = r.json()
    assert crear_version(cliente, h_docente, lab["id"]).status_code == 201
    return lab


def evaluar_y_avanzar(cliente, h_docente, entrega_id, hasta="publicada", ajuste=None):
    """Evalúa la entrega y la lleva a `aprobada` o `publicada`."""
    r = evaluar_entrega(cliente, h_docente, entrega_id)
    assert r.status_code == 202, r.text
    eid = r.json()["id"]
    if ajuste:
        assert ajustar(cliente, h_docente, eid, **ajuste).status_code == 200
    assert cliente.post(f"/api/evaluaciones/{eid}/aprobar", headers=h_docente).status_code == 200
    if hasta == "publicada":
        assert (
            cliente.post(f"/api/evaluaciones/{eid}/publicar", headers=h_docente).status_code == 200
        )
    return eid


def entrega_con_evidencias(cliente, h_est, lab_id):
    e = crear_entrega(cliente, h_est, lab_id).json()
    assert (
        subir(cliente, h_est, e["id"], "informe_pdf", pdf_con_texto(), "i.pdf").status_code == 201
    )
    assert subir(cliente, h_est, e["id"], "codigo_zip", zip_bytes(), "c.zip").status_code == 201
    return e["id"]


def publicar_lab(cliente, h_docente, h_est, lab_id, **kw):
    return evaluar_y_avanzar(
        cliente, h_docente, entrega_con_evidencias(cliente, h_est, lab_id), **kw
    )


@pytest.fixture
def lab1(cliente, h_docente):
    return crear_lab_con_rubrica(cliente, h_docente, "C1-LAB01", 1, ("regresión", "Clasificación"))


@pytest.fixture
def eval_publicada(cliente, h_docente, h_est1, lab1, storage, pipeline4):
    return publicar_lab(cliente, h_docente, h_est1, lab1["id"])


def generar(cliente, h, estudiante_id):
    return cliente.post(f"/api/estudiantes/{estudiante_id}/informes", headers=h)


def informe_listo(cliente, h_docente, est1, eval_publicada):
    r = generar(cliente, h_docente, est1.id)
    assert r.status_code == 202, r.text
    iid = r.json()["id"]
    g = cliente.get(f"/api/informes/{iid}", headers=h_docente)
    assert g.json()["estado"] == "listo", g.text
    return iid


# ---------------------------------------------------------------- flujo completo


def test_flujo_completo(cliente, db, h_docente, est1, eval_publicada, pipeline4):
    r = generar(cliente, h_docente, est1.id)
    assert r.status_code == 202, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "procesando"
    assert cuerpo["evaluaciones_incluidas"] == [eval_publicada]
    assert cuerpo["estudiante"]["id"] == est1.id

    g = cliente.get(f"/api/informes/{cuerpo['id']}", headers=h_docente).json()
    assert g["estado"] == "listo" and g["error"] is None
    assert g["estudiante"] == {"id": est1.id, "nombre": est1.nombre, "correo": "e1@u.co"}
    assert g["evaluaciones_incluidas"] == [eval_publicada]
    assert g["proveedor"] == "falso" and g["modelo"] == "m-informe"
    assert g["version_prompt"] == "informe-test"
    assert g["advertencias"] == ["Advertencia interna del informe"]
    assert g["uso"][0]["modelo"] == "m-informe" and g["costo_usd_estimado"] == 0.003
    assert g["sintesis"]["resumen"].startswith("Resumen del progreso")
    ag = g["agregado"]
    assert ag["estudiante"] == est1.nombre
    assert ag["laboratorios"][0]["codigo"] == "C1-LAB01"
    assert ag["laboratorios"][0]["nota_final"] == 2.6  # 0.4*5 + 0.6*1, calculada por el backend
    assert ag["promedio_general"] == 2.6
    assert [t["tema"] for t in ag["temas"]] == ["clasificación", "regresión"]
    assert g["temas_categoria"] == {
        "clasificación": "Aprendizaje supervisado",
        "regresión": "Aprendizaje supervisado",
    }
    # Aprendizaje de regresión: k1=Alto(5), k2=Bajo(1) -> 3.0; clasificación sin aprendizajes
    temas = {t["tema"]: t for t in ag["temas"]}
    assert temas["regresión"]["promedio"] == 3.0
    assert temas["clasificación"]["nivel_dominio"] is None
    # El agregado que recibió la IA es el mismo que se guardó
    assert pipeline4["agregados"][0].model_dump(mode="json") == ag

    lista = cliente.get(f"/api/estudiantes/{est1.id}/informes", headers=h_docente).json()
    assert lista == [
        {
            "id": cuerpo["id"],
            "estado": "listo",
            "generado_en": g["generado_en"],
            "evaluaciones_incluidas": [eval_publicada],
            "promedio_general": 2.6,
        }
    ]
    assert {"informe_iniciado", "informe_generado"} <= set(acciones(db))


def test_lista_mas_reciente_primero(cliente, h_docente, est1, eval_publicada):
    a = generar(cliente, h_docente, est1.id).json()["id"]
    b = generar(cliente, h_docente, est1.id).json()["id"]
    ids = [
        i["id"]
        for i in cliente.get(f"/api/estudiantes/{est1.id}/informes", headers=h_docente).json()
    ]
    assert ids == [b, a]


def test_sin_publicadas_400(cliente, h_docente, h_est1, est1, lab1, storage, pipeline4):
    r = generar(cliente, h_docente, est1.id)
    assert r.status_code == 400
    assert "publicadas" in r.json()["detail"]
    assert cliente.get(f"/api/estudiantes/{est1.id}/informes", headers=h_docente).json() == []


def test_solo_cuentan_evaluaciones_publicadas(
    cliente, h_docente, h_est1, est1, lab1, storage, pipeline4
):
    publicada = publicar_lab(cliente, h_docente, h_est1, lab1["id"])
    lab2 = crear_lab_con_rubrica(cliente, h_docente, "C1-LAB02", 1, ("redes",))
    aprobada = publicar_lab(cliente, h_docente, h_est1, lab2["id"], hasta="aprobada")
    lab3 = crear_lab_con_rubrica(cliente, h_docente, "C2-LAB01", 2, ("nlp",))
    en_revision = evaluar_entrega(
        cliente, h_docente, entrega_con_evidencias(cliente, h_est1, lab3["id"])
    ).json()["id"]

    iid = generar(cliente, h_docente, est1.id).json()["id"]
    g = cliente.get(f"/api/informes/{iid}", headers=h_docente).json()
    assert g["estado"] == "listo"
    assert g["evaluaciones_incluidas"] == [publicada]
    assert (
        aprobada not in g["evaluaciones_incluidas"]
        and en_revision not in g["evaluaciones_incluidas"]
    )
    assert [lab["codigo"] for lab in g["agregado"]["laboratorios"]] == ["C1-LAB01"]
    assert g["agregado"]["laboratorios_totales"] == 3
    # Los temas de los laboratorios aún sin publicar quedan «sin evidencia»
    temas = {t["tema"]: t for t in g["agregado"]["temas"]}
    assert temas["redes"]["nivel_dominio"] is None and temas["redes"][
        "laboratorios_sin_evidencia"
    ] == ["C1-LAB02"]
    assert {b["nombre"] for b in g["agregado"]["brechas"] if b["tipo"] == "sin_evidencia"} >= {
        "redes",
        "nlp",
    }


def test_solo_aprobada_sin_publicar_da_400(
    cliente, h_docente, h_est1, est1, lab1, storage, pipeline4
):
    publicar_lab(cliente, h_docente, h_est1, lab1["id"], hasta="aprobada")
    assert generar(cliente, h_docente, est1.id).status_code == 400


def test_la_mas_reciente_por_entrega(cliente, h_docente, h_est1, est1, lab1, storage, pipeline4):
    entrega_id = entrega_con_evidencias(cliente, h_est1, lab1["id"])
    primera = evaluar_y_avanzar(cliente, h_docente, entrega_id)
    segunda = evaluar_y_avanzar(cliente, h_docente, entrega_id, ajuste={"nivel": "Alto"})
    iid = generar(cliente, h_docente, est1.id).json()["id"]
    g = cliente.get(f"/api/informes/{iid}", headers=h_docente).json()
    assert g["evaluaciones_incluidas"] == [segunda] and primera != segunda
    assert len(g["agregado"]["laboratorios"]) == 1
    assert g["agregado"]["laboratorios"][0]["evaluacion_id"] == segunda


def test_ajustes_docentes_se_respetan(cliente, h_docente, h_est1, est1, lab1, storage, pipeline4):
    # La IA dio k2=Bajo (nota 2.6); el docente lo sube a Alto: nota final 5.0
    publicar_lab(cliente, h_docente, h_est1, lab1["id"], ajuste={"criterio": "k2", "nivel": "Alto"})
    iid = generar(cliente, h_docente, est1.id).json()["id"]
    ag = cliente.get(f"/api/informes/{iid}", headers=h_docente).json()["agregado"]
    assert ag["laboratorios"][0]["nota_final"] == 5.0
    assert ag["competencias"][0]["promedio"] == 5.0
    assert ag["competencias"][0]["nivel_dominio"] == "avanzado"
    assert {t["tema"]: t for t in ag["temas"]}["regresión"]["promedio"] == 5.0
    assert not [b for b in ag["brechas"] if b["tipo"] == "criterio"]


def test_409_si_ya_hay_uno_procesando(cliente, db, h_docente, est1, eval_publicada):
    db.add(Informe(estudiante_id=est1.id, estado="procesando", generado_por=est1.id))
    db.commit()
    assert generar(cliente, h_docente, est1.id).status_code == 409


# ---------------------------------------------------------------- permisos y vista recortada


def test_estudiante_genera_el_suyo_y_no_el_de_otro(
    cliente, db, h_docente, h_est1, h_est2, est1, est2, eval_publicada
):
    otro = generar(cliente, h_est1, est2.id)
    assert otro.status_code == 404
    propio = generar(cliente, h_est1, est1.id)
    assert propio.status_code == 202
    assert propio.json()["generado_por"]["id"] == est1.id
    # el otro estudiante tampoco puede verlo, listarlo, ni descargarlo
    iid = propio.json()["id"]
    assert cliente.get(f"/api/informes/{iid}", headers=h_est2).status_code == 404
    assert cliente.get(f"/api/informes/{iid}/mapa", headers=h_est2).status_code == 404
    assert cliente.get(f"/api/informes/{iid}/pdf", headers=h_est2).status_code == 404
    assert cliente.get(f"/api/estudiantes/{est1.id}/informes", headers=h_est2).status_code == 404
    # el propio estudiante sí
    assert cliente.get(f"/api/informes/{iid}", headers=h_est1).status_code == 200
    assert len(cliente.get(f"/api/estudiantes/{est1.id}/informes", headers=h_est1).json()) == 1


def test_requiere_autenticacion_y_estudiante_valido(cliente, db, h_docente, est1, eval_publicada):
    assert cliente.post(f"/api/estudiantes/{est1.id}/informes").status_code == 401
    assert cliente.get("/api/informes/1").status_code == 401
    assert generar(cliente, h_docente, 9999).status_code == 404
    docente = db.scalar(select(Usuario).where(Usuario.correo == "doc@u.co"))
    assert generar(cliente, h_docente, docente.id).status_code == 404  # no es estudiante
    assert cliente.get("/api/informes/9999", headers=h_docente).status_code == 404


def test_vista_recortada_para_estudiante(cliente, h_docente, h_est1, est1, eval_publicada):
    iid = generar(cliente, h_est1, est1.id).json()["id"]
    estudiante = cliente.get(f"/api/informes/{iid}", headers=h_est1).json()
    docente = cliente.get(f"/api/informes/{iid}", headers=h_docente).json()
    assert CAMPOS_INTERNOS <= set(docente)
    assert not CAMPOS_INTERNOS & set(estudiante)
    assert estudiante["estado"] == "listo" and estudiante["agregado"] and estudiante["sintesis"]
    # también en la respuesta del POST
    nuevo = generar(cliente, h_est1, est1.id).json()
    assert not CAMPOS_INTERNOS & set(nuevo)
    assert CAMPOS_INTERNOS <= set(generar(cliente, h_docente, est1.id).json())
    assert "Advertencia interna" not in str(estudiante)


# ---------------------------------------------------------------- mapa


def test_mapa_coherente(cliente, h_docente, h_est1, est1, eval_publicada):
    iid = informe_listo(cliente, h_docente, est1, eval_publicada)
    r = cliente.get(f"/api/informes/{iid}/mapa", headers=h_docente)
    assert r.status_code == 200, r.text
    mapa = r.json()
    assert mapa["informe_id"] == iid and mapa["estudiante"] == {
        "id": est1.id,
        "nombre": est1.nombre,
    }
    nodos = {n["id"]: n for n in mapa["nodos"]}
    assert len(nodos) == len(mapa["nodos"])
    assert nodos["raiz"]["tipo"] == "raiz"
    assert {
        "cat:aprendizaje-supervisado",
        "tema:regresion",
        "tema:clasificacion",
        "lab:C1-LAB01",
    } <= set(nodos)
    padre = {}
    for a in mapa["aristas"]:
        assert a["origen"] in nodos and a["destino"] in nodos
        if a["tipo"] != "relacion":
            padre[a["destino"]] = a["origen"]
    assert padre["tema:regresion"] == "cat:aprendizaje-supervisado"
    assert padre["tema:clasificacion"] == "cat:aprendizaje-supervisado"
    assert padre["cat:aprendizaje-supervisado"] == "raiz"
    assert padre["lab:C1-LAB01"] == "tema:regresion"
    assert all(n["id"] in padre for n in mapa["nodos"] if n["tipo"] != "raiz")  # sin huérfanos
    assert nodos["lab:C1-LAB01"]["datos"]["nota_final"] == 2.6
    assert nodos["tema:regresion"]["nivel_dominio"] == "basico"  # 3.0
    assert nodos["tema:clasificacion"]["datos"]["sin_evidencia"] is True
    relacion = [a for a in mapa["aristas"] if a["tipo"] == "relacion"]
    assert len(relacion) == 1 and relacion[0]["etiqueta"] == "complementa: se apoyan"
    # el estudiante dueño también lo ve
    assert cliente.get(f"/api/informes/{iid}/mapa", headers=h_est1).status_code == 200


def test_mapa_y_pdf_409_si_no_esta_listo(cliente, db, h_docente, est1, eval_publicada):
    informe = Informe(estudiante_id=est1.id, estado="procesando", generado_por=est1.id)
    fallido = Informe(estudiante_id=est1.id, estado="error", error="x", generado_por=est1.id)
    db.add_all([informe, fallido])
    db.commit()
    for i in (informe, fallido):
        assert cliente.get(f"/api/informes/{i.id}/mapa", headers=h_docente).status_code == 409
        assert cliente.get(f"/api/informes/{i.id}/pdf", headers=h_docente).status_code == 409


# ---------------------------------------------------------------- PDF


def test_pdf(cliente, db, h_docente, h_est1, est1, eval_publicada):
    est = db.get(Usuario, est1.id)
    est.nombre = "José Peña Núñez"
    db.commit()
    iid = informe_listo(cliente, h_docente, est1, eval_publicada)
    r = cliente.get(f"/api/informes/{iid}/pdf", headers=h_docente)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("attachment")
    assert f"informe-{iid}.pdf" in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF")
    texto = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(r.content)).pages)
    assert "José Peña Núñez" in texto
    assert "razón, diseño y ñandú" in texto  # tildes y ñ del resumen
    assert "C1-LAB01" in texto and "2.60" in texto
    assert "Plan de fortalecimiento" in texto and "Brechas" in texto
    assert (
        "Generado con apoyo de IA; notas calculadas por el sistema y aprobadas por el docente"
        in texto
    )
    # el estudiante dueño también puede descargarlo
    assert cliente.get(f"/api/informes/{iid}/pdf", headers=h_est1).status_code == 200


def test_pdf_con_caracteres_raros_no_revienta():
    """Caracteres fuera de Latin-1, XML y muchos temas no deben romper la generación."""
    from app.informes.agregacion import normalizar_tema
    from app.informes.contrato import TemaAgregado
    from app.informes.pdf import generar_pdf

    agregado = AgregadoInforme(
        estudiante="<Ana & «Co»>",
        laboratorios_totales=1,
        laboratorios=[],
        promedio_general=0,
        promedio_cohorte={},
        nivel_general="inicial",
        competencias=[],
        temas=[
            TemaAgregado(
                tema=normalizar_tema("Tema → <b>raro</b> 😀"),
                nivel_dominio=None,
                promedio=None,
                laboratorios=[],
            )
        ],
        tendencia=None,
        brechas=[],
    )
    sintesis = sintesis_falsa(agregado).sintesis
    pdf = generar_pdf("<Ana & «Co»>", "2026-11-12T10:00:00+00:00", agregado, sintesis, {})
    assert pdf.startswith(b"%PDF")


# ---------------------------------------------------------------- errores de síntesis


def test_error_de_sintesis_deja_el_informe_en_error(
    cliente, db, h_docente, est1, eval_publicada, pipeline4
):
    pipeline4["falla"] = ErrorEvaluacion("El proveedor de IA no respondió.")
    r = generar(cliente, h_docente, est1.id)
    assert r.status_code == 202
    g = cliente.get(f"/api/informes/{r.json()['id']}", headers=h_docente).json()
    assert g["estado"] == "error" and g["error"] == "El proveedor de IA no respondió."
    assert g["sintesis"] is None and g["agregado"] is None
    fallo = db.scalar(select(Auditoria).where(Auditoria.accion == "informe_fallido"))
    assert fallo is not None and fallo.entidad_id == g["id"]
    assert cliente.get(f"/api/informes/{g['id']}/mapa", headers=h_docente).status_code == 409
    # tras el error se puede volver a generar
    pipeline4["falla"] = None
    nuevo = generar(cliente, h_docente, est1.id)
    assert nuevo.status_code == 202
    assert (
        cliente.get(f"/api/informes/{nuevo.json()['id']}", headers=h_docente).json()["estado"]
        == "listo"
    )


def test_excepcion_inesperada_mensaje_generico(cliente, h_docente, est1, eval_publicada, pipeline4):
    pipeline4["falla"] = RuntimeError("traza interna secreta")
    iid = generar(cliente, h_docente, est1.id).json()["id"]
    g = cliente.get(f"/api/informes/{iid}", headers=h_docente).json()
    assert g["estado"] == "error"
    assert "traza interna" not in g["error"] and "error interno" in g["error"]

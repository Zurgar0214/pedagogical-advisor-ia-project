# ruff: noqa: F811
"""Iteración 3: API de evaluaciones y revisión docente (RF-06/07/08, RNF-07).

El pipeline de IA se sustituye por un doble (`evaluar` devuelve un `ResultadoEvaluacion` armado
a mano): estas pruebas no dependen de `app.evaluacion`.
"""

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.api.deps import get_session_factory
from app.core.config import get_settings
from app.evaluacion import servicio
from app.evaluacion.contrato import (
    ErrorEvaluacion,
    EvaluacionCriterio,
    EvidenciaCitada,
    ResultadoEvaluacion,
    ResultadoIA,
    UsoModelo,
    VerificacionTecnica,
)
from app.main import app
from app.models.auditoria import Auditoria
from app.models.entrega import Entrega
from app.models.evaluacion import AjusteCriterio, Evaluacion
from app.schemas.rubrica import Rubrica
from app.services.calculo_nota import calcular_nota
from tests.conftest import cabecera, crear_usuario
from tests.test_iteracion2 import (  # noqa: F401  (fixtures reutilizados)
    acciones,
    crear_entrega,
    crear_lab,
    crear_version,
    est1,
    est2,
    h_docente,
    h_est1,
    h_est2,
    rubrica_json,
    storage,
    subir,
)
from tests.utiles import pdf_con_texto, zip_bytes

NIVELES_IA = {"k1": "Alto", "k2": "Bajo"}  # 0.4*5 + 0.6*1 = 2.6

CAMPOS_INTERNOS = {"uso", "costo_usd_estimado", "nota_preliminar", "advertencias"}
CAMPOS_INTERNOS_CRITERIO = {"confianza", "nivel_ia"}


def resultado_falso(contexto, niveles=None) -> ResultadoEvaluacion:
    niveles = niveles or {c.id: c.niveles[0].nombre for c in contexto.rubrica.criterios}
    criterios = [
        EvaluacionCriterio(
            criterio_id=cid,
            nivel=nivel,
            confianza=0.8,
            justificacion=f"Justificación de {cid}",
            evidencias=[EvidenciaCitada(evidencia_id=1, fuente="informe_pdf", fragmento="cita")],
            fortalezas=["f"],
            modelo="modelo-falso",
        )
        for cid, nivel in niveles.items()
    ]
    return ResultadoEvaluacion(
        resultado=ResultadoIA(criterios=criterios, resumen="Resumen de la IA", fortalezas=["F"]),
        verificacion=VerificacionTecnica(archivos_analizados=3),
        niveles_elegidos=niveles,
        uso=[
            UsoModelo(proveedor="falso", modelo="modelo-falso", proposito="evaluacion", costo_usd_estimado=0.004),
            UsoModelo(proveedor="falso", modelo="modelo-falso", proposito="escalamiento", costo_usd_estimado=0.002),
        ],
        proveedor="falso",
        modelo_principal="modelo-falso",
        requiere_revision=True,
        advertencias=["Advertencia interna"],
        version_prompt="eval-test",
    )


@pytest.fixture
def pipeline(monkeypatch, fabrica_sesion):
    """Sustituye el pipeline y la fábrica de sesiones; registra los contextos recibidos."""
    visto = {"contextos": [], "falla": None}

    def evaluar(contexto, settings):
        visto["contextos"].append(contexto)
        if visto["falla"] is not None:
            raise visto["falla"]
        return resultado_falso(contexto, NIVELES_IA)

    monkeypatch.setattr(servicio, "evaluar", evaluar)
    monkeypatch.setattr(servicio, "estado_proveedor", lambda settings: (True, "Listo."))
    app.dependency_overrides[get_session_factory] = lambda: fabrica_sesion
    return visto


@pytest.fixture
def entrega_lista(cliente, h_est1, lab, storage):  # noqa: F811
    e = crear_entrega(cliente, h_est1, lab["id"]).json()
    assert subir(cliente, h_est1, e["id"], "informe_pdf", pdf_con_texto(), "i.pdf").status_code == 201
    assert subir(cliente, h_est1, e["id"], "codigo_zip", zip_bytes(), "c.zip").status_code == 201
    return cliente.get(f"/api/entregas/{e['id']}", headers=h_est1).json()


@pytest.fixture
def lab(cliente, h_docente):  # noqa: F811
    lab = crear_lab(cliente, h_docente)
    assert crear_version(cliente, h_docente, lab["id"]).status_code == 201
    return lab


def evaluar_entrega(cliente, h_docente, entrega_id):
    return cliente.post(f"/api/entregas/{entrega_id}/evaluaciones", headers=h_docente)


@pytest.fixture
def evaluacion(cliente, h_docente, entrega_lista, pipeline):
    r = evaluar_entrega(cliente, h_docente, entrega_lista["id"])
    assert r.status_code == 202, r.text
    return r.json()


def obtener(cliente, h, evaluacion_id):
    return cliente.get(f"/api/evaluaciones/{evaluacion_id}", headers=h)


def ajustar(cliente, h, evaluacion_id, criterio="k2", nivel="Alto", justificacion="Justificación suficiente"):
    return cliente.patch(
        f"/api/evaluaciones/{evaluacion_id}/criterios/{criterio}",
        headers=h,
        json={"nivel": nivel, "justificacion": justificacion},
    )


# ---------------------------------------------------------------- flujo completo (RF-06/07)


def test_flujo_completo_nota_calculada_por_el_backend(cliente, db, h_docente, entrega_lista, pipeline):
    r = evaluar_entrega(cliente, h_docente, entrega_lista["id"])
    assert r.status_code == 202
    # La respuesta describe el estado al crear; el pipeline corre después (segundo plano).
    assert r.json()["estado"] == "procesando"
    assert r.json()["criterios"] == []

    ev = obtener(cliente, h_docente, r.json()["id"]).json()
    assert ev["estado"] == "en_revision"
    assert ev["error"] is None
    esperado = calcular_nota(Rubrica.model_validate(rubrica_json()), NIVELES_IA).nota
    assert Decimal(str(ev["nota_preliminar"])) == esperado == Decimal("2.6")
    assert ev["nota_final"] == ev["nota_preliminar"]
    assert ev["proveedor"] == "falso"
    assert ev["modelo_principal"] == "modelo-falso"
    assert ev["version_prompt"] == "eval-test"
    assert ev["requiere_revision"] is True
    assert ev["advertencias"] == ["Advertencia interna"]
    assert ev["costo_usd_estimado"] == pytest.approx(0.006)
    assert len(ev["uso"]) == 2
    assert ev["resumen"] == "Resumen de la IA"
    assert ev["verificacion"]["archivos_analizados"] == 3
    assert ev["rubrica_version"]["numero"] == 1

    k1 = ev["criterios"][0]
    assert (k1["criterio_id"], k1["criterio"], k1["competencia"], k1["peso"]) == (
        "k1", "Criterio 1", "Competencia 1", 40,
    )
    assert [n["nombre"] for n in k1["niveles_disponibles"]] == ["Bajo", "Alto"]
    assert k1["nivel_ia"] == k1["nivel_final"] == "Alto"
    assert k1["valor_nivel_final"] == 5
    assert k1["confianza"] == 0.8
    assert k1["ajuste_docente"] is None

    fila = db.get(Evaluacion, ev["id"])
    assert fila.parametros["umbral_confianza"] == get_settings().ia_umbral_confianza
    assert fila.modelo_escalamiento == get_settings().ia_modelo_escalamiento
    assert db.get(Entrega, entrega_lista["id"]).estado == "evaluada"
    assert {"evaluacion_iniciada", "evaluacion_finalizada"} <= set(acciones(db))


def test_contexto_con_rutas_absolutas_y_evidencias(cliente, h_docente, entrega_lista, pipeline, storage):
    evaluar_entrega(cliente, h_docente, entrega_lista["id"])
    (contexto,) = pipeline["contextos"]
    assert contexto.laboratorio.codigo == "C1-LAB01"
    assert len(contexto.evidencias) == 2
    pdf = next(e for e in contexto.evidencias if e.tipo == "informe_pdf")
    assert pdf.texto_extraido
    ruta = pdf.ruta_archivo
    assert ruta.startswith(str(storage.resolve()))
    assert Path(ruta).is_absolute()


def test_la_nota_no_viene_del_llm(cliente, h_docente, entrega_lista, monkeypatch, pipeline):
    """Aunque el doble intente colar una nota, el backend usa solo `niveles_elegidos`."""
    base = servicio.evaluar

    def con_nota_falsa(contexto, settings):
        res = base(contexto, settings)
        res.resultado.resumen = "Mi nota es 5.0"
        return res

    monkeypatch.setattr(servicio, "evaluar", con_nota_falsa)
    r = evaluar_entrega(cliente, h_docente, entrega_lista["id"])
    assert obtener(cliente, h_docente, r.json()["id"]).json()["nota_preliminar"] == 2.6


def test_error_del_pipeline_deja_error_y_entrega_lista(cliente, db, h_docente, entrega_lista, pipeline):
    pipeline["falla"] = ErrorEvaluacion("El proveedor de IA no respondió.")
    r = evaluar_entrega(cliente, h_docente, entrega_lista["id"])
    ev = obtener(cliente, h_docente, r.json()["id"]).json()
    assert ev["estado"] == "error"
    assert ev["error"] == "El proveedor de IA no respondió."
    assert ev["nota_preliminar"] is None
    assert db.get(Entrega, entrega_lista["id"]).estado == "lista"
    assert "evaluacion_fallida" in acciones(db)
    # Se puede reintentar.
    pipeline["falla"] = None
    r2 = evaluar_entrega(cliente, h_docente, entrega_lista["id"])
    assert r2.status_code == 202
    assert obtener(cliente, h_docente, r2.json()["id"]).json()["estado"] == "en_revision"


def test_excepcion_inesperada_no_expone_trazas(cliente, db, h_docente, entrega_lista, pipeline):
    pipeline["falla"] = RuntimeError("secreto interno /ruta/privada Traceback")
    r = evaluar_entrega(cliente, h_docente, entrega_lista["id"])
    ev = obtener(cliente, h_docente, r.json()["id"]).json()
    assert ev["estado"] == "error"
    assert "secreto" not in ev["error"] and "Traceback" not in ev["error"]
    assert "error interno" in ev["error"]
    assert db.get(Entrega, entrega_lista["id"]).estado == "lista"


# ---------------------------------------------------------------- conflictos (409)


def test_409_si_ya_hay_una_procesando(cliente, db, h_docente, entrega_lista, pipeline):
    db.add(
        Evaluacion(
            entrega_id=entrega_lista["id"],
            rubrica_version_id=entrega_lista["rubrica_version"]["id"],
            estado="procesando",
        )
    )
    db.commit()
    r = evaluar_entrega(cliente, h_docente, entrega_lista["id"])
    assert r.status_code == 409
    assert "en proceso" in r.json()["detail"]


def test_409_si_la_entrega_no_esta_lista(cliente, h_docente, h_est1, lab, storage, pipeline):
    borrador = crear_entrega(cliente, h_est1, lab["id"]).json()
    assert evaluar_entrega(cliente, h_docente, borrador["id"]).status_code == 409


def test_se_puede_reevaluar_una_entrega_evaluada(cliente, h_docente, evaluacion, pipeline):
    r = evaluar_entrega(cliente, h_docente, evaluacion["entrega_id"])
    assert r.status_code == 202
    lista = cliente.get(f"/api/entregas/{evaluacion['entrega_id']}/evaluaciones", headers=h_docente).json()
    assert [e["id"] for e in lista] == sorted((e["id"] for e in lista), reverse=True)
    assert len(lista) == 2


def test_estudiante_no_puede_lanzar_evaluaciones(cliente, h_est1, entrega_lista, pipeline):
    assert evaluar_entrega(cliente, h_est1, entrega_lista["id"]).status_code == 403


# ---------------------------------------------------------------- ajustes docentes (RF-08)


def test_ajuste_cambia_nota_final_no_la_preliminar_y_deja_historial(cliente, db, h_docente, evaluacion):
    r = ajustar(cliente, h_docente, evaluacion["id"], "k2", "Alto", "El estudiante sí lo resolvió bien.")
    assert r.status_code == 200, r.text
    ev = r.json()
    assert ev["nota_preliminar"] == 2.6
    assert ev["nota_final"] == 5.0  # 0.4*5 + 0.6*5
    k2 = next(c for c in ev["criterios"] if c["criterio_id"] == "k2")
    assert k2["nivel_ia"] == "Bajo" and k2["nivel_final"] == "Alto"
    assert k2["ajuste_docente"]["nivel"] == "Alto"
    assert k2["ajuste_docente"]["usuario"]["nombre"]

    # Segundo ajuste: queda el historial completo y manda el último.
    ev2 = ajustar(cliente, h_docente, evaluacion["id"], "k2", "Bajo", "Me equivoqué, era el nivel bajo.").json()
    assert ev2["nota_final"] == 2.6
    k2 = next(c for c in ev2["criterios"] if c["criterio_id"] == "k2")
    assert [a["nivel"] for a in k2["historial_ajustes"]] == ["Alto", "Bajo"]
    assert k2["historial_ajustes"][1]["nivel_anterior"] == "Alto"

    filas = list(db.scalars(select(AjusteCriterio).order_by(AjusteCriterio.id)))
    assert [(f.nivel_anterior, f.nivel_nuevo) for f in filas] == [("Bajo", "Alto"), ("Alto", "Bajo")]
    auditoria = [a for a in db.scalars(select(Auditoria)) if a.accion == "criterio_ajustado"]
    assert len(auditoria) == 2
    assert auditoria[0].detalle["nota_final_nueva"] == "5.0"
    assert db.get(Evaluacion, evaluacion["id"]).nota_preliminar == Decimal("2.60")


def test_ajuste_nivel_inexistente_400(cliente, h_docente, evaluacion):
    r = ajustar(cliente, h_docente, evaluacion["id"], "k1", "Genial")
    assert r.status_code == 400
    assert "Genial" in r.json()["detail"]


def test_ajuste_criterio_inexistente_404(cliente, h_docente, evaluacion):
    assert ajustar(cliente, h_docente, evaluacion["id"], "zz").status_code == 404


def test_ajuste_justificacion_corta_400(cliente, h_docente, evaluacion):
    assert ajustar(cliente, h_docente, evaluacion["id"], justificacion="corta").status_code == 400
    assert ajustar(cliente, h_docente, evaluacion["id"], justificacion="         x         ").status_code == 400


def test_no_se_ajusta_tras_aprobar(cliente, h_docente, evaluacion):
    assert cliente.post(f"/api/evaluaciones/{evaluacion['id']}/aprobar", headers=h_docente).status_code == 200
    assert ajustar(cliente, h_docente, evaluacion["id"]).status_code == 409


def test_estudiante_no_puede_ajustar(cliente, h_est1, evaluacion):
    assert ajustar(cliente, h_est1, evaluacion["id"]).status_code == 403


# ---------------------------------------------------------------- aprobar / publicar


def test_aprobar_y_publicar_en_orden(cliente, db, h_docente, evaluacion):
    eid = evaluacion["id"]
    # Orden incorrecto.
    assert cliente.post(f"/api/evaluaciones/{eid}/publicar", headers=h_docente).status_code == 409
    ap = cliente.post(f"/api/evaluaciones/{eid}/aprobar", headers=h_docente)
    assert ap.status_code == 200
    assert ap.json()["estado"] == "aprobada"
    assert ap.json()["aprobado_en"] and ap.json()["revisado_por"]["id"]
    assert cliente.post(f"/api/evaluaciones/{eid}/aprobar", headers=h_docente).status_code == 409
    pub = cliente.post(f"/api/evaluaciones/{eid}/publicar", headers=h_docente)
    assert pub.status_code == 200
    assert pub.json()["estado"] == "publicada" and pub.json()["publicado_en"]
    assert cliente.post(f"/api/evaluaciones/{eid}/publicar", headers=h_docente).status_code == 409
    assert {"evaluacion_aprobada", "evaluacion_publicada"} <= set(acciones(db))


def test_no_se_aprueba_una_evaluacion_con_error(cliente, h_docente, entrega_lista, pipeline):
    pipeline["falla"] = ErrorEvaluacion("Falló.")
    eid = evaluar_entrega(cliente, h_docente, entrega_lista["id"]).json()["id"]
    assert cliente.post(f"/api/evaluaciones/{eid}/aprobar", headers=h_docente).status_code == 409


def test_cola_de_revision(cliente, h_docente, h_est1, evaluacion):
    cola = cliente.get("/api/evaluaciones", headers=h_docente)
    assert cola.status_code == 200
    assert [e["id"] for e in cola.json()] == [evaluacion["id"]]
    assert cliente.get("/api/evaluaciones?estado=aprobada", headers=h_docente).json() == []
    assert cliente.get("/api/evaluaciones?estado=inventado", headers=h_docente).status_code == 400
    assert cliente.get("/api/evaluaciones", headers=h_est1).status_code == 403


# ---------------------------------------------------------------- visibilidad del estudiante


def test_estudiante_ve_solo_publicada_y_sin_campos_internos(cliente, h_docente, h_est1, evaluacion):
    eid = evaluacion["id"]
    entrega_id = evaluacion["entrega_id"]
    ajustar(cliente, h_docente, eid, "k2", "Alto", "Ajuste hecho por el docente.")

    assert obtener(cliente, h_est1, eid).status_code == 404
    assert cliente.get(f"/api/entregas/{entrega_id}/evaluaciones", headers=h_est1).json() == []
    cliente.post(f"/api/evaluaciones/{eid}/aprobar", headers=h_docente)
    assert obtener(cliente, h_est1, eid).status_code == 404  # aprobada aún no es visible
    cliente.post(f"/api/evaluaciones/{eid}/publicar", headers=h_docente)

    r = obtener(cliente, h_est1, eid)
    assert r.status_code == 200
    ev = r.json()
    assert CAMPOS_INTERNOS.isdisjoint(ev)
    assert ev["nota_final"] == 5.0
    assert ev["estado"] == "publicada"
    assert ev["resumen"] == "Resumen de la IA"
    for c in ev["criterios"]:
        assert CAMPOS_INTERNOS_CRITERIO.isdisjoint(c)
    assert "confianza" not in r.text and "nivel_ia" not in r.text and "costo" not in r.text
    lista = cliente.get(f"/api/entregas/{entrega_id}/evaluaciones", headers=h_est1).json()
    assert [e["id"] for e in lista] == [eid]
    assert CAMPOS_INTERNOS.isdisjoint(lista[0])

    # El docente sigue viendo todo.
    docente = obtener(cliente, h_docente, eid).json()
    assert CAMPOS_INTERNOS <= set(docente)


def test_otra_estudiante_recibe_404_incluso_publicada(cliente, h_docente, h_est2, evaluacion):
    eid = evaluacion["id"]
    cliente.post(f"/api/evaluaciones/{eid}/aprobar", headers=h_docente)
    cliente.post(f"/api/evaluaciones/{eid}/publicar", headers=h_docente)
    assert obtener(cliente, h_est2, eid).status_code == 404
    assert cliente.get(f"/api/entregas/{evaluacion['entrega_id']}/evaluaciones", headers=h_est2).status_code == 404
    assert obtener(cliente, h_est2, 9999).status_code == 404


# ---------------------------------------------------------------- versión de rúbrica fijada


def test_usa_la_version_de_rubrica_de_la_entrega(cliente, h_docente, lab, entrega_lista, pipeline):
    # Aparece una versión más nueva, con otros pesos y otros niveles.
    assert crear_version(cliente, h_docente, lab["id"], pesos=(10, 90)).status_code == 201
    r = evaluar_entrega(cliente, h_docente, entrega_lista["id"])
    assert r.status_code == 202
    (contexto,) = pipeline["contextos"]
    assert [c.peso for c in contexto.rubrica.criterios] == [40, 60]
    ev = obtener(cliente, h_docente, r.json()["id"]).json()
    assert ev["rubrica_version"] == entrega_lista["rubrica_version"]
    assert ev["rubrica_version"]["numero"] == 1
    assert ev["nota_preliminar"] == 2.6  # con pesos 10/90 habría dado 1.4
    assert [c["peso"] for c in ev["criterios"]] == [40, 60]


# ---------------------------------------------------------------- configuración de IA


def test_configuracion_ia_sin_secretos(cliente, h_docente, h_est1, pipeline, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ultra-secreta")
    get_settings.cache_clear()
    try:
        r = cliente.get("/api/ia/configuracion", headers=h_docente)
    finally:
        get_settings.cache_clear()
    assert r.status_code == 200
    cuerpo = r.json()
    assert set(cuerpo) == {
        "proveedor", "modelo_principal", "modelo_escalamiento", "umbral_confianza", "disponible", "motivo",
    }
    assert cuerpo["disponible"] is True and cuerpo["motivo"] == "Listo."
    assert "sk-ultra" not in r.text
    assert cliente.get("/api/ia/configuracion", headers=h_est1).status_code == 403


def test_configuracion_ia_tolera_fallo_del_proveedor(cliente, h_docente, monkeypatch):
    def falla(settings):
        raise RuntimeError("boom")

    monkeypatch.setattr(servicio, "estado_proveedor", falla)
    r = cliente.get("/api/ia/configuracion", headers=h_docente)
    assert r.status_code == 200 and r.json()["disponible"] is False


def test_endpoints_requieren_sesion(cliente):
    assert cliente.get("/api/evaluaciones").status_code == 401
    assert cliente.post("/api/entregas/1/evaluaciones").status_code == 401
    assert cliente.get("/api/ia/configuracion").status_code == 401


def test_admin_tambien_puede_evaluar(cliente, db, entrega_lista, pipeline):
    crear_usuario(db, "adm@u.co", "admin")
    h = cabecera(cliente, "adm@u.co")
    assert evaluar_entrega(cliente, h, entrega_lista["id"]).status_code == 202

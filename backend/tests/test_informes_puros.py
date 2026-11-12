"""Agregación determinista (RF-09) y mapa mental (RF-10): funciones puras con datos armados a mano."""

from datetime import UTC, datetime

import pytest

from app.evaluacion.contrato import Aprendizaje, EvaluacionCriterio, ResultadoIA
from app.informes.agregacion import (
    EvaluacionPublicada,
    LaboratorioCatalogo,
    construir_agregado,
    normalizar_tema,
)
from app.informes.contrato import (
    AccionPlan,
    ClasificacionTema,
    RelacionTemas,
    SintesisInforme,
    nivel_por_valor,
)
from app.informes.mapa import construir_mapa, slug
from app.schemas.rubrica import Competencia, Criterio, NivelDesempeno, Rubrica

NIVELES = [
    NivelDesempeno(nombre="Bajo", valor=1),
    NivelDesempeno(nombre="Medio", valor=3),
    NivelDesempeno(nombre="Alto", valor=5),
]


def rubrica(pesos=(60, 20, 20)) -> Rubrica:
    return Rubrica(
        competencias=[
            Competencia(id="c1", nombre="Modelado"),
            Competencia(id="c2", nombre="Datos"),
        ],
        criterios=[
            Criterio(
                id="k1", nombre="Criterio 1", competencia_id="c1", peso=pesos[0], niveles=NIVELES
            ),
            Criterio(
                id="k2", nombre="Criterio 2", competencia_id="c1", peso=pesos[1], niveles=NIVELES
            ),
            Criterio(
                id="k3", nombre="Criterio 3", competencia_id="c2", peso=pesos[2], niveles=NIVELES
            ),
        ],
    )


def aprendizaje(tema, nivel="competente", criterios=(), fortalecer="Practicar más") -> Aprendizaje:
    return Aprendizaje(
        tema=tema,
        que_aprendio=f"Aprendió {tema}",
        como_aplico=f"Aplicó {tema}",
        que_fortalecer=fortalecer,
        nivel_dominio=nivel,
        criterios_relacionados=list(criterios),
    )


def evaluacion(
    eid, codigo, cohorte, nota, niveles, aprendizajes, temas=(), titulo="Titulo", pesos=(60, 20, 20)
):
    return EvaluacionPublicada(
        evaluacion_id=eid,
        laboratorio=LaboratorioCatalogo(id=eid, codigo=codigo, cohorte=cohorte, temas=list(temas)),
        titulo=f"{titulo} {codigo}",
        nota_final=nota,
        publicado_en=datetime(2026, 11, eid, tzinfo=UTC),
        rubrica=rubrica(pesos),
        niveles_finales=niveles,
        resultado=ResultadoIA(
            criterios=[
                EvaluacionCriterio(criterio_id=k, nivel=n, confianza=0.9, justificacion="j")
                for k, n in niveles.items()
            ],
            resumen="r",
            fortalezas=[f"F {codigo}"],
            debilidades=[f"D {codigo}"],
            recomendaciones=[f"R {codigo}"],
            aprendizajes=aprendizajes,
        ),
    )


# Evaluación A (cohorte 1): Modelado (5*60+1*20)/80 = 4.0 ; Datos 3.0
EVAL_A = evaluacion(
    1,
    "C1-LAB01",
    1,
    4.0,
    {"k1": "Alto", "k2": "Bajo", "k3": "Medio"},
    [
        aprendizaje("REGRESIÓN", "competente", ["k1", "k2"]),
        aprendizaje("clasificación", "avanzado"),
    ],
    temas=["Regresión", "  Clasificación  "],
)
# Evaluación B (cohorte 2): Modelado (1*60+3*20)/80 = 1.5 ; Datos 5.0
EVAL_B = evaluacion(
    2,
    "C2-LAB01",
    2,
    3.0,
    {"k1": "Bajo", "k2": "Medio", "k3": "Alto"},
    [aprendizaje("regresión", "basico", ["k1"], fortalecer="Practicar más")],
    temas=["regresión"],
)
CATALOGO = [
    LaboratorioCatalogo(
        id=1, codigo="C1-LAB01", cohorte=1, temas=["Regresión", "  Clasificación  "]
    ),
    LaboratorioCatalogo(id=2, codigo="C2-LAB01", cohorte=2, temas=["regresión"]),
    LaboratorioCatalogo(id=3, codigo="C2-LAB02", cohorte=2, temas=["Clustering"]),
]


@pytest.fixture
def agregado():
    return construir_agregado("Ana Pérez", [EVAL_B, EVAL_A], CATALOGO)  # desordenado a propósito


# ---------------------------------------------------------------- agregación


def test_normalizar_tema():
    assert normalizar_tema("  Redes   NEURONALES ") == "redes neuronales"


def test_nota_general_cohortes_y_tendencia(agregado):
    assert agregado.estudiante == "Ana Pérez"
    assert agregado.laboratorios_totales == 3
    assert [lab.codigo for lab in agregado.laboratorios] == ["C1-LAB01", "C2-LAB01"]
    assert agregado.promedio_general == 3.5
    assert agregado.promedio_cohorte == {"1": 4.0, "2": 3.0}
    assert agregado.tendencia == -1.0
    assert agregado.nivel_general == "competente"  # 3.5 no es < 3.5
    lab = agregado.laboratorios[0]
    assert lab.fortalezas == ["F C1-LAB01"] and lab.debilidades == ["D C1-LAB01"]
    assert lab.recomendaciones == ["R C1-LAB01"]
    assert lab.publicado_en.startswith("2026-11-01")


def test_competencias_ponderadas_por_peso(agregado):
    comp = {c.nombre: c for c in agregado.competencias}
    # (5*60 + 1*20 + 1*60 + 3*20) / (60+20+60+20) = 2.75: con promedio simple sería 2.5
    assert comp["Modelado"].promedio == 2.75
    assert comp["Modelado"].nivel_dominio == "basico"
    assert comp["Modelado"].por_cohorte == {"1": 4.0, "2": 1.5}
    assert comp["Modelado"].laboratorios == ["C1-LAB01", "C2-LAB01"]
    assert comp["Datos"].promedio == 4.0
    assert comp["Datos"].nivel_dominio == "competente"


def test_pesos_distintos_cambian_el_promedio():
    # k1=Alto(5), k2=Bajo(1): con 90/10 -> 4.6 ; con 10/90 -> 1.4
    niveles = {"k1": "Alto", "k2": "Bajo", "k3": "Medio"}
    a = construir_agregado("x", [evaluacion(1, "L1", 1, 3.0, niveles, [], pesos=(90, 10, 10))], [])
    b = construir_agregado("x", [evaluacion(1, "L1", 1, 3.0, niveles, [], pesos=(10, 90, 10))], [])
    assert {c.nombre: c.promedio for c in a.competencias}["Modelado"] == 4.6
    assert {c.nombre: c.promedio for c in b.competencias}["Modelado"] == 1.4


def test_ajuste_docente_se_refleja_en_los_niveles_finales():
    """Los niveles finales (con ajustes) son los únicos que cuentan: ajustar k2 a Alto sube a 5.0."""
    sin_ajuste = construir_agregado("x", [EVAL_A], CATALOGO)
    ajustada = EVAL_A.model_copy(
        update={"niveles_finales": {"k1": "Alto", "k2": "Alto", "k3": "Medio"}}
    )
    con_ajuste = construir_agregado("x", [ajustada], CATALOGO)
    assert {c.nombre: c.promedio for c in sin_ajuste.competencias}["Modelado"] == 4.0
    assert {c.nombre: c.promedio for c in con_ajuste.competencias}["Modelado"] == 5.0
    assert not [b for b in con_ajuste.brechas if b.tipo == "criterio"]
    assert [b.nombre for b in sin_ajuste.brechas if b.tipo == "criterio"] == ["Criterio 2"]


def test_redondeo_a_dos_decimales():
    niveles = {"k1": "Alto", "k2": "Alto", "k3": "Alto"}
    evs = [
        evaluacion(1, "A", 1, 4.0, niveles, []),
        evaluacion(2, "B", 1, 4.0, niveles, []),
        evaluacion(3, "C", 1, 5.0, niveles, []),
    ]
    ag = construir_agregado("x", evs, [])
    assert ag.promedio_general == 4.33
    assert ag.promedio_cohorte == {"1": 4.33}


def test_temas_normalizados_y_unidos(agregado):
    nombres = [t.tema for t in agregado.temas]
    assert nombres == ["clasificación", "clustering", "regresión"]  # una sola «regresión»


def test_tema_promedio_desde_criterios_relacionados(agregado):
    t = {t.tema: t for t in agregado.temas}["regresión"]
    # k1=5, k2=1 (eval A) y k1=1 (eval B) -> 7/3
    assert t.promedio == 2.33
    assert t.nivel_dominio == "inicial"
    assert t.laboratorios == ["C1-LAB01", "C2-LAB01"]
    assert t.laboratorios_sin_evidencia == []
    assert [(a.laboratorio, a.nivel_dominio) for a in t.aprendizajes] == [
        ("C1-LAB01", "competente"),
        ("C2-LAB01", "basico"),
    ]
    assert t.que_fortalecer == ["Practicar más"]  # sin duplicados


def test_tema_sin_criterios_usa_valor_por_nivel(agregado):
    t = {t.tema: t for t in agregado.temas}["clasificación"]
    assert (t.promedio, t.nivel_dominio) == (5.0, "avanzado")
    assert t.laboratorios == ["C1-LAB01"]
    # mezcla de niveles: avanzado(5) y basico(3) -> 4.0
    evs = [
        evaluacion(1, "A", 1, 4.0, {"k1": "Alto"}, [aprendizaje("t", "avanzado")]),
        evaluacion(2, "B", 1, 4.0, {"k1": "Alto"}, [aprendizaje("t", "basico")]),
    ]
    mezcla = construir_agregado("x", evs, []).temas[0]
    assert (mezcla.promedio, mezcla.nivel_dominio) == (4.0, "competente")


def test_tema_sin_evidencia(agregado):
    t = {t.tema: t for t in agregado.temas}["clustering"]
    assert t.nivel_dominio is None and t.promedio is None
    assert t.laboratorios == []
    assert t.laboratorios_sin_evidencia == ["C2-LAB02"]
    assert t.aprendizajes == []


def test_brechas(agregado):
    por_tipo = {}
    for b in agregado.brechas:
        por_tipo.setdefault(b.tipo, []).append(b)
    assert [b.nombre for b in por_tipo["competencia"]] == ["Modelado"]
    assert [b.nombre for b in por_tipo["tema"]] == ["regresión"]
    criterios = {(b.nombre, b.detalle) for b in por_tipo["criterio"]}
    assert len(criterios) == 2
    assert any(n == "Criterio 2" and "C1-LAB01" in d for n, d in criterios)
    assert any(n == "Criterio 1" and "C2-LAB01" in d for n, d in criterios)  # Bajo=1 < 3
    assert [b.nombre for b in por_tipo["sin_evidencia"]] == ["clustering"]
    assert "C2-LAB02" in por_tipo["sin_evidencia"][0].detalle


def test_tendencia_requiere_ambas_cohortes():
    solo_c1 = construir_agregado("x", [EVAL_A], CATALOGO)
    assert solo_c1.tendencia is None
    assert solo_c1.promedio_cohorte == {"1": 4.0}
    solo_c2 = construir_agregado("x", [EVAL_B], CATALOGO)
    assert solo_c2.tendencia is None


def test_tendencia_positiva():
    niveles = {"k1": "Alto"}
    evs = [
        evaluacion(1, "A", 1, 3.0, niveles, []),
        evaluacion(2, "B", 2, 4.5, niveles, []),
    ]
    assert construir_agregado("x", evs, []).tendencia == 1.5


def test_sin_evaluaciones_no_revienta():
    ag = construir_agregado("x", [], CATALOGO)
    assert ag.laboratorios == [] and ag.competencias == []
    assert ag.tendencia is None
    assert all(t.nivel_dominio is None for t in ag.temas)


def test_nivel_por_valor_umbrales():
    assert [nivel_por_valor(v) for v in (0, 2.49, 2.5, 3.49, 3.5, 4.29, 4.3, 5)] == [
        "inicial",
        "inicial",
        "basico",
        "basico",
        "competente",
        "competente",
        "avanzado",
        "avanzado",
    ]


# ---------------------------------------------------------------- mapa


def sintesis(clasificacion=None, relaciones=None) -> SintesisInforme:
    return SintesisInforme(
        resumen="r",
        evolucion="e",
        plan=[
            AccionPlan(
                prioridad=1,
                tema="regresión",
                objetivo="o",
                actividades=["a"],
                indicador_logro="i",
                plazo_semanas=2,
            )  # fmt: skip
        ],
        clasificacion=clasificacion or [],
        relaciones=relaciones or [],
    )


CLASIF = [
    ClasificacionTema(tema="regresión", categoria="Aprendizaje supervisado"),
    ClasificacionTema(tema="Clasificación", categoria="Aprendizaje supervisado"),
]
TEMAS_CAT = {"regresión": "Aprendizaje supervisado", "clasificación": "Aprendizaje supervisado"}
# «clustering» sin categoría -> «Otros»


def test_slug_sin_tildes():
    assert slug("Aprendizaje por refuerzo") == "aprendizaje-por-refuerzo"
    assert slug("Regresión lineal ñandú") == "regresion-lineal-nandu"
    assert slug("Ética y responsabilidad en IA") == "etica-y-responsabilidad-en-ia"


def test_mapa_estructura(agregado):
    rel = [
        RelacionTemas(
            origen="regresión", destino="clasificación", tipo="prerrequisito", explicacion="base"
        ),
        RelacionTemas(origen="regresión", destino="no-existe", tipo="aplica", explicacion="x"),
        RelacionTemas(origen="regresión", destino="regresión", tipo="aplica", explicacion="x"),
        RelacionTemas(
            origen="REGRESIÓN", destino="clasificación", tipo="prerrequisito", explicacion="dup"
        ),
    ]
    mapa = construir_mapa(7, {"id": 2, "nombre": "Ana"}, agregado, sintesis(CLASIF, rel), TEMAS_CAT)
    nodos = {n.id: n for n in mapa.nodos}
    assert mapa.informe_id == 7 and mapa.estudiante == {"id": 2, "nombre": "Ana"}
    assert len(nodos) == len(mapa.nodos)  # ids únicos
    assert nodos["raiz"].etiqueta == "Inteligencia Artificial"
    assert nodos["cat:aprendizaje-supervisado"].tipo == "categoria"
    assert nodos["cat:aprendizaje-supervisado"].datos["temas"] == 2
    assert nodos["cat:otros"].datos["temas"] == 1  # clustering sin categoría
    assert "cat:fundamentos-de-ia" not in nodos  # categorías vacías no aparecen
    reg = nodos["tema:regresion"]
    assert reg.etiqueta == "regresión" and reg.nivel_dominio == "inicial"
    assert reg.datos["cohortes"] == [1, 2] and reg.datos["sin_evidencia"] is False
    assert reg.datos["laboratorios"] == ["C1-LAB01", "C2-LAB01"]
    assert nodos["tema:clustering"].datos["sin_evidencia"] is True
    assert nodos["tema:clustering"].nivel_dominio is None
    lab = nodos["lab:C1-LAB01"]
    assert lab.tipo == "laboratorio" and lab.etiqueta == "C1-LAB01 · Titulo C1-LAB01"
    assert lab.datos == {
        "cohorte": 1,
        "nota_final": 4.0,
        "evaluacion_id": 1,
        "titulo": "Titulo C1-LAB01",
    }
    assert "lab:C2-LAB02" not in nodos  # sin evaluación: no es nodo
    # raíz y categoría: promedio de temas con evidencia (2.33 y 5.0 -> 3.67)
    assert nodos["raiz"].datos["promedio"] == 3.67 and nodos["raiz"].nivel_dominio == "competente"
    assert nodos["cat:aprendizaje-supervisado"].datos["promedio"] == 3.67
    assert nodos["cat:otros"].nivel_dominio is None

    relaciones = [a for a in mapa.aristas if a.tipo == "relacion"]
    assert len(relaciones) == 1  # inválidas y duplicadas descartadas
    assert (relaciones[0].origen, relaciones[0].destino) == ("tema:regresion", "tema:clasificacion")
    assert relaciones[0].etiqueta == "prerrequisito: base"


def test_mapa_coherente_sin_huerfanos(agregado):
    mapa = construir_mapa(1, {"id": 1, "nombre": "A"}, agregado, sintesis(CLASIF), TEMAS_CAT)
    ids = {n.id for n in mapa.nodos}
    assert len({a.id for a in mapa.aristas}) == len(mapa.aristas)
    padres = {}
    for a in mapa.aristas:
        assert a.origen in ids and a.destino in ids
        if a.tipo != "relacion":
            padres.setdefault(a.destino, []).append(a)
    for n in mapa.nodos:
        if n.tipo == "raiz":
            continue
        assert n.id in padres, f"nodo huérfano {n.id}"
    por_id = {n.id: n for n in mapa.nodos}
    for a in mapa.aristas:
        if a.tipo == "jerarquia":
            asc = {"raiz": "categoria", "categoria": "tema"}
            assert asc[por_id[a.origen].tipo] == por_id[a.destino].tipo
        if a.tipo == "aplicado_en":
            assert por_id[a.origen].tipo == "tema" and por_id[a.destino].tipo == "laboratorio"
    # cada tema bajo la categoría que dice temas_categoria
    for a in mapa.aristas:
        if a.tipo == "jerarquia" and por_id[a.destino].tipo == "tema":
            esperada = TEMAS_CAT.get(por_id[a.destino].etiqueta, "Otros")
            assert por_id[a.origen].etiqueta == esperada


def test_mapa_categoria_invalida_va_a_otros(agregado):
    cat = {**TEMAS_CAT, "clustering": "Categoría inventada"}
    mapa = construir_mapa(1, {"id": 1, "nombre": "A"}, agregado, sintesis(CLASIF), cat)
    ids = {n.id for n in mapa.nodos}
    assert "cat:otros" in ids and "cat:categoria-inventada" not in ids


def test_mapa_ids_estables(agregado):
    a = construir_mapa(1, {"id": 1, "nombre": "A"}, agregado, sintesis(CLASIF), TEMAS_CAT)
    b = construir_mapa(1, {"id": 1, "nombre": "A"}, agregado, sintesis(CLASIF), TEMAS_CAT)
    assert [n.id for n in a.nodos] == [n.id for n in b.nodos]
    assert [x.id for x in a.aristas] == [x.id for x in b.aristas]

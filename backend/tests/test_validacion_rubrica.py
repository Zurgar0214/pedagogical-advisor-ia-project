from app.services.validacion_rubrica import validar_rubrica
from tests.conftest import hacer_rubrica, niveles


def test_rubrica_valida(rubrica_valida):
    assert validar_rubrica(rubrica_valida) == []


def test_pesos_no_suman_100():
    errores = validar_rubrica(hacer_rubrica([40, 50]))
    assert any("90" in e and "100 %" in e for e in errores)


def test_pesos_decimales_dentro_de_tolerancia():
    assert validar_rubrica(hacer_rubrica([33.33, 33.33, 33.34])) == []
    assert validar_rubrica(hacer_rubrica([33.3, 33.3, 33.3])) != []


def test_criterio_sin_niveles():
    r = hacer_rubrica([100])
    r.criterios[0].niveles = []
    assert any("no tiene niveles" in e for e in validar_rubrica(r))


def test_nivel_sin_descriptor():
    r = hacer_rubrica([100])
    r.criterios[0].niveles[1].descriptor = "  "
    assert any("no tiene descriptor" in e for e in validar_rubrica(r))


def test_competencia_inexistente():
    r = hacer_rubrica([100])
    r.criterios[0].competencia_id = "zzz"
    assert any("competencia inexistente" in e for e in validar_rubrica(r))


def test_valor_fuera_de_rango():
    r = hacer_rubrica([100])
    r.criterios[0].niveles = niveles(0, 5.5)
    assert any("fuera del rango" in e for e in validar_rubrica(r))


def test_valores_de_nivel_duplicados():
    r = hacer_rubrica([100])
    r.criterios[0].niveles = niveles(2, 2, 5)
    assert any("valor duplicado" in e for e in validar_rubrica(r))


def test_ids_duplicados():
    r = hacer_rubrica([50, 50])
    r.criterios[1].id = "k1"
    r.competencias.append(r.competencias[0].model_copy())
    errores = validar_rubrica(r)
    assert any("criterio duplicado" in e for e in errores)
    assert any("competencia duplicado" in e for e in errores)


def test_rubrica_sin_criterios():
    r = hacer_rubrica([])
    assert validar_rubrica(r) == ["La rúbrica no tiene criterios."]

from decimal import Decimal

import pytest

from app.services.calculo_nota import ErrorCalculoNota, calcular_nota
from tests.conftest import hacer_rubrica


def test_todo_cero():
    res = calcular_nota(hacer_rubrica([40, 60]), {"k1": "N0", "k2": "N0"})
    assert res.nota == Decimal("0.0")


def test_todo_cinco():
    res = calcular_nota(hacer_rubrica([40, 60]), {"k1": "N5", "k2": "N5"})
    assert res.nota == Decimal("5.0")


def test_mezcla_y_desglose():
    res = calcular_nota(hacer_rubrica([40, 60]), {"k1": "N5", "k2": "N2.5"})
    assert res.nota == Decimal("3.5")  # 0.4*5 + 0.6*2.5
    assert [d.aporte for d in res.desglose] == [Decimal("2.0"), Decimal("1.5")]
    assert res.desglose[0].criterio_id == "k1" and res.desglose[0].nivel == "N5"


def test_redondeo_half_up():
    r = hacer_rubrica([100], valores=(0, 2.25, 4.25))
    assert calcular_nota(r, {"k1": "N2.25"}).nota == Decimal("2.3")
    assert calcular_nota(r, {"k1": "N4.25"}).nota == Decimal("4.3")


def test_pesos_decimales():
    r = hacer_rubrica([33.33, 33.33, 33.34], valores=(0, 3, 5))
    res = calcular_nota(r, {"k1": "N3", "k2": "N3", "k3": "N5"})
    # 0.3333*3 + 0.3333*3 + 0.3334*5 = 3.6667 -> 3.7
    assert res.nota == Decimal("3.7")


def test_determinista():
    r = hacer_rubrica([25, 25, 50])
    elegidos = {"k1": "N2.5", "k2": "N5", "k3": "N0"}
    assert calcular_nota(r, elegidos) == calcular_nota(r, elegidos)


def test_rechaza_rubrica_invalida():
    with pytest.raises(ErrorCalculoNota, match="Rúbrica inválida"):
        calcular_nota(hacer_rubrica([40, 50]), {"k1": "N0", "k2": "N0"})


def test_rechaza_criterio_faltante():
    with pytest.raises(ErrorCalculoNota, match="Faltan niveles.*k2"):
        calcular_nota(hacer_rubrica([40, 60]), {"k1": "N0"})


def test_rechaza_nivel_inexistente_y_criterio_extra():
    r = hacer_rubrica([100])
    with pytest.raises(ErrorCalculoNota, match="no existe"):
        calcular_nota(r, {"k1": "Excelente"})
    with pytest.raises(ErrorCalculoNota, match="inexistentes"):
        calcular_nota(r, {"k1": "N0", "k9": "N0"})

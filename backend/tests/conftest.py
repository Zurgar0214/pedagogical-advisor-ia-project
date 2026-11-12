import pytest

from app.schemas.rubrica import Competencia, Criterio, NivelDesempeno, Rubrica


def niveles(*valores: float) -> list[NivelDesempeno]:
    return [NivelDesempeno(nombre=f"N{v}", descriptor=f"Descriptor {v}", valor=v) for v in valores]


def hacer_rubrica(pesos: list[float], valores: tuple[float, ...] = (0, 2.5, 5)) -> Rubrica:
    return Rubrica(
        version=1,
        competencias=[Competencia(id="c1", nombre="Competencia 1")],
        criterios=[
            Criterio(
                id=f"k{i}",
                nombre=f"Criterio {i}",
                competencia_id="c1",
                peso=p,
                niveles=niveles(*valores),
            )
            for i, p in enumerate(pesos, start=1)
        ],
    )


@pytest.fixture
def rubrica_valida() -> Rubrica:
    return hacer_rubrica([40, 60])

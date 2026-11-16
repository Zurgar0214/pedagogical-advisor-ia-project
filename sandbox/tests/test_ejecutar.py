"""Pruebas de ejecutar.py (sin Docker): tar seguro y parseo del junit."""

import io
import tarfile

import ejecutar
import pytest


def hacer_tar(entradas):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:") as t:
        for info, datos in entradas:
            t.addfile(info, io.BytesIO(datos) if datos is not None else None)
    return buf.getvalue()


def archivo(nombre, datos=b"x"):
    i = tarfile.TarInfo(nombre)
    i.size = len(datos)
    return i, datos


def test_extraccion_normal(tmp_path):
    n = ejecutar.extraer_seguro(hacer_tar([archivo("a/b.py", b"hola")]), tmp_path)
    assert n == 1 and (tmp_path / "a/b.py").read_bytes() == b"hola"


@pytest.mark.parametrize("nombre", ["/etc/x", "../x", "a/../../x", "C:/x"])
def test_rechaza_rutas_peligrosas(tmp_path, nombre):
    with pytest.raises(ejecutar.TarInseguro):
        ejecutar.extraer_seguro(hacer_tar([archivo(nombre)]), tmp_path)


@pytest.mark.parametrize(
    "tipo", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE]
)
def test_rechaza_enlaces_y_dispositivos(tmp_path, tipo):
    i = tarfile.TarInfo("e")
    i.type = tipo
    i.linkname = "/etc/passwd"
    with pytest.raises(ejecutar.TarInseguro):
        ejecutar.extraer_seguro(hacer_tar([(i, None)]), tmp_path)


def test_topes(tmp_path, monkeypatch):
    monkeypatch.setattr(ejecutar, "MAX_ENTRADAS", 3)
    with pytest.raises(ejecutar.TarInseguro, match="entradas"):
        ejecutar.extraer_seguro(hacer_tar([archivo(f"f{i}") for i in range(4)]), tmp_path)
    monkeypatch.setattr(ejecutar, "MAX_BYTES_DESCOMPRIMIDO", 10)
    with pytest.raises(ejecutar.TarInseguro, match="20 MB"):
        ejecutar.extraer_seguro(hacer_tar([archivo("g", b"x" * 11)]), tmp_path)


def test_tar_invalido(tmp_path):
    with pytest.raises(ejecutar.TarInseguro):
        ejecutar.extraer_seguro(b"no es un tar", tmp_path)


def test_parsear_junit(tmp_path):
    xml = tmp_path / "r.xml"
    xml.write_text(
        '<testsuites><testsuite tests="6" failures="1" errors="1" skipped="1"/></testsuites>'
    )
    esperado = {"total": 6, "exitosas": 3, "fallidas": 1, "errores": 1, "omitidas": 1}
    assert ejecutar.parsear_junit(xml) == esperado
    assert ejecutar.parsear_junit(tmp_path / "no_existe.xml")["total"] == 0
    xml.write_text("<roto")
    assert ejecutar.parsear_junit(xml)["total"] == 0


def test_recortar():
    assert ejecutar.recortar("abc") == "abc"
    r = ejecutar.recortar("x" * 20000)
    assert len(r) < 8100 and "recortada" in r

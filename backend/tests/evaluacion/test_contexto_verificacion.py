import tempfile
from pathlib import Path

from app.evaluacion import contexto as ctx
from app.evaluacion import verificacion
from app.evaluacion.contexto import preparar_contexto
from app.evaluacion.contrato import EvidenciaContexto
from tests.evaluacion.utiles_eval import PNG, contexto, notebook, settings


def preparar(c, aceptar_imagenes=True, **kw):
    return preparar_contexto(c, settings(**kw), aceptar_imagenes)


def rutas(p):
    return {a.ruta for a in p.archivos}


def test_zip_ignora_binarios_y_carpetas_excluidas(tmp_path):
    c = contexto(
        tmp_path,
        {
            "main.py": "print('hola')\n",
            "README.md": "# Proyecto",
            "logo.png": PNG,
            "datos.bin": b"\x00\x01\x02" * 50,
            "node_modules/lib/x.js": "x",
            ".git/config": "[core]",
            "__pycache__/a.cpython.pyc": b"\x00",
            ".venv/lib/site.py": "x=1",
            "pkg/util.py": "def f():\n    return 1\n",
        },
    )
    p = preparar(c)
    assert rutas(p) == {"main.py", "README.md", "pkg/util.py"}
    assert any("binarios" in a for a in p.advertencias)


def test_zip_rechaza_rutas_peligrosas(tmp_path):
    c = contexto(
        tmp_path,
        {
            "../evil.py": "x=1",
            "/abs.py": "x=1",
            "C:\\win.py": "x=1",
            "a/../../b.py": "x=1",
            "ok/a.py": "x=1\n",
        },
    )
    p = preparar(c)
    assert rutas(p) == {"ok/a.py"}
    assert any("peligrosas" in a for a in p.advertencias)


def test_zip_respeta_limites(tmp_path, monkeypatch):
    monkeypatch.setattr(ctx, "MAX_BYTES_ARCHIVO", 100)
    monkeypatch.setattr(ctx, "MAX_ARCHIVOS_CODIGO", 2)
    c = contexto(tmp_path, {f"f{i}.py": "x = 1\n" * 100 for i in range(5)})
    p = preparar(c)
    assert len(p.archivos) == 2
    assert all(a.truncado and len(a.texto.encode()) <= 100 for a in p.archivos)
    assert any("máximo de 2 archivos" in a for a in p.advertencias)
    assert any("truncó" in a for a in p.advertencias)


def test_zip_corrupto_no_rompe(tmp_path):
    malo = tmp_path / "malo.zip"
    malo.write_bytes(b"no es un zip")
    c = contexto(
        extra=[
            EvidenciaContexto(id=2, tipo="codigo_zip", nombre_original="malo.zip", ruta_archivo=str(malo))
        ]
    )
    p = preparar(c)
    assert p.archivos == []
    assert any("No se pudo abrir el ZIP" in a for a in p.advertencias)


def test_notebook_extrae_celdas_y_detecta_sintaxis(tmp_path):
    nb = notebook(
        [
            ("markdown", "# Título"),
            ("code", "x = 1\n%matplotlib inline\nprint(x)"),
            ("code", "def roto(:\n    pass"),
        ]
    )
    p = preparar(contexto(tmp_path, {"analisis.ipynb": nb}))
    [a] = p.archivos
    assert a.lenguaje == "notebook"
    assert "celda 2 - código" in a.texto and "# Título" in a.texto
    assert [n for n, _ in a.celdas_python] == [2, 3]
    v = verificacion.verificar(p, settings())
    assert len(v.errores_sintaxis) == 1
    assert "celda 3" in v.errores_sintaxis[0].archivo  # la magic de la celda 2 no es error


def test_sintaxis_invalida_detectada_y_conteo_por_lenguaje(tmp_path):
    p = preparar(
        contexto(tmp_path, {"bien.py": "x = 1\n", "mal.py": "def f(:\n  pass\n", "a.js": "var a;"})
    )
    v = verificacion.verificar(p, settings())
    assert [(h.archivo, h.regla) for h in v.errores_sintaxis] == [("mal.py", "sintaxis")]
    assert v.errores_sintaxis[0].linea == 1
    assert v.archivos_por_lenguaje == {"python": 2, "javascript": 1}
    assert v.archivos_analizados == 3
    assert v.pruebas.ejecutadas is False
    assert "no incluye pruebas unitarias" in v.pruebas.motivo


def test_ruff_se_ejecuta_y_limpia_temporales(tmp_path, monkeypatch):
    creados = []
    original = tempfile.mkdtemp

    def registrar(*a, **kw):
        d = original(*a, **kw)
        creados.append(d)
        return d

    monkeypatch.setattr(verificacion.tempfile, "mkdtemp", registrar)
    p = preparar(contexto(tmp_path, {"src/uno.py": "import os\n\nx = 1\n"}))
    v = verificacion.verificar(p, settings())
    if verificacion._comando_ruff() is None:
        assert any("Ruff no está disponible" in n for n in v.notas)
    else:
        assert any(h.regla == "F401" and h.archivo == "src/uno.py" for h in v.hallazgos_estaticos)
        assert v.hallazgos_estaticos[0].linea == 1
    assert creados and not any(Path(d).exists() for d in creados)


def test_ruff_no_disponible_se_marca(tmp_path, monkeypatch):
    monkeypatch.setattr(verificacion, "_comando_ruff", lambda: None)
    v = verificacion.verificar(preparar(contexto(tmp_path, {"a.py": "x = 1\n"})), settings())
    assert v.hallazgos_estaticos == []
    assert any("Ruff no está disponible" in n for n in v.notas)


def test_recorte_de_contexto_con_advertencia(tmp_path):
    informe = "Párrafo del informe. " * 400  # ~8400 caracteres
    codigo = {f"mod{i}.py": "\n".join(f"v{j} = {j}" for j in range(300)) for i in range(4)}
    p = preparar(contexto(tmp_path, codigo=codigo, informe=informe), ia_max_caracteres_contexto=6000)
    total = sum(len(f.texto_prompt) for f in p.fuentes)
    assert total <= 6000
    inf = next(f for f in p.fuentes if f.fuente == "informe_pdf")
    assert inf.truncado and len(inf.texto_prompt) == 3600  # 60 % del tope
    assert any("tope de contexto" in a for a in p.advertencias)
    # el código completo sigue disponible para verificar aunque no quepa en el prompt
    assert len(p.archivos) == 4
    assert len(p.fuentes) < 5


def test_codigo_numerado_y_archivos_principales_primero(tmp_path):
    p = preparar(
        contexto(tmp_path, {"util.py": "a = 1\nb = 2\n", "main.py": "print(1)\n", "z.txt": "nota"})
    )
    nombres = [f.fuente for f in p.fuentes]
    assert nombres[:2] == ["informe_pdf", "codigo:main.py"]
    main = p.fuentes[1]
    assert main.texto_prompt.startswith("   1| print(1)")


def test_repo_github_se_lista_y_no_se_clona():
    c = contexto(
        extra=[EvidenciaContexto(id=3, tipo="repo_github", url="https://github.com/u/r")]
    )
    p = preparar(c)
    assert p.repositorios_no_analizados == ["https://github.com/u/r"]
    assert any("no se clonan" in a for a in p.advertencias)
    assert verificacion.verificar(p, settings()).repositorios_no_analizados == ["https://github.com/u/r"]


def test_imagenes_segun_proveedor_y_limites(tmp_path, monkeypatch):
    extra = []
    for i in range(7):
        f = tmp_path / f"i{i}.png"
        f.write_bytes(PNG)
        extra.append(
            EvidenciaContexto(
                id=10 + i, tipo="imagen", nombre_original=f"i{i}.png", ruta_archivo=str(f)
            )
        )
    grande = tmp_path / "grande.png"
    grande.write_bytes(PNG)
    c = contexto(extra=extra)
    p = preparar(c, aceptar_imagenes=True)
    assert len(p.imagenes) == 5
    assert p.imagenes[0].media_type == "image/png"
    assert sum("máximo 5 imágenes" in a for a in p.advertencias) == 2

    monkeypatch.setattr(ctx, "MAX_BYTES_IMAGEN", 10)
    p2 = preparar(c, aceptar_imagenes=True)
    assert p2.imagenes == [] and any("supera 5 MB" in a for a in p2.advertencias)

    p3 = preparar(c, aceptar_imagenes=False)
    assert p3.imagenes == []
    assert sum("no admite imágenes" in a for a in p3.advertencias) == 7


def test_pruebas_con_sandbox_deshabilitada_dan_motivo_claro(tmp_path):
    p = preparar(contexto(tmp_path, {"a.py": "x = 1\n", "test_a.py": "def test_a():\n    pass\n"}))
    v = verificacion.verificar(p, settings(sandbox_url=""))
    assert v.pruebas.ejecutadas is False
    assert "no está configurada" in v.pruebas.motivo

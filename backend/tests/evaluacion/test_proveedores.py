import json
from types import SimpleNamespace

import httpx
import pytest

from app.evaluacion.esquemas import SalidaCriterios, SalidaEvaluacion
from app.evaluacion.proveedores import crear_proveedor, estado_de
from app.evaluacion.proveedores.base import (
    BloqueImagen,
    BloqueTexto,
    ErrorProveedor,
    ErrorSalidaInvalida,
)
from app.evaluacion.proveedores.claude import ClaudeProveedor
from app.evaluacion.proveedores.falso import FalsoProveedor
from app.evaluacion.proveedores.ollama import OllamaProveedor
from tests.evaluacion.utiles_eval import crit, salida, settings


class ClienteFalso:
    """Imita `anthropic.Anthropic` lo justo: `messages.create(**kw)`."""

    def __init__(self, respuesta=None, stop_reason="end_turn", usage=None):
        self.llamadas: list[dict] = []
        self._respuesta = respuesta
        self._stop = stop_reason
        self._usage = usage or SimpleNamespace(
            input_tokens=1000,
            output_tokens=500,
            cache_read_input_tokens=2000,
            cache_creation_input_tokens=0,
        )
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.llamadas.append(kw)
        texto = self._respuesta if isinstance(self._respuesta, str) else self._respuesta.model_dump_json()
        return SimpleNamespace(
            stop_reason=self._stop,
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text=texto),
            ],
            usage=self._usage,
        )


def llamar(prov, esquema=SalidaEvaluacion, proposito="evaluacion", variables=None):
    return prov.generar_estructurado(
        "SISTEMA",
        [BloqueTexto("ESTABLE-1"), BloqueTexto("ESTABLE-2")],
        variables or [BloqueTexto("VARIABLE"), BloqueImagen("image/png", "QUJD")],
        esquema,
        "claude-haiku-5-5",
        proposito,
    )


def test_claude_construye_peticion_con_cache_y_salida_estructurada():
    cliente = ClienteFalso(salida([crit("k1")]))
    prov = ClaudeProveedor(settings(ai_provider="claude", anthropic_api_key="x"), cliente=cliente)
    obj, uso = llamar(prov)
    [kw] = cliente.llamadas

    assert kw["model"] == "claude-haiku-5-5"
    assert kw["system"] == [{"type": "text", "text": "SISTEMA"}]
    contenido = kw["messages"][0]["content"]
    assert [b["type"] for b in contenido] == ["text", "text", "text", "image"]
    # cache_control solo en el ÚLTIMO bloque estable; lo variable va después y sin caché
    assert "cache_control" not in contenido[0]
    assert contenido[1]["cache_control"] == {"type": "ephemeral"}
    assert all("cache_control" not in b for b in contenido[2:])
    assert contenido[3]["source"] == {"type": "base64", "media_type": "image/png", "data": "QUJD"}
    # sin parámetros prohibidos en Haiku/Sonnet 5.5
    for prohibido in ("temperature", "top_p", "top_k", "thinking"):
        assert prohibido not in kw
    assert kw["messages"][-1]["role"] == "user"  # sin prefill
    oc = kw["output_config"]
    assert oc["effort"] == "low" and oc["format"]["type"] == "json_schema"
    assert oc["format"]["schema"]["additionalProperties"] is False
    assert "resumen" in oc["format"]["schema"]["properties"]

    assert obj.criterios[0].criterio_id == "k1"
    assert (uso.tokens_entrada, uso.tokens_salida, uso.tokens_cache_lectura) == (1000, 500, 2000)
    # 1000*0.10 + 500*0.50 + 2000*0.01 = 370 / 1e6
    assert uso.costo_usd_estimado == pytest.approx(0.00037)
    assert uso.proveedor == "claude" and uso.modelo == "claude-haiku-5-5"


def test_claude_escalamiento_usa_esfuerzo_medio():
    cliente = ClienteFalso(SalidaCriterios(criterios=[crit("k1")]))
    prov = ClaudeProveedor(settings(ai_provider="claude", anthropic_api_key="x"), cliente=cliente)
    llamar(prov, SalidaCriterios, "escalamiento")
    assert cliente.llamadas[0]["output_config"]["effort"] == "medium"


def test_claude_refusal_se_revisa_antes_de_leer_contenido():
    prov = ClaudeProveedor(
        settings(ai_provider="claude", anthropic_api_key="x"),
        cliente=ClienteFalso("no es json", stop_reason="refusal"),
    )
    with pytest.raises(ErrorProveedor, match="negó") as e:
        llamar(prov)
    assert not isinstance(e.value, ErrorSalidaInvalida)


def test_claude_max_tokens_y_json_invalido_son_salida_invalida_con_uso():
    for stop, texto in (("max_tokens", '{"criterios": ['), ("end_turn", '{"criterios": 5}')):
        prov = ClaudeProveedor(
            settings(ai_provider="claude", anthropic_api_key="x"),
            cliente=ClienteFalso(texto, stop_reason=stop),
        )
        with pytest.raises(ErrorSalidaInvalida) as e:
            llamar(prov)
        assert e.value.uso is not None and e.value.uso.tokens_salida == 500


def test_claude_sin_clave_no_crea_cliente():
    prov = ClaudeProveedor(settings(ai_provider="claude"))
    with pytest.raises(ErrorProveedor, match="ANTHROPIC_API_KEY"):
        llamar(prov)


def test_fabrica_segun_ai_provider():
    assert isinstance(crear_proveedor(settings(ai_provider="falso")), FalsoProveedor)
    assert isinstance(crear_proveedor(settings(ai_provider="OLLAMA")), OllamaProveedor)
    p = crear_proveedor(settings(ai_provider="claude", anthropic_api_key="x"))
    assert isinstance(p, ClaudeProveedor) and p.acepta_imagenes
    assert (p.modelo_principal, p.modelo_escalamiento) == ("claude-haiku-5-5", "claude-sonnet-5-5")
    with pytest.raises(ErrorProveedor, match="desconocido"):
        crear_proveedor(settings(ai_provider="gpt"))


def test_ollama_usa_api_chat_con_schema_y_costo_cero():
    visto = {}

    def manejador(req: httpx.Request) -> httpx.Response:
        visto["url"] = str(req.url)
        visto["cuerpo"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "message": {"content": salida([crit("k1")]).model_dump_json()},
                "prompt_eval_count": 321,
                "eval_count": 45,
            },
        )

    http = httpx.Client(transport=httpx.MockTransport(manejador))
    prov = OllamaProveedor(settings(ai_provider="ollama"), cliente=http)
    obj, uso = llamar(prov)
    assert visto["url"].endswith("/api/chat")
    cuerpo = visto["cuerpo"]
    assert cuerpo["stream"] is False and cuerpo["model"] == "claude-haiku-5-5"
    assert cuerpo["format"]["properties"]["criterios"]
    assert "ESTABLE-1" in cuerpo["messages"][1]["content"] and "VARIABLE" in cuerpo["messages"][1]["content"]
    assert obj.resumen == "Resumen"
    assert (uso.tokens_entrada, uso.tokens_salida, uso.costo_usd_estimado) == (321, 45, 0.0)
    assert not prov.acepta_imagenes


def test_ollama_errores():
    def malo(_):
        return httpx.Response(200, json={"message": {"content": "{}"}})

    prov = OllamaProveedor(
        settings(ai_provider="ollama"), cliente=httpx.Client(transport=httpx.MockTransport(malo))
    )
    with pytest.raises(ErrorSalidaInvalida):
        llamar(prov)

    def caido(_):
        raise httpx.ConnectError("sin conexión")

    prov = OllamaProveedor(
        settings(ai_provider="ollama"), cliente=httpx.Client(transport=httpx.MockTransport(caido))
    )
    with pytest.raises(ErrorProveedor, match="No se pudo conectar"):
        llamar(prov)


def test_estado_ollama_con_transporte_simulado():
    ok = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    assert estado_de(settings(ai_provider="ollama"), ok)[0]

    def caido(_):
        raise httpx.ConnectError("x")

    mal = httpx.Client(transport=httpx.MockTransport(caido))
    disponible, motivo = estado_de(settings(ai_provider="ollama"), mal)
    assert not disponible and "No se pudo conectar" in motivo


def test_estado_claude_sin_clave_y_clave_en_blanco():
    assert not estado_de(settings(ai_provider="claude"))[0]
    assert not estado_de(settings(ai_provider="claude", anthropic_api_key="   "))[0]
    assert estado_de(settings(ai_provider="claude", anthropic_api_key="sk-ant-x"))[0]


def test_falso_es_determinista_y_valida_contra_el_esquema():
    estables = [
        BloqueTexto(
            '<temas>\n["T1"]\n</temas>\n\n<rubrica>\n'
            + json.dumps(
                {
                    "criterios": [
                        {
                            "criterio_id": "k1",
                            "niveles_de_menor_a_mayor": [{"nombre": "A"}, {"nombre": "B"}],
                        }
                    ]
                }
            )
            + "\n</rubrica>"
        )
    ]
    variables = [
        BloqueTexto(
            '<evidencia_estudiante fuente="informe_pdf" evidencia_id="1">\nHola mundo\n'
            "</evidencia_estudiante>"
        )
    ]
    prov = FalsoProveedor()
    a, _ = prov.generar_estructurado("s", estables, variables, SalidaEvaluacion, "m", "evaluacion")
    b, _ = prov.generar_estructurado("s", estables, variables, SalidaEvaluacion, "m", "evaluacion")
    assert a == b
    assert a.criterios[0].evidencias[0].fragmento == "Hola mundo"
    assert a.aprendizajes[0].tema == "T1"

import math

import pytest

from app import weather
from app.cache import StaleCache


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    reloj = Reloj()
    monkeypatch.setattr(weather, "_cache", StaleCache(ttl=300, maxsize=4, max_stale=3600, clock=reloj))
    monkeypatch.setattr(weather, "_fallo_hasta", 0.0)
    monkeypatch.setattr(weather, "_aviso_config_emitido", False)
    return reloj


@pytest.mark.parametrize("payload", [
    {}, {"main": {}}, {"main": {"temp": "caliente"}}, {"main": {"temp": None}},
    {"main": {"temp": True}}, {"main": {"temp": math.nan}}, {"main": {"temp": 999}},
    {"main": {"temp": -80}}, None, [],
])
def test_respuestas_invalidas_se_rechazan(payload):
    with pytest.raises(ValueError):
        weather._validar_temperatura(payload)


def test_respuesta_valida():
    assert weather._validar_temperatura({"main": {"temp": 24.5}}) == 24.5
    assert weather._validar_temperatura({"main": {"temp": 0}}) == 0.0


def test_fallo_sin_lectura_previa_devuelve_none_y_no_reintenta(monkeypatch):
    llamadas = []

    def falla():
        llamadas.append(1)
        raise RuntimeError("caído")

    monkeypatch.setattr(weather, "_consultar", falla)
    assert weather.obtener_temperatura() is None
    assert weather.obtener_temperatura() is None  # enfriamiento activo
    assert len(llamadas) == 1


def test_usa_ultima_lectura_buena_si_cae_el_servicio(monkeypatch, limpio):
    monkeypatch.setattr(weather, "_consultar", lambda: 21.0)
    assert weather.obtener_temperatura() == 21.0
    limpio.t = 400  # TTL vencido

    def falla():
        raise RuntimeError("caído")

    monkeypatch.setattr(weather, "_consultar", falla)
    assert weather.obtener_temperatura() == 21.0


def test_descarta_lectura_de_mas_de_una_hora(monkeypatch, limpio):
    monkeypatch.setattr(weather, "_consultar", lambda: 21.0)
    weather.obtener_temperatura()
    limpio.t = 3601

    def falla():
        raise RuntimeError("caído")

    monkeypatch.setattr(weather, "_consultar", falla)
    assert weather.obtener_temperatura() is None


def test_sin_configuracion_devuelve_none(monkeypatch):
    monkeypatch.setattr(weather.settings, "owm_api_key", None)
    monkeypatch.setattr(weather, "_consultar", lambda: pytest.fail("no debe llamarse"))
    assert weather.obtener_temperatura() is None

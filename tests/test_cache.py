import pytest

from app.cache import StaleCache


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_devuelve_valor_fresco_sin_recargar():
    reloj, llamadas = Reloj(), []
    c = StaleCache(ttl=10, clock=reloj)
    cargador = lambda: llamadas.append(1) or 42
    assert c.get_or_load("k", cargador) == 42
    assert c.get_or_load("k", cargador) == 42
    assert len(llamadas) == 1


def test_usa_ultima_lectura_si_falla_la_recarga():
    reloj = Reloj()
    c = StaleCache(ttl=10, clock=reloj)
    c.get_or_load("k", lambda: 1)
    reloj.t = 100

    def falla():
        raise RuntimeError("caído")

    assert c.get_or_load("k", falla) == 1


def test_relanza_si_no_hay_lectura_previa():
    c = StaleCache(ttl=10)
    with pytest.raises(RuntimeError):
        c.get_or_load("k", lambda: (_ for _ in ()).throw(RuntimeError("x")))


def test_max_stale_descarta_lecturas_viejas():
    reloj = Reloj()
    c = StaleCache(ttl=10, max_stale=3600, clock=reloj)
    c.set("k", 1)
    reloj.t = 3601
    assert c.get_stale("k") is None


def test_maxsize_expulsa_la_mas_vieja():
    reloj = Reloj()
    c = StaleCache(ttl=10, maxsize=2, clock=reloj)
    for i, k in enumerate("abc"):
        reloj.t = i
        c.set(k, i)
    assert c.get_fresh("a") is None and c.get_fresh("c") == 2


def test_tras_fallo_con_copia_previa_no_reintenta_de_inmediato():
    reloj, llamadas = Reloj(), []
    c = StaleCache(ttl=10, reintento_tras_fallo=30, clock=reloj)
    c.get_or_load("k", lambda: 1)
    reloj.t = 20  # TTL vencido

    def falla():
        llamadas.append(1)
        raise RuntimeError("caído")

    assert c.get_or_load("k", falla) == 1
    reloj.t = 40  # dentro de los 30 s de enfriamiento
    assert c.get_or_load("k", falla) == 1
    assert len(llamadas) == 1
    reloj.t = 51  # enfriamiento vencido: reintenta
    c.get_or_load("k", falla)
    assert len(llamadas) == 2

"""Temperatura actual vía OpenWeatherMap, con resiliencia.

- Timeout corto (conexión, lectura).
- Enfriamiento tras un fallo: no se vuelve a llamar durante N segundos.
- Validación de la respuesta (sin main.temp, texto, NaN o fuera de rango = fallo).
- Ajuste de calibración local (-2°C).
- Si el servicio cae se usa la última lectura buena, descartada pasada 1 hora.
- Sin clave o ubicación: devuelve None y avisa una sola vez.

Devolver None desactiva únicamente la Regla D; el menú sigue funcionando.
"""
import logging
import math
import threading
import time

import requests

from .cache import StaleCache
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

OWM_URL = "https://api.openweathermap.org/data/2.5/weather"
TEMP_MIN_VALIDA_C = -60.0
TEMP_MAX_VALIDA_C = 60.0
_CLAVE = "temp"

_cache = StaleCache(
    ttl=settings.cache_ttl_seconds,
    maxsize=4,
    max_stale=settings.owm_max_stale_seconds,
)
_lock = threading.Lock()
_fallo_hasta = 0.0          # instante (monotonic) hasta el que no se reintenta
_aviso_config_emitido = False


def _validar_temperatura(payload: object) -> float:
    """Extrae main.temp, la valida y le aplica el ajuste de -2°C y redondeo."""
    try:
        bruto = payload["main"]["temp"]  # type: ignore[index]
    except (KeyError, TypeError) as exc:
        raise ValueError("Respuesta sin main.temp") from exc
    if isinstance(bruto, bool) or not isinstance(bruto, (int, float)):
        raise ValueError("main.temp no es numérico")
    temp = float(bruto)
    if not math.isfinite(temp) or not TEMP_MIN_VALIDA_C <= temp <= TEMP_MAX_VALIDA_C:
        raise ValueError("main.temp fuera de rango válido")
    
    # Se ajusta la temperatura restando 2 grados y redondeando
    return float(round(temp - 2.0))


def _consultar() -> float:
    params: dict = {"appid": settings.owm_api_key, "units": "metric"}
    if settings.owm_lat is not None and settings.owm_lon is not None:
        params.update(lat=settings.owm_lat, lon=settings.owm_lon)
    else:
        params["q"] = settings.owm_city
    resp = requests.get(
        OWM_URL,
        params=params,
        timeout=(settings.owm_connect_timeout_seconds, settings.owm_read_timeout_seconds),
    )
    resp.raise_for_status()
    return _validar_temperatura(resp.json())


def _configurado() -> bool:
    ubicacion = settings.owm_city or (settings.owm_lat is not None and settings.owm_lon is not None)
    return bool(settings.owm_api_key and ubicacion)


def _describir(exc: Exception) -> str:
    """Descripción segura: las URLs de requests incluyen la API key, no se registran."""
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return f"HTTP {exc.response.status_code}"
    return type(exc).__name__ if not isinstance(exc, ValueError) else str(exc)


def obtener_temperatura() -> float | None:
    """Temperatura en °C, o None si no hay configuración ni lectura utilizable."""
    global _fallo_hasta, _aviso_config_emitido

    if not _configurado():
        if not _aviso_config_emitido:
            logger.warning("OpenWeatherMap no configurado: se omite el recomendador climático.")
            _aviso_config_emitido = True
        return None

    fresca = _cache.get_fresh(_CLAVE)
    if fresca is not None:
        return fresca

    with _lock:
        fresca = _cache.get_fresh(_CLAVE)  # otra petición pudo recargar mientras esperábamos
        if fresca is not None:
            return fresca
        if time.monotonic() < _fallo_hasta:
            return _cache.get_stale(_CLAVE)
        try:
            temp = _consultar()
        except Exception as exc:
            _fallo_hasta = time.monotonic() + settings.owm_failure_cooldown_seconds
            vieja = _cache.get_stale(_CLAVE)
            logger.warning(
                "OpenWeatherMap falló (%s); %s.",
                _describir(exc),
                "se usa la última lectura buena" if vieja is not None else "se omite la Regla D",
            )
            return vieja
        _cache.set(_CLAVE, temp)
        return temp

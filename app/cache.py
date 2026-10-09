"""Caché con TTL que conserva la última lectura buena ("stale") para degradar con elegancia.

Interfaz compatible con `StaleCache(ttl=..., maxsize=...)` + `get_or_load(clave, funcion)`.
Si `max_stale` es None, la lectura antigua se conserva sin límite de edad.
Tras una recarga fallida con copia previa, espera `reintento_tras_fallo` s antes de reintentar.
"""
import logging
import threading
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

_FALTA = object()


class StaleCache:
    def __init__(
        self,
        ttl: float,
        maxsize: int = 16,
        max_stale: float | None = None,
        reintento_tras_fallo: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ttl = ttl
        self.maxsize = maxsize
        self.max_stale = max_stale
        self.reintento_tras_fallo = reintento_tras_fallo  # evita martillar una API caída
        self._reintentar_desde: dict[Any, float] = {}
        self._clock = clock
        self._datos: dict[Any, tuple[Any, float]] = {}
        self._lock = threading.RLock()

    # --- lectura ---------------------------------------------------------
    def _leer(self, clave: Any, edad_maxima: float | None) -> Any:
        with self._lock:
            entrada = self._datos.get(clave)
            if entrada is None:
                return _FALTA
            valor, guardado = entrada
            if edad_maxima is not None and self._clock() - guardado > edad_maxima:
                return _FALTA
            return valor

    def get_fresh(self, clave: Any) -> Any | None:
        """Valor dentro del TTL, o None."""
        valor = self._leer(clave, self.ttl)
        return None if valor is _FALTA else valor

    def get_stale(self, clave: Any) -> Any | None:
        """Última lectura buena (dentro de `max_stale`), o None."""
        valor = self._leer(clave, self.max_stale)
        return None if valor is _FALTA else valor

    # --- escritura -------------------------------------------------------
    def set(self, clave: Any, valor: Any) -> None:
        with self._lock:
            self._datos[clave] = (valor, self._clock())
            while len(self._datos) > self.maxsize:
                mas_vieja = min(self._datos, key=lambda k: self._datos[k][1])
                del self._datos[mas_vieja]

    def clear(self) -> None:
        with self._lock:
            self._datos.clear()
            self._reintentar_desde.clear()

    # --- patrón principal ------------------------------------------------
    def get_or_load(self, clave: Any, cargador: Callable[[], Any]) -> Any:
        """Devuelve el valor fresco; si recargar falla, usa la última lectura buena.

        Si no hay lectura previa utilizable, relanza la excepción original.
        El bloqueo evita que varias peticiones simultáneas recarguen a la vez.
        """
        with self._lock:
            valor = self._leer(clave, self.ttl)
            if valor is not _FALTA:
                return valor
            viejo = self._leer(clave, self.max_stale)
            if viejo is not _FALTA and self._clock() < self._reintentar_desde.get(clave, 0.0):
                return viejo  # recarga fallida hace poco: no se reintenta todavía
            try:
                nuevo = cargador()
            except Exception:
                if viejo is _FALTA:
                    raise
                logger.warning(
                    "Falló la recarga de '%s'; se sirve la última lectura buena.", clave, exc_info=True
                )
                self._reintentar_desde[clave] = self._clock() + self.reintento_tras_fallo
                return viejo
            self.set(clave, nuevo)
            self._reintentar_desde.pop(clave, None)
            return nuevo

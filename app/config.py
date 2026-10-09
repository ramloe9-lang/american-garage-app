"""Configuración centralizada (variables de entorno / archivo .env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Google Sheets
    google_sheet_id: str
    google_service_account_file: str | None = None
    google_service_account_json: str | None = None

    # OpenWeatherMap (si falta, el motor omite la Regla D sin romper el menú)
    owm_api_key: str | None = None
    owm_city: str | None = None
    owm_lat: float | None = None
    owm_lon: float | None = None
    owm_connect_timeout_seconds: float = 2.0
    owm_read_timeout_seconds: float = 4.0
    owm_failure_cooldown_seconds: float = 60.0   # sin reintentar tras un fallo
    owm_max_stale_seconds: float = 3600.0        # vigencia de la última lectura buena

    # Caché y red
    cache_ttl_seconds: int = 300
    http_timeout_seconds: float = 8.0

    # Seguridad / operación
    dashboard_api_key: str | None = None  # si se define, /dashboard exige header X-API-Key
    cors_origins: str = "*"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Conexión segura a Google Sheets (gspread + oauth2client, Service Account) con caché."""
import json
import logging
import threading

import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

from .cache import StaleCache
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Columnas mínimas que exige el motor por pestaña (se valida al cargar).
COLUMNAS_REQUERIDAS: dict[str, list[str]] = {
    "Inventario_Bebidas": [
        "ID_Bebida",
        "Nombre_Producto",
        "Categoria",
        "Estado_Stock",
        "Precio_Costo",
        "Precio_Venta",
        "Temperatura_Ideal",
    ],
    "Menu_Productos": [
        "ID_Producto",
        "Nombre_Producto",
        "Categoria",
        "Precio_Venta",
        "Costo_Estimado",
        "Temperatura_Ideal",
        "Ingredientes_Clave",
    ],
    "Inventario_Insumos_Mermas": [
        "ID_Insumo",
        "Nombre_Insumo",
        "Costo_Anterior",
        "Costo_Actual",
        "Descuento_Sugerido",
        "Estado_Insumo",
    ],
    "Registro_Ventas": [
        "ID_Venta",
        "Fecha_Hora",
        "ID_Producto",
        "Cantidad",
        "Total_Venta",
    ],
    "Dashboard_Resumen": [],  # se lee por posición (los encabezados llevan espacios y '/')
}


class SheetsError(Exception):
    """Error al acceder o interpretar la hoja de cálculo."""


_cache = StaleCache(ttl=settings.cache_ttl_seconds)
_client: gspread.Client | None = None
_client_lock = threading.Lock()


def _crear_cliente() -> gspread.Client:
    try:
        if settings.google_service_account_json:
            info = json.loads(settings.google_service_account_json)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(info, SCOPES)
        elif settings.google_service_account_file:
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                settings.google_service_account_file, SCOPES
            )
        else:
            raise SheetsError(
                "Falta GOOGLE_SERVICE_ACCOUNT_FILE o GOOGLE_SERVICE_ACCOUNT_JSON."
            )
        return gspread.authorize(creds)
    except SheetsError:
        raise
    except Exception as exc:  # credenciales corruptas, archivo ausente, etc.
        raise SheetsError(f"No se pudo autenticar con Google: {exc}") from exc


def _obtener_cliente(reiniciar: bool = False) -> gspread.Client:
    global _client
    with _client_lock:
        if _client is None or reiniciar:
            _client = _crear_cliente()
        return _client


def _a_dataframe(valores: list[list[str]]) -> pd.DataFrame:
    """Matriz de celdas -> DataFrame (primera fila = encabezados; filas vacías descartadas)."""
    if not valores:
        return pd.DataFrame()
    encabezado = [str(h).strip() for h in valores[0]]
    n = len(encabezado)
    filas = [(f + [""] * n)[:n] for f in valores[1:]]
    df = pd.DataFrame(filas, columns=encabezado)

    # Filtrar filas completamente vacías (solo si hay filas: apply sobre un DataFrame vacío
    # descartaba las columnas y una pestaña con únicamente encabezados provocaba un 503).
    if not df.empty:
        df = df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)].reset_index(
            drop=True
        )

    # Normalizar alias comunes de Temperatura_Ideal
    mapeo_columnas = {}
    for col in df.columns:
        col_clean = col.strip().lower().replace(" ", "_")
        if col_clean in ["temperatura_ideal", "temp_ideal", "temperatura"]:
            mapeo_columnas[col] = "Temperatura_Ideal"

    if mapeo_columnas:
        df = df.rename(columns=mapeo_columnas)

    # Garantizar que los valores de Temperatura_Ideal estén en minúsculas y limpios
    if "Temperatura_Ideal" in df.columns:
        df["Temperatura_Ideal"] = (
            df["Temperatura_Ideal"].astype(str).str.strip().str.lower()
        )

    return df


def _descargar() -> dict[str, pd.DataFrame]:
    """Lee las 5 pestañas (≈6 llamadas a la API por refresco)."""
    try:
        try:
            libro = _obtener_cliente().open_by_key(settings.google_sheet_id)
        except Exception:
            logger.info("Reintentando con un cliente nuevo de gspread.")
            libro = _obtener_cliente(reiniciar=True).open_by_key(
                settings.google_sheet_id
            )
        hojas = {ws.title: ws for ws in libro.worksheets()}
        tablas: dict[str, pd.DataFrame] = {}
        for nombre, requeridas in COLUMNAS_REQUERIDAS.items():
            if nombre not in hojas:
                raise SheetsError(
                    f"No existe la pestaña '{nombre}' en la hoja de cálculo."
                )
            df = _a_dataframe(hojas[nombre].get_all_values())
            faltantes = [c for c in requeridas if c not in df.columns]
            if faltantes:
                raise SheetsError(
                    f"La pestaña '{nombre}' no tiene las columnas: {faltantes}"
                )
            tablas[nombre] = df
        return tablas
    except SheetsError:
        raise
    except Exception as exc:
        raise SheetsError(f"Error leyendo Google Sheets: {exc}") from exc


def obtener_tablas() -> dict[str, pd.DataFrame]:
    """Devuelve las 5 pestañas como DataFrames (caché TTL + stale-if-error)."""
    return _cache.get_or_load("tablas", _descargar)


def obtener_dashboard() -> list[dict[str, str]]:
    """KPIs de 'Dashboard_Resumen' (columnas leídas por posición: métrica, valor, nota)."""
    df = obtener_tablas()["Dashboard_Resumen"]
    kpis = []
    for fila in df.itertuples(index=False):
        celdas = list(fila) + ["", "", ""]
        if str(celdas[0]).strip():
            kpis.append(
                {
                    "metrica": str(celdas[0]).strip(),
                    "valor": str(celdas[1]).strip(),
                    "nota": str(celdas[2]).strip(),
                }
            )
    return kpis
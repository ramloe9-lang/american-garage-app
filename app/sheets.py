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

# Columnas mínimas (dejadas flexibles para evitar bloqueos)
COLUMNAS_REQUERIDAS: dict[str, list[str]] = {
    "Inventario_Bebidas": [],
    "Menu_Productos": [],
    "Inventario_Insumos_Mermas": [],
    "Registro_Ventas": [],
    "Dashboard_Resumen": [],  
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
    except Exception as exc:
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

    # Filtrar filas completamente vacías
    if not df.empty:
        df = df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)].reset_index(
            drop=True
        )

    # Normalizar alias comunes de columnas (Temperatura, Imagen y Descripción)
    mapeo_columnas = {}
    for col in df.columns:
        col_clean = col.strip().lower().replace(" ", "_")
        if col_clean in ["temperatura_ideal", "temp_ideal", "temperatura"]:
            mapeo_columnas[col] = "Temperatura_Ideal"
        elif col_clean in ["imagen", "imagen_url", "imagenurl", "foto"]:
            mapeo_columnas[col] = "imagenUrl"
        elif col_clean in ["descripcion", "descripción", "descripcion_larga", "detalles", "ingredientes_clave"]:
            mapeo_columnas[col] = "descripcion"

    if mapeo_columnas:
        df = df.rename(columns=mapeo_columnas)

    # Limpieza segura columna por columna asegurando que sean Series
    if "Temperatura_Ideal" in df.columns:
        df["Temperatura_Ideal"] = df["Temperatura_Ideal"].astype(str).str.strip().str.lower()
    else:
        df["Temperatura_Ideal"] = "indiferente"

    if "imagenUrl" in df.columns:
        df["imagenUrl"] = df["imagenUrl"].astype(str).str.strip()
        df["imagenUrl"] = df["imagenUrl"].apply(
            lambda x: None if x in ["", "none", "null", "nan", "undefined", "nat"] else x
        )
    else:
        df["imagenUrl"] = None

    if "descripcion" in df.columns:
        df["descripcion"] = df["descripcion"].astype(str).str.strip()
        df["descripcion"] = df["descripcion"].apply(
            lambda x: None if x in ["", "none", "null", "nan", "undefined", "nat"] else x
        )
    else:
        df["descripcion"] = None

    return df


def _descargar() -> dict[str, pd.DataFrame]:
    """Lee las pestañas del documento."""
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
        for nombre in COLUMNAS_REQUERIDAS.keys():
            if nombre not in hojas:
                continue
            df = _a_dataframe(hojas[nombre].get_all_values())
            tablas[nombre] = df
        return tablas
    except SheetsError:
        raise
    except Exception as exc:
        raise SheetsError(f"Error leyendo Google Sheets: {exc}") from exc


def obtener_tablas() -> dict[str, pd.DataFrame]:
    """Devuelve las pestañas como DataFrames (caché TTL + stale-if-error)."""
    return _cache.get_or_load("tablas", _descargar)


def obtener_dashboard() -> list[dict[str, str]]:
    """KPIs de 'Dashboard_Resumen'."""
    df = obtener_tablas().get("Dashboard_Resumen")
    if df is None or df.empty:
        return []
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

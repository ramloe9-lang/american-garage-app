"""Conexión segura a Google Sheets (gspread + oauth2client, Service Account) con caché."""
import json
import logging
import re
import threading
import unicodedata

import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

from .cache import StaleCache
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Listas de pestañas
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


def _limpiar_valor_texto(val: str) -> str | None:
    if val is None:
        return None
    v = str(val).strip()
    return None if v.lower() in ["", "none", "null", "nan", "undefined", "nat"] else v


def _normalizar_texto(texto: str) -> str:
    """Elimina acentos, espacios extra y convierte a minúsculas."""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    sin_acentos = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return re.sub(r"[^a-z0-9]", "", sin_acentos.lower())


def _a_dataframe(valores: list[list[str]]) -> pd.DataFrame:
    """Matriz de celdas -> DataFrame con manejo ultra seguro de columnas."""
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

    # Buscar índices de columnas usando normalización sin acentos
    col_temp = None
    col_img = None
    col_desc = None

    for col in df.columns:
        norm = _normalizar_texto(col)
        if norm in ["temperaturaideal", "tempideal", "temperatura"] and not col_temp:
            col_temp = col
        elif norm in ["imagen", "imagenurl", "foto"] and not col_img:
            col_img = col
        elif norm in ["descripcion", "descripcionlarga", "detalles", "ingredientes"] and not col_desc:
            col_desc = col

    # Asignar columnas estandarizadas de forma limpia
    if col_temp and col_temp in df.columns:
        df["Temperatura_Ideal"] = df[col_temp].astype(str).apply(lambda x: str(x).strip().lower())
    else:
        df["Temperatura_Ideal"] = "indiferente"

    if col_img and col_img in df.columns:
        df["imagenUrl"] = df[col_img].astype(str).apply(_limpiar_valor_texto)
    else:
        df["imagenUrl"] = None

    if col_desc and col_desc in df.columns:
        desc_limpia = df[col_desc].astype(str).apply(_limpiar_valor_texto)
        df["descripcion"] = desc_limpia
        df["Descripcion"] = desc_limpia
    else:
        df["descripcion"] = None
        df["Descripcion"] = None

    return df


def _descargar() -> dict[str, pd.DataFrame]:
    """Lee las pestañas del documento de forma inteligente y ultra tolerante."""
    try:
        try:
            libro = _obtener_cliente().open_by_key(settings.google_sheet_id)
        except Exception:
            logger.info("Reintentando con un cliente nuevo de gspread.")
            libro = _obtener_cliente(reiniciar=True).open_by_key(
                settings.google_sheet_id
            )
        
        hojas = {ws.title.strip(): ws for ws in libro.worksheets()}
        logger.info(f"Pestañas encontradas en Google Sheets: {list(hojas.keys())}")
        
        tablas: dict[str, pd.DataFrame] = {}
        
        # Buscamos 'Menu_Productos' o la primera hoja disponible con nombre similar
        hoja_menu_key = None
        for nombre_hoja in hojas.keys():
            if "menu" in nombre_hoja.lower() or "productos" in nombre_hoja.lower():
                hoja_menu_key = nombre_hoja
                break
        
        if not hoja_menu_key and hojas:
            # Fallback a la primera pestaña del archivo si no coincide exacto
            hoja_menu_key = list(hojas.keys())[0]

        if hoja_menu_key:
            df_menu = _a_dataframe(hojas[hoja_menu_key].get_all_values())
            tablas["Menu_Productos"] = df_menu
            tablas[hoja_menu_key] = df_menu

        # Cargar el resto de pestañas requeridas
        for nombre in COLUMNAS_REQUERIDAS.keys():
            if nombre in tablas:
                continue
            if nombre in hojas:
                tablas[nombre] = _a_dataframe(hojas[nombre].get_all_values())
            else:
                tablas[nombre] = pd.DataFrame()

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

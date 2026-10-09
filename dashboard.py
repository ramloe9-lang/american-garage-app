"""Panel interno (Streamlit) de Margin Guard.

Variables de entorno:
  API_BASE_URL         URL del backend FastAPI (por defecto http://localhost:8000)
  DASHBOARD_API_KEY    clave X-API-Key para /api/v1/dashboard (si el backend la exige)
  DASHBOARD_PASSWORD   contraseña opcional para abrir el panel
"""
import hmac
import os

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("DASHBOARD_API_KEY", "")
PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")

st.set_page_config(page_title="Margin Guard Dashboard", page_icon="🍔", layout="wide")

# --- Acceso opcional por contraseña -------------------------------------
if PASSWORD and not st.session_state.get("autenticado"):
    st.title("🔒 Margin Guard")
    clave = st.text_input("Contraseña", type="password")
    if clave:
        if hmac.compare_digest(clave, PASSWORD):
            st.session_state["autenticado"] = True
            st.rerun()
        st.error("Contraseña incorrecta.")
    st.stop()

st.title("🍔 Margin Guard - Dashboard de Menú Dinámico")
st.caption("Menú priorizado en tiempo real: inventario, mermas, márgenes y clima")

if st.button("🔄 Actualizar Datos"):
    st.cache_data.clear()


def _get(ruta: str, headers: dict | None = None) -> dict | list:
    resp = requests.get(f"{API_BASE_URL}{ruta}", headers=headers, timeout=(3, 6))
    resp.raise_for_status()
    return resp.json()


# Las excepciones no se cachean: tras una caída breve el siguiente refresco reintenta.
@st.cache_data(ttl=60)
def cargar_menu() -> list:
    data = _get("/api/v1/menu")
    return data.get("items", data.get("menu", [])) if isinstance(data, dict) else data


@st.cache_data(ttl=60)
def cargar_kpis() -> dict:
    return _get("/api/v1/dashboard", {"X-API-Key": API_KEY} if API_KEY else None)


def clima_desde_insignias(items: list) -> str:
    textos = " ".join(" ".join(i.get("insignias") or [i.get("insignia_sugerida") or ""]) for i in items)
    if "Clima Frío" in textos:
        return "🌧️ Frío (< 18 °C)"
    if "Calor" in textos:
        return "☀️ Caluroso (> 25 °C)"
    return "Templado o sin dato"


try:
    items = cargar_menu()
except Exception as exc:
    st.error(f"No se pudo obtener el menú de {API_BASE_URL}: {type(exc).__name__}")
    st.warning("Verifica que el backend FastAPI esté en línea y que API_BASE_URL sea correcta.")
    st.stop()

df = pd.DataFrame(items)

# --- KPIs ----------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Productos en menú", len(df))
con_descuento = int((df["descuento_aplicado"] > 0).sum()) if "descuento_aplicado" in df else 0
con_chef = int(sum("Chef" in " ".join(i.get("insignias") or []) for i in items))
c2.metric("Con descuento por merma", con_descuento)
c3.metric("Sugerencias del Chef", con_chef)
c4.metric("Condición climática", clima_desde_insignias(items))

st.markdown("---")
st.subheader("📋 Menú ordenado por prioridad")

if df.empty:
    st.info("No hay productos disponibles en el menú actual.")
else:
    if "insignias" in df:
        df["insignias"] = df["insignias"].apply(lambda x: " · ".join(x) if isinstance(x, list) else x)
    columnas = [c for c in ["prioridad_score", "nombre", "categoria", "precio_original",
                            "precio_final", "descuento_aplicado", "insignias",
                            "temperatura_ideal"] if c in df.columns]
    df = df[columnas]
    if "categoria" in df.columns:
        categorias = sorted({c for c in df["categoria"].dropna().astype(str) if c.strip()})
        elegida = st.selectbox("Filtrar por categoría:", ["Todas"] + categorias)
        if elegida != "Todas":
            df = df[df["categoria"] == elegida]
    st.dataframe(df, use_container_width=True, hide_index=True)

# --- KPIs de la hoja Dashboard_Resumen -------------------------------------
st.markdown("---")
st.subheader("📊 Resumen del negocio (Dashboard_Resumen)")
try:
    kpis = cargar_kpis()
    st.caption(f"Generado: {kpis.get('generado_en', 'N/D')}")
    st.dataframe(pd.DataFrame(kpis.get("kpis", [])), use_container_width=True, hide_index=True)
except requests.HTTPError as exc:
    if exc.response is not None and exc.response.status_code == 401:
        st.info("El backend exige API key: define DASHBOARD_API_KEY en el panel.")
    else:
        st.warning("No se pudo cargar el resumen de KPIs.")
except Exception:
    st.warning("No se pudo cargar el resumen de KPIs.")

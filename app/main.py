"""API FastAPI de 'Dynamic Menu & Margin Guard' - The American Garage (Wings & Burgers)."""
import logging
import secrets
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from . import sheets, weather
from .config import get_settings
from .public_menu import crear_router_publico
from .schemas import DashboardResponse, ItemMenu, Kpi
from .scoring import construir_menu

settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("margin_guard")

app = FastAPI(title="Dynamic Menu & Margin Guard", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def verificar_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Protege el dashboard (datos internos del negocio) si DASHBOARD_API_KEY está definida."""
    esperada = settings.dashboard_api_key
    if esperada and not secrets.compare_digest(x_api_key or "", esperada):
        raise HTTPException(status_code=401, detail="API key inválida o ausente.")


def _leer_hoja(funcion):
    """Traduce errores de Sheets a 503 sin filtrar detalles internos al cliente."""
    try:
        return funcion()
    except sheets.SheetsError:
        logger.exception("Error de Google Sheets")
        raise HTTPException(
            status_code=503,
            detail="Fuente de datos no disponible. Intenta en unos minutos.",
        )


@app.get("/health", include_in_schema=False)
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/v1/menu", response_model=list[ItemMenu])
def obtener_menu(response: Response, categoria: str | None = None) -> list[ItemMenu]:
    """Menú QR ordenado por prioridad (mayor a menor). Filtro opcional: ?categoria=Burgers"""
    tablas = _leer_hoja(sheets.obtener_tablas)
    try:
        temperatura = weather.obtener_temperatura()  # None => se omite la Regla D
    except Exception:  # defensa final: el clima nunca debe tumbar el menú
        logger.exception("Error inesperado consultando el clima; se omite la Regla D")
        temperatura = None

    # --- Determinar el modo de clima según los umbrales de temperatura ---
    modo_clima = "templado"
    if temperatura is not None:
        if temperatura < 18.0:
            modo_clima = "frio"
        elif temperatura > 25.0:
            modo_clima = "calor"

    # Inyectamos los datos del clima en los headers HTTP para que el frontend los lea
    response.headers["X-Temperatura"] = str(temperatura) if temperatura is not None else "16"
    response.headers["X-Clima-Modo"] = modo_clima
    # -------------------------------------------------------------------

    try:
        items = construir_menu(tablas, temperatura)
    except Exception:
        logger.exception("Error calculando el menú")
        raise HTTPException(
            status_code=500, detail="Error interno calculando el menú."
        )

    if categoria:
        items = [i for i in items if i.categoria.casefold() == categoria.casefold()]

    response.headers["Cache-Control"] = "public, max-age=60"
    return items


# REGISTRO DEL ENDPOINT PÚBLICO SEGURO (/api/v1/menu/public)
app.include_router(crear_router_publico(obtener_menu))


@app.get(
    "/api/v1/dashboard",
    response_model=DashboardResponse,
    dependencies=[Depends(verificar_api_key)],
)
def obtener_dashboard() -> DashboardResponse:
    """KPIs calculados en la pestaña Dashboard_Resumen."""
    kpis = _leer_hoja(sheets.obtener_dashboard)
    return DashboardResponse(
        generado_en=datetime.now(timezone.utc),
        total=len(kpis),
        kpis=[Kpi(**k) for k in kpis],
    )

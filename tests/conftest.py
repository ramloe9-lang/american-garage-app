"""Variables de entorno de prueba: deben definirse ANTES de importar la app."""
import os

os.environ.setdefault("GOOGLE_SHEET_ID", "hoja-de-prueba")
os.environ.setdefault("OWM_API_KEY", "clave-de-prueba")
os.environ.setdefault("OWM_CITY", "Queretaro,MX")

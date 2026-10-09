"""Modelos de respuesta de la API."""
from datetime import datetime

from pydantic import BaseModel, Field


class ItemMenu(BaseModel):
    id: str
    nombre: str
    categoria: str
    precio_original: float
    precio_final: float
    descuento_aplicado: float = Field(description="Porcentaje de descuento (15.0 = 15%).")
    insignia_sugerida: str | None = Field(description="Insignia de mayor prioridad, si aplica.")
    insignias: list[str] = Field(default_factory=list)
    prioridad_score: int = Field(ge=0, le=100)
    temperatura_ideal: str | None = Field(default=None, description="Temperatura ideal para el producto: frio, calor, o todos.") # <-- AGREGAR ESTA LÍNEA


class Kpi(BaseModel):
    metrica: str
    valor: str
    nota: str


class DashboardResponse(BaseModel):
    generado_en: datetime
    total: int
    kpis: list[Kpi]

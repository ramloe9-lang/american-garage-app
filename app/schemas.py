"""Modelos de respuesta de la API."""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, model_validator


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
    temperatura_ideal: str | None = Field(default=None, description="Temperatura ideal para el producto: frio, calor, o todos.")
    imagenUrl: str | None = Field(default=None, description="URL de la imagen del producto (mapeado desde la columna Imagen).")
    descripcion: str | None = Field(default=None, description="Descripción detallada del producto.")

    @model_validator(mode="before")
    @classmethod
    def asegurar_campos_opcionales(cls, data: Any) -> Any:
        """Validador preventivo para asegurar que variaciones de mayúsculas pasen como 'descripcion'."""
        if isinstance(data, dict):
            # Si viene con mayúscula o acento desde algún diccionario crudo, lo mapeamos a 'descripcion'
            if not data.get("descripcion"):
                data["descripcion"] = (
                    data.get("Descripcion")
                    or data.get("Descripción")
                    or data.get("descripcion_larga")
                    or data.get("detalles")
                )
            
            # Limpieza general de valores vacíos o nulos extraños
            desc = data.get("descripcion")
            if desc is not None:
                s_desc = str(desc).strip()
                if s_desc.lower() in ["", "none", "null", "undefined", "nan"]:
                    data["descripcion"] = None
                else:
                    data["descripcion"] = s_desc
                    
        return data


class Kpi(BaseModel):
    metrica: str
    valor: str
    nota: str


class DashboardResponse(BaseModel):
    generado_en: datetime
    total: int
    kpis: list[Kpi]

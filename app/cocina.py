"""Módulo de Comandas y Kitchen Display System (KDS) para /cocina."""
import threading
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

TipoEstacion = Literal["alimento", "bebida"]
FiltroEstacion = Literal["todos", "alimento", "bebida"]


class ItemComandaIn(BaseModel):
    producto_id: str
    nombre: str
    cantidad: int = Field(ge=1)
    categoria: str = ""
    notas: str | None = None
    tipo: TipoEstacion | None = None


class NuevaComandaIn(BaseModel):
    mesa: str
    numero_ronda: int = Field(default=1, ge=1)
    items: list[ItemComandaIn] = Field(min_length=1)


class CompletarComandaIn(BaseModel):
    estacion: FiltroEstacion = "todos"


class ItemComandaOut(BaseModel):
    id: str
    producto_id: str
    nombre: str
    cantidad: int
    categoria: str
    notas: str | None
    tipo: TipoEstacion
    listo: bool = False
    completado_en: datetime | None = None


class ComandaOut(BaseModel):
    id: str
    mesa: str
    numero_ronda: int
    creada_en: datetime
    items: list[ItemComandaOut]
    completada_total: bool = False
    ultima_actualizacion: datetime


# Almacenamiento en memoria protegido con Lock (ideal para instancia activa en Render)
_lock = threading.Lock()
_comandas: list[ComandaOut] = []

CATEGORIAS_BEBIDA = {
    "bebida", "bebidas", "cafe", "café", "refresco", "refrescos",
    "te", "té", "malteada", "malteadas", "cerveza", "cervezas",
    "jugo", "jugos", "agua", "aguas", "limonada", "coctel", "cóctel",
}


def _inferir_tipo(producto_id: str, categoria: str, tipo_explicito: str | None) -> TipoEstacion:
    if tipo_explicito in ("alimento", "bebida"):
        return tipo_explicito  # type: ignore[return-value]
    if producto_id.strip().upper().startswith("BEB"):
        return "bebida"
    if categoria.strip().lower() in CATEGORIAS_BEBIDA:
        return "bebida"
    return "alimento"


router = APIRouter(prefix="/api/v1/cocina", tags=["Cocina KDS"])


@router.post("/comandas", response_model=ComandaOut, status_code=201)
def crear_comanda(payload: NuevaComandaIn) -> ComandaOut:
    """Recibe una nueva ronda desde el menú del cliente."""
    ahora = datetime.now(timezone.utc)
    items_out = [
        ItemComandaOut(
            id=str(uuid.uuid4())[:8],
            producto_id=it.producto_id,
            nombre=it.nombre,
            cantidad=it.cantidad,
            categoria=it.categoria,
            notas=it.notas.strip() if it.notas and it.notas.strip() else None,
            tipo=_inferir_tipo(it.producto_id, it.categoria, it.tipo),
            listo=False,
        )
        for it in payload.items
    ]
    comanda = ComandaOut(
        id=str(uuid.uuid4())[:8],
        mesa=payload.mesa.strip(),
        numero_ronda=payload.numero_ronda,
        creada_en=ahora,
        items=items_out,
        completada_total=False,
        ultima_actualizacion=ahora,
    )
    with _lock:
        _comandas.append(comanda)
        # Mantenemos máximo las últimas 100 comandas en memoria
        if len(_comandas) > 100:
            del _comandas[:-100]
    return comanda


@router.get("/comandas", response_model=list[ComandaOut])
def listar_comandas(incluir_completadas: bool = True) -> list[ComandaOut]:
    """Devuelve las comandas ordenadas de más antigua a más reciente."""
    with _lock:
        if incluir_completadas:
            return list(_comandas)
        return [c for c in _comandas if not c.completada_total]


@router.patch("/comandas/{comanda_id}/completar", response_model=ComandaOut)
def completar_estacion(comanda_id: str, payload: CompletarComandaIn) -> ComandaOut:
    """Marca como listos únicamente los ítems visibles en la estación indicada."""
    ahora = datetime.now(timezone.utc)
    with _lock:
        comanda = next((c for c in _comandas if c.id == comanda_id), None)
        if not comanda:
            raise HTTPException(status_code=404, detail="Comanda no encontrada.")

        for item in comanda.items:
            if payload.estacion == "todos" or item.tipo == payload.estacion:
                if not item.listo:
                    item.listo = True
                    item.completado_en = ahora

        comanda.completada_total = all(i.listo for i in comanda.items)
        comanda.ultima_actualizacion = ahora
        return comanda


@router.patch("/comandas/{comanda_id}/restaurar", response_model=ComandaOut)
def restaurar_estacion(comanda_id: str, payload: CompletarComandaIn) -> ComandaOut:
    """Devuelve a pendiente los ítems de la estación (por si se marcó listo por error)."""
    ahora = datetime.now(timezone.utc)
    with _lock:
        comanda = next((c for c in _comandas if c.id == comanda_id), None)
        if not comanda:
            raise HTTPException(status_code=404, detail="Comanda no encontrada.")

        for item in comanda.items:
            if payload.estacion == "todos" or item.tipo == payload.estacion:
                item.listo = False
                item.completado_en = None

        comanda.completada_total = all(i.listo for i in comanda.items)
        comanda.ultima_actualizacion = ahora
        return comanda
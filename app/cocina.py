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
    entregado: bool = False
    entregado_en: datetime | None = None


class ComandaOut(BaseModel):
    id: str
    mesa: str
    numero_ronda: int
    creada_en: datetime
    items: list[ItemComandaOut]
    completada_total: bool = False
    ultima_actualizacion: datetime


class ItemRondaCuenta(BaseModel):
    producto_id: str
    nombre: str
    categoria: str = ""
    precio: float = Field(ge=0)
    cantidad: int = Field(ge=1)
    comentarios: str = ""
    subtotal: float = Field(ge=0)


class CrearRondaCuentaRequest(BaseModel):
    items: list[ItemRondaCuenta] = Field(min_length=1)
    subtotal_ronda: float = Field(ge=0)


class LlamarMeseroIn(BaseModel):
    mesa: str
    motivo: str = "Atención en mesa"


class LlamadoMeseroOut(BaseModel):
    id: str
    mesa: str
    motivo: str
    creado_en: datetime
    atendido: bool = False
    atendido_en: datetime | None = None


class EntregarMesaIn(BaseModel):
    comanda_id: str
    estacion: FiltroEstacion = "todos"


class RegistroEntregaOut(BaseModel):
    id: str
    comanda_id: str
    mesa: str
    numero_ronda: int
    estacion: FiltroEstacion
    items: list[ItemComandaOut]
    listo_en: datetime
    entregado_en: datetime


# Almacenamiento en memoria protegido con Lock (ideal para instancia activa en Render)
_lock = threading.Lock()
_comandas: list[ComandaOut] = []
_cuentas_por_mesa: dict[str, list[dict]] = {}
_llamados_mesero: list[LlamadoMeseroOut] = []
_entregas_historial: list[RegistroEntregaOut] = []

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
            entregado=False,
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
                item.entregado = False
                item.entregado_en = None

        comanda.completada_total = all(i.listo for i in comanda.items)
        comanda.ultima_actualizacion = ahora
        return comanda


@router.post("/estatus-mesas/entregar", response_model=RegistroEntregaOut)
def marcar_entregado_mesa(payload: EntregarMesaIn) -> RegistroEntregaOut:
    """Marca como entregados a la mesa los ítems listos de la comanda/estación y los guarda en historial."""
    ahora = datetime.now(timezone.utc)
    with _lock:
        comanda = next((c for c in _comandas if c.id == payload.comanda_id), None)
        if not comanda:
            raise HTTPException(status_code=404, detail="Comanda no encontrada.")

        items_a_entregar: list[ItemComandaOut] = []
        for item in comanda.items:
            coincide_estacion = payload.estacion == "todos" or item.tipo == payload.estacion
            if coincide_estacion and item.listo and not item.entregado:
                item.entregado = True
                item.entregado_en = ahora
                items_a_entregar.append(item.model_copy(deep=True))

        if not items_a_entregar:
            raise HTTPException(
                status_code=400,
                detail="No hay ítems listos pendientes de entrega para esta estación.",
            )

        fechas_listos = [it.completado_en for it in items_a_entregar if it.completado_en is not None]
        listo_en = min(fechas_listos) if fechas_listos else ahora

        registro = RegistroEntregaOut(
            id=str(uuid.uuid4())[:8],
            comanda_id=comanda.id,
            mesa=comanda.mesa,
            numero_ronda=comanda.numero_ronda,
            estacion=payload.estacion,
            items=items_a_entregar,
            listo_en=listo_en,
            entregado_en=ahora,
        )
        _entregas_historial.insert(0, registro)
        if len(_entregas_historial) > 150:
            del _entregas_historial[150:]

        comanda.ultima_actualizacion = ahora
        return registro


@router.get("/estatus-mesas")
def obtener_estatus_mesas() -> dict:
    """Devuelve entregas listas pendientes por mesa, llamados activos y órdenes anteriores de estatus mesas."""
    with _lock:
        pendientes_entrega: list[dict] = []
        for c in _comandas:
            listos_sin_entregar = [it for it in c.items if it.listo and not it.entregado]
            if not listos_sin_entregar:
                continue

            tipos_presentes = {it.tipo for it in listos_sin_entregar}
            if tipos_presentes == {"alimento"}:
                origen: FiltroEstacion = "alimento"
            elif tipos_presentes == {"bebida"}:
                origen = "bebida"
            else:
                origen = "todos"

            fechas_listos = [it.completado_en for it in listos_sin_entregar if it.completado_en is not None]
            listo_en = min(fechas_listos) if fechas_listos else c.ultima_actualizacion

            pendientes_entrega.append({
                "id": f"{c.id}-{origen}",
                "comanda_id": c.id,
                "mesa": c.mesa,
                "numero_ronda": c.numero_ronda,
                "estacion": origen,
                "listo_en": listo_en,
                "items": [it.model_dump() for it in listos_sin_entregar],
            })

        return {
            "entregas_pendientes": pendientes_entrega,
            "llamados_activos": [ll.model_dump() for ll in _llamados_mesero if not ll.atendido],
            "llamados_atendidos": [ll.model_dump() for ll in _llamados_mesero if ll.atendido],
            "ordenes_anteriores": [reg.model_dump() for reg in _entregas_historial],
        }


@router.post("/llamar-mesero", response_model=LlamadoMeseroOut, status_code=201)
def llamar_mesero(payload: LlamarMeseroIn) -> LlamadoMeseroOut:
    """Registra una alerta automática cuando el cliente presiona Llamar al mesero."""
    mesa_key = payload.mesa.strip()
    if not mesa_key:
        raise HTTPException(status_code=400, detail="Mesa inválida.")

    ahora = datetime.now(timezone.utc)
    with _lock:
        # Si ya existe un llamado activo sin atender para la misma mesa, actualizamos su hora
        existente = next(
            (ll for ll in _llamados_mesero if ll.mesa == mesa_key and not ll.atendido),
            None,
        )
        if existente:
            existente.creado_en = ahora
            existente.motivo = payload.motivo.strip() or "Atención en mesa"
            return existente

        llamado = LlamadoMeseroOut(
            id=str(uuid.uuid4())[:8],
            mesa=mesa_key,
            motivo=payload.motivo.strip() or "Atención en mesa",
            creado_en=ahora,
            atendido=False,
        )
        _llamados_mesero.insert(0, llamado)
        if len(_llamados_mesero) > 100:
            del _llamados_mesero[100:]
        return llamado


@router.get("/llamados-mesero", response_model=list[LlamadoMeseroOut])
def listar_llamados_mesero(incluir_atendidos: bool = True) -> list[LlamadoMeseroOut]:
    """Devuelve los llamados al mesero."""
    with _lock:
        if incluir_atendidos:
            return list(_llamados_mesero)
        return [ll for ll in _llamados_mesero if not ll.atendido]


@router.patch("/llamados-mesero/{llamado_id}/atender", response_model=LlamadoMeseroOut)
def atender_llamado_mesero(llamado_id: str) -> LlamadoMeseroOut:
    """Marca un llamado al mesero como atendido."""
    ahora = datetime.now(timezone.utc)
    with _lock:
        llamado = next((ll for ll in _llamados_mesero if ll.id == llamado_id), None)
        if not llamado:
            raise HTTPException(status_code=404, detail="Llamado de mesero no encontrado.")
        llamado.atendido = True
        llamado.atendido_en = ahora
        return llamado


@router.get("/cuentas/{mesa}")
def obtener_cuenta_mesa(mesa: str) -> dict:
    """Devuelve las rondas confirmadas vigentes de la mesa y el siguiente número de ronda."""
    mesa_key = str(mesa).strip()
    if not mesa_key:
        raise HTTPException(status_code=400, detail="Mesa inválida.")

    with _lock:
        rondas = list(_cuentas_por_mesa.get(mesa_key, []))
        return {
            "mesa": mesa_key,
            "rondas": rondas,
            "siguiente_numero_ronda": len(rondas) + 1,
        }


@router.post("/cuentas/{mesa}/rondas", status_code=201)
def agregar_ronda_cuenta(mesa: str, payload: CrearRondaCuentaRequest) -> dict:
    """Registra una ronda confirmada en la cuenta abierta de la mesa."""
    mesa_key = str(mesa).strip()
    if not mesa_key:
        raise HTTPException(status_code=400, detail="Mesa inválida.")

    with _lock:
        rondas_actuales = _cuentas_por_mesa.setdefault(mesa_key, [])
        numero_ronda = len(rondas_actuales) + 1
        nueva_ronda = {
            "numeroRonda": numero_ronda,
            "items": [item.model_dump() for item in payload.items],
            "subtotalRonda": round(float(payload.subtotal_ronda), 2),
            "confirmadaEn": datetime.now(timezone.utc).isoformat(),
        }
        rondas_actuales.append(nueva_ronda)
        return {
            "mesa": mesa_key,
            "ronda": nueva_ronda,
            "rondas": list(rondas_actuales),
        }


@router.delete("/cuentas/{mesa}")
def cerrar_cuenta_mesa(mesa: str) -> dict:
    """Limpia la cuenta abierta de la mesa al finalizar cuenta."""
    mesa_key = str(mesa).strip()
    if not mesa_key:
        raise HTTPException(status_code=400, detail="Mesa inválida.")

    with _lock:
        _cuentas_por_mesa.pop(mesa_key, None)
        return {"mesa": mesa_key, "cerrada": True}

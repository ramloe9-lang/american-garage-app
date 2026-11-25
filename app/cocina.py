"""Módulo de Comandas y Kitchen Display System (KDS) para /cocina."""
import threading
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

TipoEstacion = Literal["alimento", "bebida"]
FiltroEstacion = Literal["todos", "alimento", "bebida"]
MetodoPago = Literal["efectivo", "tarjeta"]


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
    ya_entregado_antes: bool = False


class ComandaOut(BaseModel):
    id: str
    mesa: str
    numero_ronda: int
    cuenta_id: str = "default"
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


class CuentaPorCobrarOut(BaseModel):
    id: str
    mesa: str
    cuenta_id: str
    rondas: list[dict]
    subtotal: float
    metodo_pago: MetodoPago = "efectivo"
    solicitada_en: datetime


class PagarCuentaIn(BaseModel):
    metodo_pago: MetodoPago
    propina: float = Field(default=0, ge=0)


class CuentaPagadaOut(BaseModel):
    id: str
    mesa: str
    cuenta_id: str
    rondas: list[dict]
    subtotal: float
    propina: float
    total_final: float
    metodo_pago: MetodoPago
    solicitada_en: datetime
    pagada_en: datetime


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
    cuenta_id: str = "default"
    numero_cuenta: int = 1
    estacion: FiltroEstacion
    items: list[ItemComandaOut]
    listo_en: datetime
    entregado_en: datetime


# Almacenamiento en memoria protegido con Lock
_lock = threading.Lock()
_comandas: list[ComandaOut] = []
_cuentas_por_mesa: dict[str, list[dict]] = {}
_cuenta_activa_id_por_mesa: dict[str, str] = {}
_cuentas_por_cobrar: list[CuentaPorCobrarOut] = []
_cuentas_pagadas: list[CuentaPagadaOut] = []
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


def _obtener_cuenta_id_actual(mesa_key: str) -> str:
    if mesa_key not in _cuenta_activa_id_por_mesa:
        _cuenta_activa_id_por_mesa[mesa_key] = str(uuid.uuid4())[:8]
    return _cuenta_activa_id_por_mesa[mesa_key]


def _consolidar_historial_por_cuenta_y_ronda(registros: list[RegistroEntregaOut]) -> list[dict]:
    """Agrupa entregas parciales por mesa, cuenta y ronda manteniendo numeración cronológica fija."""
    agrupados: dict[tuple[str, str, int], dict] = {}
    orden_claves: list[tuple[str, str, int]] = []

    for reg in registros:
        mesa_key = str(reg.mesa).strip()
        cuenta_key = reg.cuenta_id or reg.comanda_id
        clave = (mesa_key, cuenta_key, int(reg.numero_ronda))

        if clave not in agrupados:
            orden_claves.append(clave)
            agrupados[clave] = {
                "id": f"entrega-{reg.id}",
                "comanda_id": reg.comanda_id,
                "mesa": mesa_key,
                "numero_ronda": int(reg.numero_ronda),
                "cuenta_id": cuenta_key,
                "estacion": reg.estacion,
                "items_por_id": {},
                "listo_en": reg.listo_en,
                "entregado_en": reg.entregado_en,
            }

        destino = agrupados[clave]
        if reg.entregado_en > destino["entregado_en"]:
            destino["entregado_en"] = reg.entregado_en
        if reg.listo_en < destino["listo_en"]:
            destino["listo_en"] = reg.listo_en

        for it in reg.items:
            destino["items_por_id"][it.id] = it.model_dump()

    cronologico = sorted(
        orden_claves,
        key=lambda k: (agrupados[k]["listo_en"], agrupados[k]["entregado_en"]),
    )
    contador_cuentas_por_mesa: dict[str, dict[str, int]] = {}
    numero_por_clave: dict[tuple[str, str, int], int] = {}

    for clave in cronologico:
        entry = agrupados[clave]
        mesa_key = entry["mesa"]
        cuenta_key = entry["cuenta_id"]
        mapa_mesa = contador_cuentas_por_mesa.setdefault(mesa_key, {})
        if cuenta_key not in mapa_mesa:
            mapa_mesa[cuenta_key] = len(mapa_mesa) + 1
        numero_por_clave[clave] = mapa_mesa[cuenta_key]

    resultado: list[dict] = []
    for clave in orden_claves:
        entry = agrupados[clave]
        resultado.append({
            "id": entry["id"],
            "comanda_id": entry["comanda_id"],
            "mesa": entry["mesa"],
            "numero_ronda": entry["numero_ronda"],
            "cuenta_id": entry["cuenta_id"],
            "numero_cuenta": numero_por_clave[clave],
            "estacion": entry["estacion"],
            "items": list(entry["items_por_id"].values()),
            "listo_en": entry["listo_en"],
            "entregado_en": entry["entregado_en"],
        })
    return resultado


router = APIRouter(prefix="/api/v1/cocina", tags=["Cocina KDS"])


@router.post("/comandas", response_model=ComandaOut, status_code=201)
def crear_comanda(payload: NuevaComandaIn) -> ComandaOut:
    """Recibe una nueva ronda desde el menú del cliente."""
    ahora = datetime.now(timezone.utc)
    mesa_key = payload.mesa.strip()
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
            ya_entregado_antes=False,
        )
        for it in payload.items
    ]
    with _lock:
        cuenta_id = _obtener_cuenta_id_actual(mesa_key)
        comanda = ComandaOut(
            id=str(uuid.uuid4())[:8],
            mesa=mesa_key,
            numero_ronda=payload.numero_ronda,
            cuenta_id=cuenta_id,
            creada_en=ahora,
            items=items_out,
            completada_total=False,
            ultima_actualizacion=ahora,
        )
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
                if item.entregado:
                    item.ya_entregado_antes = True
                item.listo = False
                item.completado_en = None
                item.entregado = False
                item.entregado_en = None

        comanda.completada_total = all(i.listo for i in comanda.items)
        comanda.ultima_actualizacion = ahora
        return comanda


@router.post("/estatus-mesas/entregar", response_model=RegistroEntregaOut)
def marcar_entregado_mesa(payload: EntregarMesaIn) -> RegistroEntregaOut:
    """Marca como entregados a la mesa los ítems listos de la comanda/estación."""
    ahora = datetime.now(timezone.utc)
    with _lock:
        comanda = next((c for c in _comandas if c.id == payload.comanda_id), None)
        if not comanda:
            raise HTTPException(status_code=404, detail="Comanda no encontrada.")

        items_a_entregar: list[ItemComandaOut] = []
        items_nuevos_para_historial: list[ItemComandaOut] = []

        for item in comanda.items:
            coincide_estacion = payload.estacion == "todos" or item.tipo == payload.estacion
            if coincide_estacion and item.listo and not item.entregado:
                item.entregado = True
                item.entregado_en = ahora
                copia = item.model_copy(deep=True)
                items_a_entregar.append(copia)
                if not item.ya_entregado_antes:
                    items_nuevos_para_historial.append(copia)
                item.ya_entregado_antes = True

        if not items_a_entregar:
            raise HTTPException(
                status_code=400,
                detail="No hay ítems listos pendientes de entrega para esta estación.",
            )

        fechas_listos = [it.completado_en for it in items_a_entregar if it.completado_en is not None]
        listo_en = min(fechas_listos) if fechas_listos else ahora

        items_historial = items_nuevos_para_historial or items_a_entregar
        registro = RegistroEntregaOut(
            id=str(uuid.uuid4())[:8],
            comanda_id=comanda.id,
            mesa=comanda.mesa,
            numero_ronda=comanda.numero_ronda,
            cuenta_id=comanda.cuenta_id,
            estacion=payload.estacion,
            items=items_historial,
            listo_en=listo_en,
            entregado_en=ahora,
        )

        if items_nuevos_para_historial:
            _entregas_historial.insert(0, registro)
            if len(_entregas_historial) > 150:
                del _entregas_historial[150:]

        comanda.ultima_actualizacion = ahora
        return registro


@router.get("/estatus-mesas")
def obtener_estatus_mesas() -> dict:
    """Devuelve entregas listas pendientes por mesa, llamados activos y órdenes anteriores por cuenta/ronda."""
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
                "cuenta_id": c.cuenta_id,
                "estacion": origen,
                "listo_en": listo_en,
                "items": [it.model_dump() for it in listos_sin_entregar],
            })

        return {
            "entregas_pendientes": pendientes_entrega,
            "llamados_activos": [ll.model_dump() for ll in _llamados_mesero if not ll.atendido],
            "llamados_atendidos": [ll.model_dump() for ll in _llamados_mesero if ll.atendido],
            "ordenes_anteriores": _consolidar_historial_por_cuenta_y_ronda(_entregas_historial),
        }


@router.post("/llamar-mesero", response_model=LlamadoMeseroOut, status_code=201)
def llamar_mesero(payload: LlamarMeseroIn) -> LlamadoMeseroOut:
    """Registra una alerta automática cuando el cliente presiona Llamar al mesero."""
    mesa_key = payload.mesa.strip()
    if not mesa_key:
        raise HTTPException(status_code=400, detail="Mesa inválida.")

    ahora = datetime.now(timezone.utc)
    with _lock:
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
        _obtener_cuenta_id_actual(mesa_key)
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
        _obtener_cuenta_id_actual(mesa_key)
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
def cerrar_cuenta_mesa(
    mesa: str,
    metodo_pago: MetodoPago | None = None,
    payload: dict | None = Body(default=None),
) -> dict:
    """Envía el resumen de la cuenta a Cuentas por Cobrar, limpia la mesa e inicia nuevo ciclo."""
    mesa_key = str(mesa).strip()
    if not mesa_key:
        raise HTTPException(status_code=400, detail="Mesa inválida.")

    pago_elegido: MetodoPago = "efectivo"
    if metodo_pago in ("efectivo", "tarjeta"):
        pago_elegido = metodo_pago
    elif isinstance(payload, dict) and payload.get("metodo_pago") in ("efectivo", "tarjeta"):
        pago_elegido = payload["metodo_pago"]  # type: ignore[assignment]

    ahora = datetime.now(timezone.utc)
    with _lock:
        rondas_cerradas = _cuentas_por_mesa.pop(mesa_key, [])
        cuenta_id_cerrada = _obtener_cuenta_id_actual(mesa_key)

        if rondas_cerradas:
            subtotal = round(sum(float(r.get("subtotalRonda", 0)) for r in rondas_cerradas), 2)
            cuenta_cobro = CuentaPorCobrarOut(
                id=str(uuid.uuid4())[:8],
                mesa=mesa_key,
                cuenta_id=cuenta_id_cerrada,
                rondas=list(rondas_cerradas),
                subtotal=subtotal,
                metodo_pago=pago_elegido,
                solicitada_en=ahora,
            )
            _cuentas_por_cobrar.insert(0, cuenta_cobro)

        _cuenta_activa_id_por_mesa[mesa_key] = str(uuid.uuid4())[:8]
        return {"mesa": mesa_key, "cerrada": True, "metodo_pago": pago_elegido}


@router.get("/cuentas-por-cobrar", response_model=list[CuentaPorCobrarOut])
def listar_cuentas_por_cobrar() -> list[CuentaPorCobrarOut]:
    """Devuelve las cuentas finalizadas por el comensal pendientes de cobro."""
    with _lock:
        return list(_cuentas_por_cobrar)


@router.post("/cuentas-por-cobrar/{cuenta_cobro_id}/pagar", response_model=CuentaPagadaOut)
def registrar_pago_cuenta(cuenta_cobro_id: str, payload: PagarCuentaIn) -> CuentaPagadaOut:
    """Marca la cuenta como pagada, la quita de pendientes y guarda venta + propina."""
    ahora = datetime.now(timezone.utc)
    with _lock:
        idx = next((i for i, c in enumerate(_cuentas_por_cobrar) if c.id == cuenta_cobro_id), None)
        if idx is None:
            raise HTTPException(status_code=404, detail="Cuenta por cobrar no encontrada.")

        cuenta = _cuentas_por_cobrar.pop(idx)
        propina_val = round(float(payload.propina), 2)
        total_final = round(cuenta.subtotal + propina_val, 2)

        pagada = CuentaPagadaOut(
            id=cuenta.id,
            mesa=cuenta.mesa,
            cuenta_id=cuenta.cuenta_id,
            rondas=cuenta.rondas,
            subtotal=cuenta.subtotal,
            propina=propina_val,
            total_final=total_final,
            metodo_pago=payload.metodo_pago,
            solicitada_en=cuenta.solicitada_en,
            pagada_en=ahora,
        )
        _cuentas_pagadas.insert(0, pagada)
        return pagada


@router.get("/cuentas-pagadas", response_model=list[CuentaPagadaOut])
def listar_cuentas_pagadas() -> list[CuentaPagadaOut]:
    """Devuelve el historial de cuentas pagadas (base para el resumen del día)."""
    with _lock:
        return list(_cuentas_pagadas)


@router.get("/resumen-dia")
def obtener_resumen_dia() -> dict:
    """Calcula el resumen del día a partir de las cuentas pagadas."""
    with _lock:
        hoy_utc = datetime.now(timezone.utc).date()
        cuentas_hoy = [c for c in _cuentas_pagadas if c.pagada_en.date() == hoy_utc]
        base_cuentas = cuentas_hoy if cuentas_hoy else list(_cuentas_pagadas)

        subtotal_ventas = round(sum(float(c.subtotal) for c in base_cuentas), 2)
        propinas_totales = round(sum(float(c.propina) for c in base_cuentas), 2)
        total_general = round(sum(float(c.total_final) for c in base_cuentas), 2)

        total_efectivo = round(
            sum(float(c.total_final) for c in base_cuentas if c.metodo_pago == "efectivo"), 2
        )
        total_tarjeta = round(
            sum(float(c.total_final) for c in base_cuentas if c.metodo_pago == "tarjeta"), 2
        )

        conteo_general: dict[str, dict] = {}
        conteo_alimento: dict[str, dict] = {}
        conteo_bebida: dict[str, dict] = {}
        conteo_combo: dict[str, dict] = {}

        for cuenta in base_cuentas:
            for ronda in cuenta.rondas:
                for item in ronda.get("items", []):
                    nombre = str(item.get("nombre", "")).strip()
                    if not nombre:
                        continue
                    cantidad = int(item.get("cantidad", 0))
                    categoria = str(item.get("categoria", "")).strip()
                    producto_id = str(item.get("producto_id", "")).strip()
                    es_combo = "combo" in categoria.lower() or "combo" in nombre.lower()
                    tipo_item = _inferir_tipo(producto_id, categoria, None)

                    clave = nombre.lower()
                    entry_gen = conteo_general.setdefault(clave, {"nombre": nombre, "cantidad": 0})
                    entry_gen["cantidad"] += cantidad

                    if es_combo:
                        entry_cbo = conteo_combo.setdefault(clave, {"nombre": nombre, "cantidad": 0})
                        entry_cbo["cantidad"] += cantidad

                    if tipo_item == "bebida":
                        entry_beb = conteo_bebida.setdefault(clave, {"nombre": nombre, "cantidad": 0})
                        entry_beb["cantidad"] += cantidad
                    else:
                        entry_ali = conteo_alimento.setdefault(clave, {"nombre": nombre, "cantidad": 0})
                        entry_ali["cantidad"] += cantidad

        def _mas_vendido(dic: dict[str, dict]) -> dict | None:
            if not dic:
                return None
            ganador = max(dic.values(), key=lambda x: x["cantidad"])
            return ganador if ganador["cantidad"] > 0 else None

        return {
            "cantidad_cuentas": len(base_cuentas),
            "subtotal_ventas": subtotal_ventas,
            "propinas_totales": propinas_totales,
            "total_general": total_general,
            "total_efectivo": total_efectivo,
            "total_tarjeta": total_tarjeta,
            "producto_mas_vendido": _mas_vendido(conteo_general),
            "alimento_mas_vendido": _mas_vendido(conteo_alimento),
            "bebida_mas_vendido": _mas_vendido(conteo_bebida),
            "combo_mas_vendido": _mas_vendido(conteo_combo),
        }


@router.post("/cerrar-dia")
def cerrar_dia_actual() -> dict:
    """Reinicia absolutamente todo el estado de cocina, estatus de mesas, cuentas y ventas del día."""
    with _lock:
        total_cerradas = len(_cuentas_pagadas)
        _cuentas_pagadas.clear()
        _cuentas_por_cobrar.clear()
        _cuentas_por_mesa.clear()
        _cuenta_activa_id_por_mesa.clear()
        _comandas.clear()
        _entregas_historial.clear()
        _llamados_mesero.clear()
        return {"cerrado": True, "cuentas_cerradas": total_cerradas}

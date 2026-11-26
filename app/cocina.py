"""Módulo de Comandas y Kitchen Display System (KDS) para /cocina."""
import calendar
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

TipoEstacion = Literal["alimento", "bebida"]
FiltroEstacion = Literal["todos", "alimento", "bebida"]
MetodoPago = Literal["efectivo", "tarjeta"]

TZ_LOCAL = ZoneInfo("America/Mexico_City")

MESES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

DIAS_ES = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}


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
    numero_cuenta: int = 1
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
    numero_cuenta: int = 1
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
    numero_cuenta: int = 1
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
_numero_cuenta_activa_por_mesa: dict[str, int] = {}
_contador_cuentas_por_mesa: dict[str, int] = {}
_cuentas_por_cobrar: list[CuentaPorCobrarOut] = []
_cuentas_pagadas: list[CuentaPagadaOut] = []
_llamados_mesero: list[LlamadoMeseroOut] = []
_entregas_historial: list[RegistroEntregaOut] = []

# Control de día operativo (3am a 3am) y registro mensual de ventas
_reinicios_por_dia_op: dict[str, int] = {}
_mes_registro_actual: tuple[int, int] | None = None  # (year, month)
_registro_ventas_dias: dict[str, dict] = {}  # clave: YYYY-MM-DD del día operativo

CATEGORIAS_BEBIDA = {
    "bebida", "bebidas", "cafe", "café", "refresco", "refrescos",
    "te", "té", "malteada", "malteadas", "cerveza", "cervezas",
    "jugo", "jugos", "agua", "aguas", "limonada", "coctel", "cóctel",
}


def _obtener_dia_operativo(dt_utc: datetime | None = None) -> tuple[str, str, int, int]:
    """
    Calcula el día operativo que inicia a las 03:00 AM y termina a las 03:00 AM del día siguiente.
    Retorna: (clave_yyyy_mm_dd, etiqueta_legible, mes_num, anio_num)
    """
    base = (dt_utc or datetime.now(timezone.utc)).astimezone(TZ_LOCAL)
    if base.hour < 3:
        dia_op = (base - timedelta(days=1)).date()
    else:
        dia_op = base.date()

    clave = dia_op.isoformat()
    etiqueta = f"{DIAS_ES[dia_op.weekday()]} {dia_op.day} de {MESES_ES[dia_op.month]} {dia_op.year}"
    return clave, etiqueta, dia_op.month, dia_op.year


def _sincronizar_ciclo_mensual(anio: int, mes: int) -> None:
    """Reinicia el registro de ventas cada 1.º de mes o al alcanzar 30 días distintos."""
    global _mes_registro_actual
    if _mes_registro_actual != (anio, mes):
        _registro_ventas_dias.clear()
        _mes_registro_actual = (anio, mes)
    elif len(_registro_ventas_dias) >= 30:
        _registro_ventas_dias.clear()


def _inferir_tipo(producto_id: str, categoria: str, tipo_explicito: str | None) -> TipoEstacion:
    if tipo_explicito in ("alimento", "bebida"):
        return tipo_explicito  # type: ignore[return-value]
    if producto_id.strip().upper().startswith("BEB"):
        return "bebida"
    if categoria.strip().lower() in CATEGORIAS_BEBIDA:
        return "bebida"
    return "alimento"


def _es_combo(producto_id: str, categoria: str, nombre: str) -> bool:
    txt = f"{producto_id} {categoria} {nombre}".lower()
    return "combo" in txt


def _calcular_metricas_cuentas(cuentas: list[CuentaPagadaOut]) -> dict:
    subtotal_ventas = round(sum(float(c.subtotal) for c in cuentas), 2)
    propinas_totales = round(sum(float(c.propina) for c in cuentas), 2)
    total_general = round(sum(float(c.total_final) for c in cuentas), 2)
    total_efectivo = round(
        sum(float(c.total_final) for c in cuentas if c.metodo_pago == "efectivo"), 2
    )
    total_tarjeta = round(
        sum(float(c.total_final) for c in cuentas if c.metodo_pago == "tarjeta"), 2
    )

    conteo_general: dict[str, dict] = {}
    conteo_alimento: dict[str, dict] = {}
    conteo_bebida: dict[str, dict] = {}
    conteo_combo: dict[str, dict] = {}

    for cuenta in cuentas:
        for ronda in cuenta.rondas:
            for item in ronda.get("items", []):
                nombre = str(item.get("nombre", "")).strip()
                if not nombre:
                    continue
                cantidad = int(item.get("cantidad", 0))
                subtotal_item = round(float(item.get("subtotal", 0)), 2)
                categoria = str(item.get("categoria", "")).strip()
                producto_id = str(item.get("producto_id", "")).strip()
                es_combo = _es_combo(producto_id, categoria, nombre)
                tipo_item = _inferir_tipo(producto_id, categoria, None)

                clave = nombre.lower()
                entry_gen = conteo_general.setdefault(
                    clave, {"nombre": nombre, "cantidad": 0, "subtotal": 0.0}
                )
                entry_gen["cantidad"] += cantidad
                entry_gen["subtotal"] = round(entry_gen["subtotal"] + subtotal_item, 2)

                if es_combo:
                    entry_cbo = conteo_combo.setdefault(
                        clave, {"nombre": nombre, "cantidad": 0, "subtotal": 0.0}
                    )
                    entry_cbo["cantidad"] += cantidad
                    entry_cbo["subtotal"] = round(entry_cbo["subtotal"] + subtotal_item, 2)

                if tipo_item == "bebida":
                    entry_beb = conteo_bebida.setdefault(
                        clave, {"nombre": nombre, "cantidad": 0, "subtotal": 0.0}
                    )
                    entry_beb["cantidad"] += cantidad
                    entry_beb["subtotal"] = round(entry_beb["subtotal"] + subtotal_item, 2)
                else:
                    entry_ali = conteo_alimento.setdefault(
                        clave, {"nombre": nombre, "cantidad": 0, "subtotal": 0.0}
                    )
                    entry_ali["cantidad"] += cantidad
                    entry_ali["subtotal"] = round(entry_ali["subtotal"] + subtotal_item, 2)

    def _mas_vendido(dic: dict[str, dict]) -> dict | None:
        if not dic:
            return None
        ganador = max(dic.values(), key=lambda x: x["cantidad"])
        if ganador["cantidad"] <= 0:
            return None
        return {"nombre": ganador["nombre"], "cantidad": ganador["cantidad"]}

    alimentos_lista = sorted(conteo_alimento.values(), key=lambda x: (-x["cantidad"], x["nombre"]))
    bebidas_lista = sorted(conteo_bebida.values(), key=lambda x: (-x["cantidad"], x["nombre"]))
    combos_lista = sorted(conteo_combo.values(), key=lambda x: (-x["cantidad"], x["nombre"]))

    return {
        "cantidad_cuentas": len(cuentas),
        "subtotal_ventas": subtotal_ventas,
        "propinas_totales": propinas_totales,
        "total_general": total_general,
        "total_efectivo": total_efectivo,
        "total_tarjeta": total_tarjeta,
        "producto_mas_vendido": _mas_vendido(conteo_general),
        "alimento_mas_vendido": _mas_vendido(conteo_alimento),
        "bebida_mas_vendido": _mas_vendido(conteo_bebida),
        "combo_mas_vendido": _mas_vendido(conteo_combo),
        "desglose_alimentos": alimentos_lista,
        "subtotal_alimentos": round(sum(x["subtotal"] for x in alimentos_lista), 2),
        "desglose_bebidas": bebidas_lista,
        "subtotal_bebidas": round(sum(x["subtotal"] for x in bebidas_lista), 2),
        "desglose_combos": combos_lista,
        "subtotal_combos": round(sum(x["subtotal"] for x in combos_lista), 2),
    }


def _asegurar_cuenta_activa(mesa_key: str) -> tuple[str, int]:
    """Devuelve (cuenta_id, numero_cuenta) asignando numeración cronológica fija por mesa."""
    if mesa_key not in _cuenta_activa_id_por_mesa:
        siguiente_num = _contador_cuentas_por_mesa.get(mesa_key, 0) + 1
        _contador_cuentas_por_mesa[mesa_key] = siguiente_num
        _cuenta_activa_id_por_mesa[mesa_key] = str(uuid.uuid4())[:8]
        _numero_cuenta_activa_por_mesa[mesa_key] = siguiente_num
    return (
        _cuenta_activa_id_por_mesa[mesa_key],
        _numero_cuenta_activa_por_mesa.get(mesa_key, 1),
    )


def _rotar_cuenta_activa(mesa_key: str) -> tuple[str, int]:
    """Crea una nueva cuenta activa para la mesa con el siguiente número cronológico."""
    siguiente_num = _contador_cuentas_por_mesa.get(mesa_key, 0) + 1
    _contador_cuentas_por_mesa[mesa_key] = siguiente_num
    nuevo_id = str(uuid.uuid4())[:8]
    _cuenta_activa_id_por_mesa[mesa_key] = nuevo_id
    _numero_cuenta_activa_por_mesa[mesa_key] = siguiente_num
    return nuevo_id, siguiente_num


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
                "numero_cuenta": int(reg.numero_cuenta or 1),
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
            mapa_mesa[cuenta_key] = entry["numero_cuenta"] or (len(mapa_mesa) + 1)
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
        cuenta_id, numero_cuenta = _asegurar_cuenta_activa(mesa_key)
        comanda = ComandaOut(
            id=str(uuid.uuid4())[:8],
            mesa=mesa_key,
            numero_ronda=payload.numero_ronda,
            cuenta_id=cuenta_id,
            numero_cuenta=numero_cuenta,
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
            numero_cuenta=comanda.numero_cuenta,
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
                "numero_cuenta": c.numero_cuenta,
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
        cuenta_id, numero_cuenta = _asegurar_cuenta_activa(mesa_key)
        rondas = list(_cuentas_por_mesa.get(mesa_key, []))
        return {
            "mesa": mesa_key,
            "cuenta_id": cuenta_id,
            "numero_cuenta": numero_cuenta,
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
        cuenta_id, numero_cuenta = _asegurar_cuenta_activa(mesa_key)
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
            "cuenta_id": cuenta_id,
            "numero_cuenta": numero_cuenta,
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
        cuenta_id_cerrada, numero_cuenta_cerrada = _asegurar_cuenta_activa(mesa_key)

        if rondas_cerradas:
            subtotal = round(sum(float(r.get("subtotalRonda", 0)) for r in rondas_cerradas), 2)
            cuenta_cobro = CuentaPorCobrarOut(
                id=str(uuid.uuid4())[:8],
                mesa=mesa_key,
                cuenta_id=cuenta_id_cerrada,
                numero_cuenta=numero_cuenta_cerrada,
                rondas=list(rondas_cerradas),
                subtotal=subtotal,
                metodo_pago=pago_elegido,
                solicitada_en=ahora,
            )
            _cuentas_por_cobrar.append(cuenta_cobro)

        _rotar_cuenta_activa(mesa_key)
        return {
            "mesa": mesa_key,
            "numero_cuenta": numero_cuenta_cerrada,
            "cerrada": True,
            "metodo_pago": pago_elegido,
        }


@router.get("/cuentas-por-cobrar", response_model=list[CuentaPorCobrarOut])
def listar_cuentas_por_cobrar() -> list[CuentaPorCobrarOut]:
    """Devuelve las cuentas finalizadas por el comensal pendientes de cobro en orden cronológico."""
    with _lock:
        return sorted(_cuentas_por_cobrar, key=lambda c: (c.numero_cuenta, c.solicitada_en))


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
            numero_cuenta=cuenta.numero_cuenta,
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
    """Devuelve el historial de cuentas pagadas."""
    with _lock:
        return list(_cuentas_pagadas)


@router.get("/resumen-dia")
def obtener_resumen_dia() -> dict:
    """Calcula el resumen del día operativo actual (3am a 3am) y el número de reinicio del día."""
    with _lock:
        clave_dia, etiqueta_dia, mes_num, anio_num = _obtener_dia_operativo()
        _sincronizar_ciclo_mensual(anio_num, mes_num)

        cuentas_dia = [
            c for c in _cuentas_pagadas if _obtener_dia_operativo(c.pagada_en)[0] == clave_dia
        ]
        metricas = _calcular_metricas_cuentas(cuentas_dia)
        reinicios_previos = _reinicios_por_dia_op.get(clave_dia, 0)
        numero_reinicio_dia = reinicios_previos + 1

        return {
            "fecha_operativa": clave_dia,
            "fecha_operativa_etiqueta": etiqueta_dia,
            "numero_reinicio_dia": numero_reinicio_dia,
            "reinicios_realizados_hoy": reinicios_previos,
            **metricas,
        }


@router.post("/cerrar-dia")
def cerrar_dia_actual() -> dict:
    """
    Registra el corte en el historial diario (acumulando cuentas y desgloses del día operativo 3am-3am)
    y reinicia todo el estado activo de cocina, estatus de mesas y cuentas.
    """
    with _lock:
        clave_dia, etiqueta_dia, mes_num, anio_num = _obtener_dia_operativo()
        _sincronizar_ciclo_mensual(anio_num, mes_num)

        reinicio_num = _reinicios_por_dia_op.get(clave_dia, 0) + 1
        _reinicios_por_dia_op[clave_dia] = reinicio_num

        metricas_corte = _calcular_metricas_cuentas(_cuentas_pagadas)
        total_cerradas = len(_cuentas_pagadas)

        registro_existente = _registro_ventas_dias.get(clave_dia)
        if not registro_existente:
            _registro_ventas_dias[clave_dia] = {
                "fecha_operativa": clave_dia,
                "fecha_operativa_etiqueta": etiqueta_dia,
                "reinicios_realizados": reinicio_num,
                "cuentas_totales": metricas_corte["cantidad_cuentas"],
                "subtotal_ventas": metricas_corte["subtotal_ventas"],
                "propinas_totales": metricas_corte["propinas_totales"],
                "total_general": metricas_corte["total_general"],
                "total_efectivo": metricas_corte["total_efectivo"],
                "total_tarjeta": metricas_corte["total_tarjeta"],
                "producto_mas_vendido": metricas_corte["producto_mas_vendido"],
                "alimento_mas_vendido": metricas_corte["alimento_mas_vendido"],
                "bebida_mas_vendido": metricas_corte["bebida_mas_vendido"],
                "combo_mas_vendido": metricas_corte["combo_mas_vendido"],
                "desglose_alimentos": metricas_corte["desglose_alimentos"],
                "subtotal_alimentos": metricas_corte["subtotal_alimentos"],
                "desglose_bebidas": metricas_corte["desglose_bebidas"],
                "subtotal_bebidas": metricas_corte["subtotal_bebidas"],
                "desglose_combos": metricas_corte["desglose_combos"],
                "subtotal_combos": metricas_corte["subtotal_combos"],
            }
        else:
            # Acumulamos las cuentas y montos del nuevo reinicio en el mismo día operativo
            cuentas_acum = int(registro_existente["cuentas_totales"]) + int(
                metricas_corte["cantidad_cuentas"]
            )
            sub_acum = round(
                float(registro_existente["subtotal_ventas"]) + float(metricas_corte["subtotal_ventas"]),
                2,
            )
            prop_acum = round(
                float(registro_existente["propinas_totales"]) + float(metricas_corte["propinas_totales"]),
                2,
            )
            tot_acum = round(
                float(registro_existente["total_general"]) + float(metricas_corte["total_general"]),
                2,
            )
            efe_acum = round(
                float(registro_existente["total_efectivo"]) + float(metricas_corte["total_efectivo"]),
                2,
            )
            tar_acum = round(
                float(registro_existente["total_tarjeta"]) + float(metricas_corte["total_tarjeta"]),
                2,
            )

            def _combinar_desgloses(base_list: list[dict], extra_list: list[dict]) -> list[dict]:
                mapa: dict[str, dict] = {}
                for row in base_list + extra_list:
                    key = str(row["nombre"]).strip().lower()
                    actual = mapa.setdefault(
                        key, {"nombre": row["nombre"], "cantidad": 0, "subtotal": 0.0}
                    )
                    actual["cantidad"] += int(row["cantidad"])
                    actual["subtotal"] = round(actual["subtotal"] + float(row["subtotal"]), 2)
                return sorted(mapa.values(), key=lambda x: (-x["cantidad"], x["nombre"]))

            ali_comb = _combinar_desgloses(
                registro_existente.get("desglose_alimentos", []),
                metricas_corte["desglose_alimentos"],
            )
            beb_comb = _combinar_desgloses(
                registro_existente.get("desglose_bebidas", []),
                metricas_corte["desglose_bebidas"],
            )
            cbo_comb = _combinar_desgloses(
                registro_existente.get("desglose_combos", []),
                metricas_corte["desglose_combos"],
            )

            gen_mapa: dict[str, dict] = {}
            for row in ali_comb + beb_comb:
                k = str(row["nombre"]).strip().lower()
                g = gen_mapa.setdefault(k, {"nombre": row["nombre"], "cantidad": 0})
                g["cantidad"] += int(row["cantidad"])

            def _top(lista_ord: list[dict]) -> dict | None:
                if not lista_ord or lista_ord[0]["cantidad"] <= 0:
                    return None
                return {"nombre": lista_ord[0]["nombre"], "cantidad": lista_ord[0]["cantidad"]}

            top_gen = None
            if gen_mapa:
                g_win = max(gen_mapa.values(), key=lambda x: x["cantidad"])
                if g_win["cantidad"] > 0:
                    top_gen = g_win

            registro_existente.update({
                "reinicios_realizados": reinicio_num,
                "cuentas_totales": cuentas_acum,
                "subtotal_ventas": sub_acum,
                "propinas_totales": prop_acum,
                "total_general": tot_acum,
                "total_efectivo": efe_acum,
                "total_tarjeta": tar_acum,
                "producto_mas_vendido": top_gen,
                "alimento_mas_vendido": _top(ali_comb),
                "bebida_mas_vendido": _top(beb_comb),
                "combo_mas_vendido": _top(cbo_comb),
                "desglose_alimentos": ali_comb,
                "subtotal_alimentos": round(sum(x["subtotal"] for x in ali_comb), 2),
                "desglose_bebidas": beb_comb,
                "subtotal_bebidas": round(sum(x["subtotal"] for x in beb_comb), 2),
                "desglose_combos": cbo_comb,
                "subtotal_combos": round(sum(x["subtotal"] for x in cbo_comb), 2),
            })

        _cuentas_pagadas.clear()
        _cuentas_por_cobrar.clear()
        _cuentas_por_mesa.clear()
        _cuenta_activa_id_por_mesa.clear()
        _numero_cuenta_activa_por_mesa.clear()
        _contador_cuentas_por_mesa.clear()
        _comandas.clear()
        _entregas_historial.clear()
        _llamados_mesero.clear()
        return {
            "cerrado": True,
            "cuentas_cerradas": total_cerradas,
            "numero_reinicio_dia": reinicio_num,
        }


@router.get("/registro-ventas")
def obtener_registro_ventas() -> dict:
    """Devuelve el historial mensual de registro de ventas y el aviso de proximidad a reinicio."""
    with _lock:
        _, _, mes_num, anio_num = _obtener_dia_operativo()
        _sincronizar_ciclo_mensual(anio_num, mes_num)

        hoy_local = datetime.now(timezone.utc).astimezone(TZ_LOCAL).date()
        ultimo_dia_mes = calendar.monthrange(hoy_local.year, hoy_local.month)[1]
        dias_restantes_mes = max(0, ultimo_dia_mes - hoy_local.day)
        dias_restantes_cupo = max(0, 30 - len(_registro_ventas_dias))
        dias_restantes = min(dias_restantes_mes, dias_restantes_cupo)
        alerta_reinicio_proximo = dias_restantes <= 3

        dias_ordenados = sorted(
            _registro_ventas_dias.values(),
            key=lambda d: d["fecha_operativa"],
            reverse=True,
        )

        return {
            "mes_nombre": MESES_ES[mes_num],
            "anio": anio_num,
            "dias_restantes_reseteo": dias_restantes,
            "alerta_reinicio_proximo": alerta_reinicio_proximo,
            "registros": dias_ordenados,
        }

"""Módulo de Comandas, Cuentas, Cortes del Día y Registro de Ventas para /cocina."""
import json
import os
import threading
import uuid
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
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
DIAS_SEMANA_ES = [
    "Lunes",
    "Martes",
    "Miercoles",
    "Jueves",
    "Viernes",
    "Sabado",
    "Domingo",
]

DATA_DIR = Path(os.environ.get("VISIAK_DATA_DIR") or os.environ.get("RENDER_DISK_PATH") or "data")
REGISTRO_FILE = DATA_DIR / "visiak_registro_ventas.json"


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


class EntregarMesaIn(BaseModel):
    comanda_id: str
    estacion: FiltroEstacion = "todos"


class LlamadoMeseroIn(BaseModel):
    mesa: str
    motivo: str = "Solicita atención en mesa"


class PagarCuentaIn(BaseModel):
    metodo_pago: MetodoPago = "efectivo"
    propina: float = Field(default=0.0, ge=0)


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
    cuenta_id: str
    numero_cuenta: int
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


class CuentaPagadaRecord(BaseModel):
    id: str
    mesa: str
    cuenta_id: str
    numero_cuenta: int
    rondas: list[dict[str, Any]]
    subtotal: float
    propina: float
    total_final: float
    metodo_pago: MetodoPago
    pagada_en: datetime


_lock = threading.Lock()
_comandas: list[ComandaOut] = []
_cuentas_por_mesa: dict[str, list[dict[str, Any]]] = {}
_contador_cuenta_por_mesa: dict[str, int] = {}
_cuenta_activa_id_por_mesa: dict[str, str] = {}
_entregas_anteriores: list[dict[str, Any]] = []
_llamados_mesero: list[dict[str, Any]] = []
_cuentas_por_cobrar: dict[str, dict[str, Any]] = {}
_cuentas_pagadas: list[CuentaPagadaRecord] = []

_reinicios_por_fecha_operativa: dict[str, int] = {}
_registro_ventas_dias: dict[str, dict[str, Any]] = {}
_ciclo_anio_mes: str = ""

CATEGORIAS_BEBIDA = {
    "bebida",
    "bebidas",
    "cafe",
    "café",
    "refresco",
    "refrescos",
    "te",
    "té",
    "malteada",
    "malteadas",
    "cerveza",
    "cervezas",
    "jugo",
    "jugos",
    "agua",
    "aguas",
    "limonada",
    "coctel",
    "cóctel",
}


def _inferir_tipo(producto_id: str, categoria: str, tipo_explicito: str | None) -> TipoEstacion:
    if tipo_explicito in ("alimento", "bebida"):
        return tipo_explicito  # type: ignore[return-value]
    if producto_id.strip().upper().startswith("BEB"):
        return "bebida"
    if categoria.strip().lower() in CATEGORIAS_BEBIDA:
        return "bebida"
    return "alimento"


def _es_combo(producto_id: str, categoria: str, nombre: str) -> bool:
    texto = f"{producto_id} {categoria} {nombre}".lower()
    return "combo" in texto


def _obtener_fecha_operativa_local(ahora_utc: datetime | None = None) -> tuple[str, str, str]:
    """Día operativo de 3:00 AM a 3:00 AM en zona horaria local."""
    base_utc = ahora_utc or datetime.now(timezone.utc)
    local_dt = base_utc.astimezone(TZ_LOCAL)
    if local_dt.time() < time(3, 0):
        fecha_op = (local_dt - timedelta(days=1)).date()
    else:
        fecha_op = local_dt.date()

    iso_str = fecha_op.isoformat()
    dia_sem = DIAS_SEMANA_ES[fecha_op.weekday()]
    mes_nom = MESES_ES.get(fecha_op.month, str(fecha_op.month))
    etiqueta = f"{dia_sem} {fecha_op.day} de {mes_nom} {fecha_op.year}"
    ciclo_key = f"{fecha_op.year}-{fecha_op.month:02d}"
    return iso_str, etiqueta, ciclo_key


def _dias_restantes_y_alerta(ahora_utc: datetime | None = None) -> tuple[int, bool]:
    base_utc = ahora_utc or datetime.now(timezone.utc)
    local_dt = base_utc.astimezone(TZ_LOCAL)
    hoy = local_dt.date()
    if hoy.month == 12:
        siguiente_primero = hoy.replace(year=hoy.year + 1, month=1, day=1)
    else:
        siguiente_primero = hoy.replace(month=hoy.month + 1, day=1)
    dias_restantes = max(0, (siguiente_primero - hoy).days)
    alerta = dias_restantes <= 3 or len(_registro_ventas_dias) >= 27
    return dias_restantes, alerta


def _guardar_estado_persistente_locked() -> None:
    """Guarda el registro de ventas y el contador de reinicios en disco."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "ciclo_anio_mes": _ciclo_anio_mes,
            "reinicios_por_fecha_operativa": _reinicios_por_fecha_operativa,
            "registro_ventas_dias": _registro_ventas_dias,
        }
        tmp_file = REGISTRO_FILE.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_file.replace(REGISTRO_FILE)
    except OSError:
        pass


def _cargar_estado_persistente() -> None:
    """Carga el registro de ventas desde disco al iniciar."""
    global _ciclo_anio_mes, _reinicios_por_fecha_operativa, _registro_ventas_dias
    _, _, ciclo_actual = _obtener_fecha_operativa_local()
    with _lock:
        _ciclo_anio_mes = ciclo_actual
        if not REGISTRO_FILE.exists():
            return
        try:
            raw = json.loads(REGISTRO_FILE.read_text(encoding="utf-8"))
            guardado_ciclo = str(raw.get("ciclo_anio_mes") or "")
            dias_guardados = raw.get("registro_ventas_dias") or {}
            reinicios_guardados = raw.get("reinicios_por_fecha_operativa") or {}

            if guardado_ciclo and guardado_ciclo != ciclo_actual:
                _registro_ventas_dias = {}
                _reinicios_por_fecha_operativa = {}
                _guardar_estado_persistente_locked()
            else:
                _registro_ventas_dias = dict(dias_guardados)
                _reinicios_por_fecha_operativa = {
                    str(k): int(v) for k, v in reinicios_guardados.items()
                }
                if len(_registro_ventas_dias) > 30:
                    claves_ordenadas = sorted(_registro_ventas_dias.keys())
                    for k in claves_ordenadas[:-30]:
                        _registro_ventas_dias.pop(k, None)
                    _guardar_estado_persistente_locked()
        except Exception:
            pass


_cargar_estado_persistente()


def _asegurar_ciclo_mensual_locked(ciclo_actual: str) -> None:
    global _ciclo_anio_mes
    if _ciclo_anio_mes and _ciclo_anio_mes != ciclo_actual:
        _registro_ventas_dias.clear()
        _reinicios_por_fecha_operativa.clear()
        _guardar_estado_persistente_locked()
    elif len(_registro_ventas_dias) >= 30:
        _registro_ventas_dias.clear()
        _reinicios_por_fecha_operativa.clear()
        _guardar_estado_persistente_locked()
    _ciclo_anio_mes = ciclo_actual


def _asegurar_cuenta_mesa_locked(mesa_key: str) -> tuple[str, int]:
    if mesa_key not in _cuenta_activa_id_por_mesa:
        siguiente_num = _contador_cuenta_por_mesa.get(mesa_key, 0) + 1
        _contador_cuenta_por_mesa[mesa_key] = siguiente_num
        _cuenta_activa_id_por_mesa[mesa_key] = f"cta-{mesa_key}-{siguiente_num}-{str(uuid.uuid4())[:6]}"
    return _cuenta_activa_id_por_mesa[mesa_key], _contador_cuenta_por_mesa[mesa_key]


def _calcular_metricas_cuentas(cuentas: list[CuentaPagadaRecord]) -> dict[str, Any]:
    subtotal_ventas = round(sum(float(c.subtotal) for c in cuentas), 2)
    propinas_totales = round(sum(float(c.propina) for c in cuentas), 2)
    total_general = round(sum(float(c.total_final) for c in cuentas), 2)
    total_efectivo = round(
        sum(float(c.total_final) for c in cuentas if c.metodo_pago == "efectivo"), 2
    )
    total_tarjeta = round(
        sum(float(c.total_final) for c in cuentas if c.metodo_pago == "tarjeta"), 2
    )

    conteo_general: dict[str, dict[str, Any]] = {}
    conteo_alimento: dict[str, dict[str, Any]] = {}
    conteo_bebida: dict[str, dict[str, Any]] = {}
    conteo_combo: dict[str, dict[str, Any]] = {}

    desglose_alimento_map: dict[str, dict[str, Any]] = {}
    desglose_bebida_map: dict[str, dict[str, Any]] = {}
    desglose_combo_map: dict[str, dict[str, Any]] = {}

    subtotal_alimentos = 0.0
    subtotal_bebidas = 0.0
    subtotal_combos = 0.0

    for cuenta in cuentas:
        for ronda in cuenta.rondas:
            for item in ronda.get("items", []):
                nombre = str(item.get("nombre", "")).strip()
                if not nombre:
                    continue
                cantidad = max(1, int(item.get("cantidad", 1)))
                precio = float(item.get("precio", 0))
                subtotal_item = float(item.get("subtotal", precio * cantidad))
                categoria = str(item.get("categoria", "")).strip()
                producto_id = str(item.get("producto_id", "")).strip()
                tipo_item = _inferir_tipo(producto_id, categoria, None)
                es_combo = _es_combo(producto_id, categoria, nombre)
                clave = nombre.lower()

                g = conteo_general.setdefault(clave, {"nombre": nombre, "cantidad": 0})
                g["cantidad"] += cantidad

                if tipo_item == "bebida":
                    b = conteo_bebida.setdefault(clave, {"nombre": nombre, "cantidad": 0})
                    b["cantidad"] += cantidad
                    d_beb = desglose_bebida_map.setdefault(
                        clave, {"nombre": nombre, "cantidad": 0, "subtotal": 0.0}
                    )
                    d_beb["cantidad"] += cantidad
                    d_beb["subtotal"] = round(d_beb["subtotal"] + subtotal_item, 2)
                    subtotal_bebidas = round(subtotal_bebidas + subtotal_item, 2)
                else:
                    a = conteo_alimento.setdefault(clave, {"nombre": nombre, "cantidad": 0})
                    a["cantidad"] += cantidad
                    d_ali = desglose_alimento_map.setdefault(
                        clave, {"nombre": nombre, "cantidad": 0, "subtotal": 0.0}
                    )
                    d_ali["cantidad"] += cantidad
                    d_ali["subtotal"] = round(d_ali["subtotal"] + subtotal_item, 2)
                    subtotal_alimentos = round(subtotal_alimentos + subtotal_item, 2)

                if es_combo:
                    cbo = conteo_combo.setdefault(clave, {"nombre": nombre, "cantidad": 0})
                    cbo["cantidad"] += cantidad
                    d_cbo = desglose_combo_map.setdefault(
                        clave, {"nombre": nombre, "cantidad": 0, "subtotal": 0.0}
                    )
                    d_cbo["cantidad"] += cantidad
                    d_cbo["subtotal"] = round(d_cbo["subtotal"] + subtotal_item, 2)
                    subtotal_combos = round(subtotal_combos + subtotal_item, 2)

    def _mas_vendido(dic: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        if not dic:
            return None
        ganador = max(dic.values(), key=lambda x: x["cantidad"])
        return ganador if ganador["cantidad"] > 0 else None

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
        "desglose_alimentos": sorted(
            desglose_alimento_map.values(), key=lambda x: (-x["cantidad"], x["nombre"])
        ),
        "subtotal_alimentos": subtotal_alimentos,
        "desglose_bebidas": sorted(
            desglose_bebida_map.values(), key=lambda x: (-x["cantidad"], x["nombre"])
        ),
        "subtotal_bebidas": subtotal_bebidas,
        "desglose_combos": sorted(
            desglose_combo_map.values(), key=lambda x: (-x["cantidad"], x["nombre"])
        ),
        "subtotal_combos": subtotal_combos,
    }


router = APIRouter(prefix="/api/v1/cocina", tags=["Cocina KDS"])


@router.post("/comandas", response_model=ComandaOut, status_code=201)
def crear_comanda(payload: NuevaComandaIn) -> ComandaOut:
    ahora = datetime.now(timezone.utc)
    mesa_key = payload.mesa.strip()
    with _lock:
        cuenta_id, numero_cuenta = _asegurar_cuenta_mesa_locked(mesa_key)
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
        if len(_comandas) > 200:
            del _comandas[:-200]
        return comanda


@router.get("/comandas", response_model=list[ComandaOut])
def listar_comandas(incluir_completadas: bool = True) -> list[ComandaOut]:
    with _lock:
        if incluir_completadas:
            return list(_comandas)
        return [c for c in _comandas if not c.completada_total]


@router.patch("/comandas/{comanda_id}/completar", response_model=ComandaOut)
def completar_estacion(comanda_id: str, payload: CompletarComandaIn) -> ComandaOut:
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


@router.get("/estatus-mesas")
def obtener_estatus_mesas() -> dict[str, Any]:
    with _lock:
        entregas_pendientes: list[dict[str, Any]] = []
        for c in _comandas:
            listos_sin_entregar = [it for it in c.items if it.listo and not it.entregado]
            if not listos_sin_entregar:
                continue

            por_tipo: dict[str, list[ItemComandaOut]] = {}
            for it in listos_sin_entregar:
                por_tipo.setdefault(it.tipo, []).append(it)

            for tipo_key, grupo_items in por_tipo.items():
                timestamps = [
                    it.completado_en or c.ultima_actualizacion for it in grupo_items
                ]
                listo_en = max(timestamps).isoformat()
                entregas_pendientes.append(
                    {
                        "id": f"ent-{c.id}-{tipo_key}",
                        "comanda_id": c.id,
                        "mesa": c.mesa,
                        "numero_ronda": c.numero_ronda,
                        "cuenta_id": c.cuenta_id,
                        "numero_cuenta": c.numero_cuenta,
                        "estacion": tipo_key,
                        "listo_en": listo_en,
                        "items": [it.model_dump(mode="json") for it in grupo_items],
                    }
                )

        llamados_activos = [ll for ll in _llamados_mesero if not ll.get("atendido")]
        llamados_atendidos = [ll for ll in _llamados_mesero if ll.get("atendido")]

        return {
            "entregas_pendientes": entregas_pendientes,
            "llamados_activos": llamados_activos,
            "llamados_atendidos": llamados_atendidos,
            "ordenes_anteriores": list(_entregas_anteriores),
        }


@router.post("/estatus-mesas/entregar")
def marcar_entregado_mesa(payload: EntregarMesaIn) -> dict[str, Any]:
    ahora = datetime.now(timezone.utc)
    with _lock:
        comanda = next((c for c in _comandas if c.id == payload.comanda_id), None)
        if not comanda:
            raise HTTPException(status_code=404, detail="Comanda no encontrada.")

        items_entregados: list[ItemComandaOut] = []
        for it in comanda.items:
            if it.listo and not it.entregado:
                if payload.estacion == "todos" or it.tipo == payload.estacion:
                    it.entregado = True
                    it.entregado_en = ahora
                    items_entregados.append(it)

        if items_entregados:
            listo_en = max(
                (it.completado_en or comanda.ultima_actualizacion) for it in items_entregados
            ).isoformat()
            _entregas_anteriores.append(
                {
                    "id": f"reg-{comanda.id}-{str(uuid.uuid4())[:6]}",
                    "comanda_id": comanda.id,
                    "mesa": comanda.mesa,
                    "numero_ronda": comanda.numero_ronda,
                    "cuenta_id": comanda.cuenta_id,
                    "numero_cuenta": comanda.numero_cuenta,
                    "estacion": payload.estacion,
                    "items": [it.model_dump(mode="json") for it in items_entregados],
                    "listo_en": listo_en,
                    "entregado_en": ahora.isoformat(),
                }
            )
            comanda.ultima_actualizacion = ahora

        return {"entregado": True, "cantidad_items": len(items_entregados)}


@router.post("/llamados-mesero", status_code=201)
def crear_llamado_mesero(payload: LlamadoMeseroIn) -> dict[str, Any]:
    ahora = datetime.now(timezone.utc)
    llamado = {
        "id": str(uuid.uuid4())[:8],
        "mesa": payload.mesa.strip(),
        "motivo": payload.motivo.strip() or "Solicita atención en mesa",
        "creado_en": ahora.isoformat(),
        "atendido": False,
        "atendido_en": None,
    }
    with _lock:
        _llamados_mesero.append(llamado)
    return llamado


@router.patch("/llamados-mesero/{llamado_id}/atender")
def atender_llamado_mesero(llamado_id: str) -> dict[str, Any]:
    ahora = datetime.now(timezone.utc)
    with _lock:
        llamado = next((ll for ll in _llamados_mesero if ll.get("id") == llamado_id), None)
        if not llamado:
            raise HTTPException(status_code=404, detail="Llamado no encontrado.")
        llamado["atendido"] = True
        llamado["atendido_en"] = ahora.isoformat()
        return llamado


@router.get("/cuentas/{mesa}")
def obtener_cuenta_mesa(mesa: str) -> dict[str, Any]:
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
def agregar_ronda_cuenta(mesa: str, payload: CrearRondaCuentaRequest) -> dict[str, Any]:
    mesa_key = str(mesa).strip()
    if not mesa_key:
        raise HTTPException(status_code=400, detail="Mesa inválida.")

    with _lock:
        _asegurar_cuenta_mesa_locked(mesa_key)
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
def cerrar_cuenta_mesa(mesa: str, metodo_pago: MetodoPago = "efectivo") -> dict[str, Any]:
    mesa_key = str(mesa).strip()
    if not mesa_key:
        raise HTTPException(status_code=400, detail="Mesa inválida.")

    ahora = datetime.now(timezone.utc)
    with _lock:
        rondas = list(_cuentas_por_mesa.pop(mesa_key, []))
        cuenta_id, numero_cuenta = _asegurar_cuenta_mesa_locked(mesa_key)
        _cuenta_activa_id_por_mesa.pop(mesa_key, None)

        subtotal = round(sum(float(r.get("subtotalRonda", 0)) for r in rondas), 2)
        cuenta_cobro_id = f"cobro-{mesa_key}-{numero_cuenta}-{str(uuid.uuid4())[:6]}"
        if rondas:
            _cuentas_por_cobrar[cuenta_cobro_id] = {
                "id": cuenta_cobro_id,
                "mesa": mesa_key,
                "cuenta_id": cuenta_id,
                "numero_cuenta": numero_cuenta,
                "rondas": rondas,
                "subtotal": subtotal,
                "metodo_pago": metodo_pago,
                "solicitada_en": ahora.isoformat(),
            }

        return {
            "mesa": mesa_key,
            "cerrada": True,
            "cuenta_por_cobrar_id": cuenta_cobro_id if rondas else None,
        }


@router.get("/cuentas-por-cobrar")
def listar_cuentas_por_cobrar() -> list[dict[str, Any]]:
    with _lock:
        return list(_cuentas_por_cobrar.values())


@router.post("/cuentas-por-cobrar/{cuenta_cobro_id}/pagar")
def pagar_cuenta_por_cobrar(cuenta_cobro_id: str, payload: PagarCuentaIn) -> dict[str, Any]:
    ahora = datetime.now(timezone.utc)
    with _lock:
        cuenta = _cuentas_por_cobrar.pop(cuenta_cobro_id, None)
        if not cuenta:
            raise HTTPException(status_code=404, detail="Cuenta por cobrar no encontrada.")

        subtotal = round(float(cuenta.get("subtotal", 0)), 2)
        propina = round(float(payload.propina), 2)
        total_final = round(subtotal + propina, 2)

        registro = CuentaPagadaRecord(
            id=str(uuid.uuid4())[:8],
            mesa=str(cuenta.get("mesa", "")),
            cuenta_id=str(cuenta.get("cuenta_id", "")),
            numero_cuenta=int(cuenta.get("numero_cuenta", 1)),
            rondas=list(cuenta.get("rondas", [])),
            subtotal=subtotal,
            propina=propina,
            total_final=total_final,
            metodo_pago=payload.metodo_pago,
            pagada_en=ahora,
        )
        _cuentas_pagadas.append(registro)
        return {"pagada": True, "registro": registro.model_dump(mode="json")}


@router.get("/resumen-dia")
def obtener_resumen_dia() -> dict[str, Any]:
    fecha_op_iso, fecha_op_etiqueta, ciclo_actual = _obtener_fecha_operativa_local()
    with _lock:
        _asegurar_ciclo_mensual_locked(ciclo_actual)
        reinicios_hechos = int(_reinicios_por_fecha_operativa.get(fecha_op_iso, 0))
        numero_reinicio_dia = reinicios_hechos + 1

        cuentas_del_dia = [
            c
            for c in _cuentas_pagadas
            if _obtener_fecha_operativa_local(c.pagada_en)[0] == fecha_op_iso
        ]
        metricas = _calcular_metricas_cuentas(cuentas_del_dia)

        registro_previo = _registro_ventas_dias.get(fecha_op_iso)
        cuentas_previas_reinicios = int(registro_previo.get("cuentas_totales", 0)) if registro_previo else 0

        return {
            "fecha_operativa": fecha_op_iso,
            "fecha_operativa_etiqueta": fecha_op_etiqueta,
            "numero_reinicio_dia": numero_reinicio_dia,
            "reinicios_realizados_hoy": reinicios_hechos,
            "cantidad_cuentas": metricas["cantidad_cuentas"],
            "cuentas_acumuladas_dia_con_reinicios": cuentas_previas_reinicios
            + metricas["cantidad_cuentas"],
            **metricas,
        }


@router.post("/cerrar-dia")
def cerrar_dia_actual() -> dict[str, Any]:
    fecha_op_iso, fecha_op_etiqueta, ciclo_actual = _obtener_fecha_operativa_local()
    with _lock:
        _asegurar_ciclo_mensual_locked(ciclo_actual)
        reinicio_num = int(_reinicios_por_fecha_operativa.get(fecha_op_iso, 0)) + 1
        _reinicios_por_fecha_operativa[fecha_op_iso] = reinicio_num

        metricas_corte = _calcular_metricas_cuentas(list(_cuentas_pagadas))

        existente = _registro_ventas_dias.get(fecha_op_iso)
        if not existente:
            existente = {
                "fecha_operativa": fecha_op_iso,
                "fecha_operativa_etiqueta": fecha_op_etiqueta,
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
            existente["reinicios_realizados"] = reinicio_num
            existente["cuentas_totales"] = int(existente.get("cuentas_totales", 0)) + int(
                metricas_corte["cantidad_cuentas"]
            )
            existente["subtotal_ventas"] = round(
                float(existente.get("subtotal_ventas", 0)) + float(metricas_corte["subtotal_ventas"]),
                2,
            )
            existente["propinas_totales"] = round(
                float(existente.get("propinas_totales", 0))
                + float(metricas_corte["propinas_totales"]),
                2,
            )
            existente["total_general"] = round(
                float(existente.get("total_general", 0)) + float(metricas_corte["total_general"]),
                2,
            )
            existente["total_efectivo"] = round(
                float(existente.get("total_efectivo", 0))
                + float(metricas_corte["total_efectivo"]),
                2,
            )
            existente["total_tarjeta"] = round(
                float(existente.get("total_tarjeta", 0)) + float(metricas_corte["total_tarjeta"]),
                2,
            )
            existente["subtotal_alimentos"] = round(
                float(existente.get("subtotal_alimentos", 0))
                + float(metricas_corte["subtotal_alimentos"]),
                2,
            )
            existente["subtotal_bebidas"] = round(
                float(existente.get("subtotal_bebidas", 0))
                + float(metricas_corte["subtotal_bebidas"]),
                2,
            )
            existente["subtotal_combos"] = round(
                float(existente.get("subtotal_combos", 0))
                + float(metricas_corte["subtotal_combos"]),
                2,
            )

            def _fusionar_desgloses(
                prev_list: list[dict[str, Any]], nueva_list: list[dict[str, Any]]
            ) -> list[dict[str, Any]]:
                mapa: dict[str, dict[str, Any]] = {}
                for it in prev_list:
                    k = str(it.get("nombre", "")).strip().lower()
                    if not k:
                        continue
                    mapa[k] = {
                        "nombre": it.get("nombre", ""),
                        "cantidad": int(it.get("cantidad", 0)),
                        "subtotal": round(float(it.get("subtotal", 0)), 2),
                    }
                for it in nueva_list:
                    k = str(it.get("nombre", "")).strip().lower()
                    if not k:
                        continue
                    if k not in mapa:
                        mapa[k] = {
                            "nombre": it.get("nombre", ""),
                            "cantidad": 0,
                            "subtotal": 0.0,
                        }
                    mapa[k]["cantidad"] += int(it.get("cantidad", 0))
                    mapa[k]["subtotal"] = round(
                        mapa[k]["subtotal"] + float(it.get("subtotal", 0)), 2
                    )
                return sorted(mapa.values(), key=lambda x: (-x["cantidad"], x["nombre"]))

            existente["desglose_alimentos"] = _fusionar_desgloses(
                existente.get("desglose_alimentos", []),
                metricas_corte["desglose_alimentos"],
            )
            existente["desglose_bebidas"] = _fusionar_desgloses(
                existente.get("desglose_bebidas", []),
                metricas_corte["desglose_bebidas"],
            )
            existente["desglose_combos"] = _fusionar_desgloses(
                existente.get("desglose_combos", []),
                metricas_corte["desglose_combos"],
            )

            def _max_item(lista: list[dict[str, Any]]) -> dict[str, Any] | None:
                if not lista:
                    return None
                top = max(lista, key=lambda x: x["cantidad"])
                return {"nombre": top["nombre"], "cantidad": top["cantidad"]} if top["cantidad"] > 0 else None

            existente["alimento_mas_vendido"] = _max_item(existente["desglose_alimentos"])
            existente["bebida_mas_vendido"] = _max_item(existente["desglose_bebidas"])
            existente["combo_mas_vendido"] = _max_item(existente["desglose_combos"])

            todos_items = (
                existente["desglose_alimentos"]
                + existente["desglose_bebidas"]
                + existente["desglose_combos"]
            )
            existente["producto_mas_vendido"] = _max_item(todos_items)

        _registro_ventas_dias[fecha_op_iso] = existente
        _guardar_estado_persistente_locked()

        total_cerradas = len(_cuentas_pagadas)
        _cuentas_pagadas.clear()
        _comandas.clear()
        _cuentas_por_mesa.clear()
        _cuenta_activa_id_por_mesa.clear()
        _entregas_anteriores.clear()
        _llamados_mesero.clear()
        _cuentas_por_cobrar.clear()

        return {
            "cerrado": True,
            "cuentas_cerradas": total_cerradas,
            "fecha_operativa": fecha_op_iso,
            "numero_reinicio_dia": reinicio_num,
        }


@router.get("/registro-ventas")
def obtener_registro_ventas() -> dict[str, Any]:
    _, _, ciclo_actual = _obtener_fecha_operativa_local()
    ahora_local = datetime.now(timezone.utc).astimezone(TZ_LOCAL)
    dias_restantes, alerta = _dias_restantes_y_alerta()

    with _lock:
        _asegurar_ciclo_mensual_locked(ciclo_actual)
        registros_ordenados = [
            _registro_ventas_dias[k] for k in sorted(_registro_ventas_dias.keys(), reverse=True)
        ]

    return {
        "mes_nombre": MESES_ES.get(ahora_local.month, str(ahora_local.month)),
        "anio": ahora_local.year,
        "dias_restantes_reseteo": dias_restantes,
        "alerta_reinicio_proximo": alerta,
        "registros": registros_ordenados,
    }

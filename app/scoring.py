"""Motor de priorización del menú (score 0-100) y Margin Guard."""
import logging
import unicodedata
from dataclasses import dataclass, field

import pandas as pd

from .schemas import ItemMenu
from .utils import a_float, a_fraccion, normalizar, separar_referencias

logger = logging.getLogger(__name__)

# --- Parámetros del negocio -------------------------------------------------
PUNTAJE_BASE = 50
BONO_URGENTE = 40
PENALIZACION_MARGEN = 30
BONO_CLIMA = 20
MARGEN_MINIMO = 0.45
TEMP_FRIA_C = 18.0
TEMP_CALUROSA_C = 25.0
MAX_DESCUENTO = 0.70  # tope de seguridad ante errores de captura en la hoja (ej. 150%)

INSIGNIA_CHEF = "👨‍🍳 Sugerencia del Chef"
INSIGNIA_FRIO = "🌧️ Especial para Clima Frío"
INSIGNIA_CALOR = "☀️ Recomendación para el Calor"

# Estados ya normalizados
ESTADO_AGOTADO = "agotado"
ESTADO_URGENTE = "urgente (vence hoy)"
ESTADO_COSTO_ELEVADO = "costo elevado"

# Temperatura_Ideal aceptada (sin acentos, en minúsculas)
TEMPS_CALIENTES = {"caliente", "calido"}
TEMPS_FRIAS = {"frio", "fresco", "helado", "calor"}


def _sin_acentos(texto: object) -> str:
    """Minúsculas, sin espacios extremos ni acentos ('Frío' -> 'frio')."""
    s = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).strip().lower()


@dataclass
class Insumo:
    id: str
    nombre: str
    estado: str
    costo_anterior: float
    costo_actual: float
    descuento: float


@dataclass
class Producto:
    id: str
    nombre: str
    categoria: str
    precio: float
    costo: float
    temperatura: str
    ingredientes: list[str] = field(default_factory=list)
    estado_stock: str = ""


class IndiceInsumos:
    """Resuelve referencias de Ingredientes_Clave por ID o nombre."""

    def __init__(self, df: pd.DataFrame) -> None:
        self.por_id: dict[str, Insumo] = {}
        self.por_nombre: dict[str, Insumo] = {}
        for r in df.to_dict("records"):
            id_insumo = str(r.get("ID_Insumo", "")).strip().upper()
            if not id_insumo:
                continue
            ins = Insumo(
                id=id_insumo,
                nombre=str(r.get("Nombre_Insumo", "")).strip(),
                estado=normalizar(r.get("Estado_Insumo", "")),
                costo_anterior=a_float(r.get("Costo_Anterior")),
                costo_actual=a_float(r.get("Costo_Actual")),
                descuento=a_fraccion(r.get("Descuento_Sugerido")),
            )
            self.por_id.setdefault(ins.id, ins)  # ID duplicado: gana la primera fila
            if ins.nombre:
                self.por_nombre.setdefault(normalizar(ins.nombre), ins)

    def resolver(self, referencias: list[str]) -> list[Insumo]:
        resueltos = []
        for ref in referencias:
            ins = self.por_id.get(ref.upper()) or self.por_nombre.get(normalizar(ref))
            if ins is None:
                logger.warning("Ingrediente '%s' no existe en inventario.", ref)
                continue
            resueltos.append(ins)
        return resueltos


def _temperatura_ideal(r: dict) -> str:
    valor = r.get("Temperatura_Ideal") or r.get("temperatura_ideal") or r.get("temp_ideal") or ""
    return normalizar(valor)


def cargar_productos(tablas: dict[str, pd.DataFrame]) -> list[Producto]:
    """Une platillos y bebidas. Omite filas sin ID, sin nombre o con precio <= 0;
    ante IDs duplicados gana la primera fila."""
    productos: list[Producto] = []
    vistos: set[str] = set()

    def agregar(p: Producto) -> None:
        clave = p.id.upper()
        if p.precio <= 0:
            logger.warning("Producto '%s' omitido: precio de venta inválido.", p.id)
            return
        if clave in vistos:
            logger.warning("ID de producto duplicado '%s': se conserva la primera fila.", p.id)
            return
        vistos.add(clave)
        productos.append(p)

    for r in tablas["Menu_Productos"].to_dict("records"):
        pid = str(r.get("ID_Producto", "")).strip()
        nombre = str(r.get("Nombre_Producto", "")).strip()
        if not pid or not nombre:
            continue
        agregar(Producto(
            id=pid, nombre=nombre, categoria=str(r.get("Categoria", "")).strip(),
            precio=a_float(r.get("Precio_Venta")), costo=a_float(r.get("Costo_Estimado")),
            temperatura=_temperatura_ideal(r),
            ingredientes=separar_referencias(r.get("Ingredientes_Clave", "")),
        ))

    for r in tablas["Inventario_Bebidas"].to_dict("records"):
        pid = str(r.get("ID_Bebida", "")).strip()
        nombre = str(r.get("Nombre_Producto", "")).strip()
        if not pid or not nombre:
            continue
        agregar(Producto(
            id=pid, nombre=nombre, categoria=str(r.get("Categoria", "")).strip(),
            precio=a_float(r.get("Precio_Venta")), costo=a_float(r.get("Precio_Costo")),
            temperatura=_temperatura_ideal(r),
            estado_stock=normalizar(r.get("Estado_Stock", "")),
        ))
    return productos


def recalcular_costo(producto: Producto, insumos: list[Insumo], total_ingredientes: int = 0) -> float:
    """Costo real del platillo tras alzas de insumos clave.

    El costo se reparte entre TODOS los ingredientes listados; los que no existen en
    el inventario cuentan sin cambio de costo (no inflan la cuota de los demás).
    """
    if not insumos or producto.costo <= 0:
        return producto.costo
    n = max(total_ingredientes, len(insumos))
    cuota = producto.costo / n
    total = cuota * (n - len(insumos))
    for ins in insumos:
        factor = 1.0
        if ins.estado == ESTADO_COSTO_ELEVADO and ins.costo_anterior > 0:
            factor = ins.costo_actual / ins.costo_anterior
        total += cuota * factor
    return total


def evaluar_producto(p: Producto, indice: IndiceInsumos, temp_c: float | None) -> ItemMenu | None:
    """Aplica las reglas A-D estrictamente."""
    insumos = indice.resolver(p.ingredientes)

    # Regla A: disponibilidad
    if p.estado_stock == ESTADO_AGOTADO or any(i.estado == ESTADO_AGOTADO for i in insumos):
        return None

    score = PUNTAJE_BASE
    insignias: list[str] = []
    descuento = 0.0

    # Regla B: urgencia de caducidad (solo insumos que vencen hoy)
    urgentes = [i for i in insumos if i.estado == ESTADO_URGENTE]
    if urgentes:
        score += BONO_URGENTE
        insignias.append(INSIGNIA_CHEF)
        descuento = min(max(i.descuento for i in urgentes), MAX_DESCUENTO)

    # Regla C: Margin Guard
    if any(i.estado == ESTADO_COSTO_ELEVADO for i in insumos) and p.precio > 0 and p.costo > 0:
        costo_real = recalcular_costo(p, insumos, len(p.ingredientes))
        # Redondeo: 50 * 1.1 = 55.00000000000001 y un margen de exactamente 45% se penalizaba
        margen = round((p.precio - costo_real) / p.precio, 4)
        if margen < MARGEN_MINIMO:
            score -= PENALIZACION_MARGEN

    # Regla D: clima estricto
    #   < 18 °C  => solo "caliente" recibe insignia de frío
    #   > 25 °C  => solo frío/fresco/helado/calor recibe insignia de calor
    #   18-25 °C => ningún producto recibe insignia de clima
    temp_norm = _sin_acentos(p.temperatura)
    if temp_c is not None:
        if temp_c < TEMP_FRIA_C:
            if temp_norm in TEMPS_CALIENTES:
                score += BONO_CLIMA
                insignias.append(INSIGNIA_FRIO)
        elif temp_c > TEMP_CALUROSA_C:
            if temp_norm in TEMPS_FRIAS:
                score += BONO_CLIMA
                insignias.append(INSIGNIA_CALOR)

    return ItemMenu(
        id=p.id,
        nombre=p.nombre,
        categoria=p.categoria,
        precio_original=round(p.precio, 2),
        precio_final=round(p.precio * (1 - descuento), 2),
        descuento_aplicado=round(descuento * 100, 2),
        insignia_sugerida=insignias[0] if insignias else None,
        insignias=insignias,
        prioridad_score=max(0, min(100, score)),
        temperatura_ideal=p.temperatura,
    )


def construir_menu(tablas: dict[str, pd.DataFrame], temp_c: float | None) -> list[ItemMenu]:
    """Menú final ordenado. Un producto roto se omite sin tumbar el menú completo."""
    indice = IndiceInsumos(tablas["Inventario_Insumos_Mermas"])
    items: list[ItemMenu] = []
    for p in cargar_productos(tablas):
        try:
            item = evaluar_producto(p, indice, temp_c)
        except Exception:
            logger.exception("Producto '%s' omitido por error al evaluarlo.", p.id)
            continue
        if item is not None:
            items.append(item)
    items.sort(key=lambda it: (-it.prioridad_score, it.nombre.casefold()))
    return items

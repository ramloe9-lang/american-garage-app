import { grupoDe, sinAcentos } from './categories'
import type {
  ApiClima, ApiItem, ApiMenuResponse, Clima, Menu, MenuItem, ModoClima, TempIdeal,
} from './types'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')
const MENU_PATH = import.meta.env.VITE_MENU_PATH ?? '/api/v1/menu/public'

export class ErrorMenu extends Error {
  tipo: 'red' | 'servidor'
  constructor(tipo: 'red' | 'servidor', mensaje: string) {
    super(mensaje)
    this.name = 'ErrorMenu'
    this.tipo = tipo
  }
}

// --- Clima ------------------------------------------------------------------------------------
const TEMP_FRIA = 18
const TEMP_CALUROSA = 25
const CONFIAR_EN_CONDICION = true

function modoDesdeTemperatura(temp: number): ModoClima {
  if (temp < TEMP_FRIA) return 'frio'
  if (temp > TEMP_CALUROSA) return 'calor'
  return 'templado'
}

function modoDesdeCondicion(condicion: unknown): ModoClima | null {
  const s = sinAcentos(String(condicion ?? ''))
  if (/calor|calid/.test(s)) return 'calor'
  if (/fri|fresc/.test(s)) return 'frio'
  if (/templad/.test(s)) return 'templado'
  return null
}

function normalizarClima(c: ApiClima | null | undefined): Clima | null {
  if (!c || typeof c.temperatura !== 'number') return null
  const modo = (CONFIAR_EN_CONDICION && modoDesdeCondicion(c.condicion)) || modoDesdeTemperatura(c.temperatura)
  return { ciudad: c.ciudad, temperatura: c.temperatura, modo, descripcion: c.descripcion }
}

/** Consulta el clima actual en tiempo real para Querétaro si la API del backend no lo envía */
async function obtenerClimaEnTiempoReal(ciudad = 'Queretaro'): Promise<Clima | null> {
  try {
    const res = await fetch(`https://wttr.in/${encodeURIComponent(ciudad)}?format=j1`)
    if (!res.ok) return null

    const data = await res.json()
    const current = data.current_condition?.[0]
    if (!current) return null

    const temp = parseFloat(current.temp_C)
    const desc = current.lang_es?.[0]?.value || current.weatherDesc?.[0]?.value || 'Clima actual'

    return {
      ciudad: 'Querétaro',
      temperatura: temp,
      modo: modoDesdeTemperatura(temp),
      descripcion: desc,
    }
  } catch (err) {
    console.warn('[clima] No se pudo obtener el clima en tiempo real:', err)
    return null
  }
}

// --- Lectura tolerante de campos --------------------------------------------------------------
const canon = (k: string) => k.toLowerCase().replace(/[^a-z0-9]/g, '')

function crearLector(raw: ApiItem) {
  const indice = new Map(Object.keys(raw).map((k) => [canon(k), k]))
  return (...claves: string[]): unknown => {
    for (const c of claves) {
      const k = indice.get(canon(c))
      const v = k === undefined ? undefined : raw[k]
      if (v !== undefined && v !== null && v !== '') return v
    }
    return undefined
  }
}

function aNumero(v: unknown): number | undefined {
  if (typeof v === 'number' && Number.isFinite(v)) return v
  if (typeof v === 'string') {
    const n = parseFloat(v.replace(/[^\d.\-]/g, ''))
    return Number.isFinite(n) ? n : undefined
  }
  return undefined
}

const aBooleano = (v: unknown) =>
  v === true || ['true', '1', 'si', 'yes'].includes(sinAcentos(String(v)))

const redondear2 = (n: number) => Math.round(n * 100) / 100

function normalizarTemperaturaIdeal(valor: unknown): TempIdeal {
  if (valor === undefined || valor === null) return 'indiferente'
  const s = sinAcentos(String(valor)).toLowerCase().trim()
  
  if (/^(fri|fres|helad)/.test(s)) return 'frio'
  if (/^(calor|calient|calid)/.test(s)) return 'caliente'
  
  return 'indiferente'
}

function normalizarItem(raw: ApiItem): MenuItem {
  const get = crearLector(raw)

  const nombreCrudo = String(get('Nombre_Producto', 'nombre', 'name') ?? '').trim()
  const categoria = String(get('Categoria', 'categoria') ?? '').trim()
  const precioOriginal = aNumero(get('Precio_Venta', 'precio_original', 'precio')) ?? 0
  const id = String(get('ID_Producto', 'ID_Bebida', 'id') ?? nombreCrudo)

  let precio = aNumero(get('precio_final'))
  const descuentoBackend = aNumero(get('descuento_aplicado', 'descuento'))
  if (precio === undefined && descuentoBackend && descuentoBackend > 0) {
    const pct = descuentoBackend < 1 ? descuentoBackend * 100 : descuentoBackend
    precio = redondear2(precioOriginal * (1 - pct / 100))
  }
  precio ??= precioOriginal
  const descuentoPct =
    precioOriginal > 0 && precio < precioOriginal ? Math.round((1 - precio / precioOriginal) * 100) : 0

  const insigniaCruda = get('insignia_sugerida', 'insignia')
  const insignia = typeof insigniaCruda === 'string' ? insigniaCruda.trim() : null
  const chefPorInsignia = insignia ? sinAcentos(insignia).includes('chef') : false
  const imagen = get('Imagen_URL', 'imagen_url', 'imagen')

  const rawInsignias = raw.insignias
  const insignias = Array.isArray(rawInsignias) ? (rawInsignias as string[]) : []

  // Extraemos directamente lo que escribió el usuario en el Sheet
  const tempIdealVal = get('Temperatura_Ideal', 'temperatura_ideal', 'temp_ideal', 'temperatura')
  const tempIdeal = String(tempIdealVal ?? '').trim().toLowerCase()

  return {
    id,
    nombre: nombreCrudo || id,
    categoria,
    grupo: grupoDe(categoria),
    precio,
    precioOriginal,
    temperatura: normalizarTemperaturaIdeal(tempIdealVal),
    agotado: sinAcentos(String(get('Estado_Stock', 'estado_stock') ?? '')) === 'agotado',
    recomendado: aBooleano(get('recomendado')) || chefPorInsignia,
    descuentoPct,
    insignia: chefPorInsignia ? null : insignia,
    insignia_sugerida: insignia,
    insignias,
    temp_ideal: tempIdeal,
    temperatura_ideal: tempIdeal,
    imagenUrl: typeof imagen === 'string' ? imagen : undefined,
  }
}

// --- Ayudas para desarrollo y pruebas de clima -----------------------------------------------
function conInsigniasDemo(items: MenuItem[]): MenuItem[] {
  return items.map((it, i) => {
    if (i === 0) return { ...it, recomendado: true }
    if (i === 1 && !it.agotado) {
      return { ...it, descuentoPct: 15, precio: redondear2((it.precioOriginal ?? it.precio) * 0.85) }
    }
    if (i === 2) return { ...it, insignia: '☀️ Recomendación para el Calor' }
    return it
  })
}

const TEMP_DEMO: Record<string, number> = { calor: 31, frio: 12, templado: 21 }
function conClimaDemo(base: Clima | null): Clima | null {
  const modo = import.meta.env.VITE_DEMO_CLIMA as ModoClima | undefined
  if (!modo || !(modo in TEMP_DEMO)) return base
  return {
    ciudad: base?.ciudad ?? 'Querétaro',
    temperatura: TEMP_DEMO[modo],
    modo,
    descripcion: modo === 'frio' ? 'Día fresco' : modo === 'calor' ? 'Día caluroso' : 'Clima templado',
  }
}

export async function fetchMenu(signal?: AbortSignal): Promise<Menu> {
  let res: Response
  try {
    res = await fetch(`${BASE_URL}${MENU_PATH}`, { signal })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ErrorMenu('red', 'No hay conexión con el servidor del menú.')
  }
  if (!res.ok) throw new ErrorMenu('servidor', `El servidor respondió con error ${res.status}.`)

  let data: ApiMenuResponse | ApiItem[]
  try {
    data = (await res.json()) as ApiMenuResponse | ApiItem[]
  } catch {
    throw new ErrorMenu('servidor', 'La respuesta del servidor no es válida.')
  }

  const lista = Array.isArray(data) ? data : (data.menu ?? [])
  const climaBackend = Array.isArray(data) ? null : data.clima
  let items = lista.map(normalizarItem)

  if (import.meta.env.DEV && import.meta.env.VITE_DEMO_BADGES === 'true') items = conInsigniasDemo(items)

  // 1. Usar clima del backend si existe
  let climaFinal = normalizarClima(climaBackend)

  // 2. Si el backend no envía clima, obtenerlo en vivo de la API de Querétaro
  if (!climaFinal && !import.meta.env.VITE_DEMO_CLIMA) {
    climaFinal = await obtenerClimaEnTiempoReal('Queretaro')
  }

  // 3. Forzar simulación solo si VITE_DEMO_CLIMA está activo en .env
  climaFinal = conClimaDemo(climaFinal)

  return { clima: climaFinal, items }
}
import type { MenuItem, ModoClima, TempIdeal } from './types'

/** Qué `Temperatura_Ideal` se recomienda en cada clima. */
export const TEMP_IDEAL_POR_MODO: Record<ModoClima, TempIdeal | null> = {
  calor: 'caliente', // Mapea a las bebidas/alimentos ideales para calor
  frio: 'frio',      // Mapea a las bebidas/alimentos ideales para frío
  templado: null,   // En clima templado no hay filtro
}

export interface TemaClima {
  icono: string
  titulo: string
  mensaje: string
  chip: string | null // null = sin botón de filtro
  fondo: string
}

export const TEMAS: Record<ModoClima, TemaClima> = {
  calor: {
    icono: '☀️',
    titulo: 'Hoy pega el sol',
    mensaje: 'Con este calor, lo mejor es bien frío.',
    chip: '☀️ Ver lo más fresco para hoy',
    fondo: 'linear-gradient(120deg, #7a2e00 0%, #b3260f 100%)',
  },
  frio: {
    icono: '🌧️',
    titulo: 'Hoy está fresco',
    mensaje: 'Se antoja algo calientito.',
    chip: '🌧️ Ver especiales de clima',
    fondo: 'linear-gradient(120deg, #12202e 0%, #26425c 100%)',
  },
  templado: {
    icono: '🌤️',
    titulo: 'Clima perfecto',
    mensaje: 'Hoy cualquier antojo es buena idea.',
    chip: null,
    fondo: 'linear-gradient(120deg, #2d2926 0%, #3d3630 100%)',
  },
}

/** Ideal para el clima y disponible (soporta temp_ideal, temperatura e insignias de la API) */
export function esIdealParaClima(item: MenuItem, modo: ModoClima): boolean {
  if (modo === 'templado' || item.agotado) return false

  // 1. Recopilamos todos los campos válidos declarados en MenuItem
  const campos = [
    item.temperatura,
    item.temp_ideal,
    item.temperatura_ideal,
  ]

  // Extraemos los valores limpios en minúsculas filtrando de forma segura para TypeScript
  const valores = campos
    .filter((val): val is string => typeof val === 'string' && val.trim() !== '')
    .map((val) => val.toLowerCase().trim())

  // Si no tiene ningún dato asignado en el Sheet, no es ideal para ningún clima
  if (valores.length === 0) return false

  // 2. Definimos los valores exactos permitidos para cada tipo de clima
  const VALORES_CALOR = new Set(['calor', 'caliente', 'fresca', 'fresco', 'cálido', 'calido'])
  const VALORES_FRIO = new Set(['frio', 'frío', 'calientito', 'helado'])

  // 3. Evaluamos según el modo de clima actual
  if (modo === 'calor') {
    return valores.some((v) => VALORES_CALOR.has(v))
  }

  if (modo === 'frio') {
    return valores.some((v) => VALORES_FRIO.has(v))
  }

  return false
}
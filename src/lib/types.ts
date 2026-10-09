/** Forma cruda que devuelve GET /api/v1/menu. Los nombres de campo se leen de forma tolerante en api.ts. */
export interface ApiClima {
  ciudad: string
  temperatura: number
  condicion: string
  descripcion: string
}

export type ApiItem = Record<string, unknown>

export interface ApiMenuResponse {
  clima?: ApiClima | null
  menu: ApiItem[]
}

/** Modelo limpio que consume la interfaz (sin costos ni márgenes). */
export type GrupoId = 'alitas' | 'hamburguesas' | 'entradas' | 'bebidas' | 'postres'
export type TempIdeal = 'frio' | 'caliente' | 'indiferente'
export type ModoClima = 'calor' | 'frio' | 'templado'

export interface MenuItem {
  id: string
  nombre: string
  categoria: string
  grupo: GrupoId
  precio: number
  precioOriginal: number
  temperatura: TempIdeal
  descuentoPct: number // 0 = sin oferta; 15 = 15% de descuento
  agotado: boolean
  recomendado: boolean // Recomendado del Chef
  insignia: string | null // etiqueta extra del backend (p. ej. de clima); null si no viene

  // Propiedades opcionales que recibe/mapea api.ts desde el backend:
  precio_original?: number
  precio_final?: number
  descuento_aplicado?: number
  temp_ideal?: string
  temperatura_ideal?: string // <-- Agregada para soporte explícito del backend/clima
  insignia_sugerida?: string | null
  insignias?: string[]
  disponible?: boolean
  imagenUrl?: string // opcional: si no viene o falla al cargar, se usa degradado + emoji
}

export interface Clima {
  ciudad: string
  temperatura: number
  modo: ModoClima
  descripcion: string
}

export interface Menu {
  clima: Clima | null
  items: MenuItem[]
}
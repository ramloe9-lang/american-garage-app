import type { GrupoId } from './types'

/** Pestañas del menú, en el orden en que se muestran. Solo se muestran las que tengan productos. */
export const GRUPOS: { id: GrupoId; label: string; emoji: string }[] = [
  { id: 'alitas', label: 'Alitas', emoji: '🍗' },
  { id: 'hamburguesas', label: 'Hamburguesas', emoji: '🍔' },
  { id: 'entradas', label: 'Entradas', emoji: '🧀' },
  { id: 'bebidas', label: 'Bebidas', emoji: '🍺' },
  { id: 'postres', label: 'Postres', emoji: '🍰' },
]

export const sinAcentos = (s: string) =>
  s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().toLowerCase()

/** Categoria (columna de Sheets) -> pestaña del menú. Agrega aquí cualquier categoría nueva. */
const GRUPO_POR_CATEGORIA: Record<string, GrupoId> = {
  cerveza: 'bebidas',
  refresco: 'bebidas',
  malteada: 'bebidas',
  cafe: 'bebidas',
  te: 'bebidas',
  burgers: 'hamburguesas',
  burger: 'hamburguesas',
  hamburguesas: 'hamburguesas',
  wings: 'alitas',
  alitas: 'alitas',
  entradas: 'entradas',
  postres: 'postres',
}

const EMOJI_POR_CATEGORIA: Record<string, string> = {
  cerveza: '🍺',
  refresco: '🥤',
  malteada: '🥛',
  cafe: '☕',
  te: '🍵',
  burgers: '🍔',
  burger: '🍔',
  hamburguesas: '🍔',
  wings: '🍗',
  alitas: '🍗',
  entradas: '🧀',
  postres: '🍰',
}

export function grupoDe(categoria: string): GrupoId {
  const grupo = GRUPO_POR_CATEGORIA[sinAcentos(categoria)]
  if (!grupo && import.meta.env.DEV) {
    console.warn(`[menu] Categoría sin mapear: "${categoria}". Agrégala en lib/categories.ts`)
  }
  return grupo ?? 'entradas'
}

export function emojiDe(categoria: string): string {
  return EMOJI_POR_CATEGORIA[sinAcentos(categoria)] ?? '🔥'
}

/** Par de colores del degradado que se muestra cuando el producto no tiene foto. */
const TONO_POR_CATEGORIA: Record<string, [string, string]> = {
  cerveza: ['#f5b800', '#8a4b00'],
  refresco: ['#ff3b2f', '#6b0f0a'],
  malteada: ['#ff9bb8', '#7a2a4d'],
  cafe: ['#b07a4a', '#2b160a'],
  te: ['#8fbf6a', '#1f3d1a'],
  burgers: ['#ff7a1a', '#7a2a00'],
  burger: ['#ff7a1a', '#7a2a00'],
  hamburguesas: ['#ff7a1a', '#7a2a00'],
  wings: ['#ff3b2f', '#5c0d08'],
  alitas: ['#ff3b2f', '#5c0d08'],
  entradas: ['#f5b800', '#6b4a00'],
  postres: ['#c98bff', '#3d1a5c'],
}

export function tonoDe(categoria: string): [string, string] {
  return TONO_POR_CATEGORIA[sinAcentos(categoria)] ?? ['#ff3b2f', '#5c0d08']
}

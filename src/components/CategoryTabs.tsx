import { useEffect, useRef } from 'react'
import type { KeyboardEvent } from 'react'
import { motion } from 'motion/react'
import { GRUPOS } from '../lib/categories'
import type { GrupoId } from '../lib/types'

interface Props {
  activo: GrupoId
  conteos: Partial<Record<GrupoId, number>>
  onChange: (grupo: GrupoId) => void
}

/** Pestañas pegadas arriba. La píldora roja se desliza entre pestañas (layoutId compartido). */
export default function CategoryTabs({ activo, conteos, onChange }: Props) {
  const grupos = GRUPOS.filter((g) => (conteos[g.id] ?? 0) > 0)
  const botones = useRef<Partial<Record<GrupoId, HTMLButtonElement | null>>>({})

  // Mantiene la pestaña activa centrada cuando la barra hace scroll horizontal.
  useEffect(() => {
    botones.current[activo]?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' })
  }, [activo])

  function alTeclear(e: KeyboardEvent, indice: number) {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    e.preventDefault()
    const paso = e.key === 'ArrowRight' ? 1 : -1
    const siguiente = grupos[(indice + paso + grupos.length) % grupos.length]
    onChange(siguiente.id)
    botones.current[siguiente.id]?.focus()
  }

  return (
    <nav
      className="sticky z-20 border-b border-acero bg-carbon/90 backdrop-blur"
      style={{ top: 'env(safe-area-inset-top)' }}
    >
      <div
        role="tablist"
        aria-label="Categorías del menú"
        className="scrollbar-oculta flex gap-2 overflow-x-auto px-4 py-3"
      >
        {grupos.map((g, i) => {
          const seleccionado = g.id === activo
          return (
            <button
              key={g.id}
              ref={(el) => { botones.current[g.id] = el }}
              role="tab"
              aria-selected={seleccionado}
              tabIndex={seleccionado ? 0 : -1}
              onClick={() => onChange(g.id)}
              onKeyDown={(e) => alTeclear(e, i)}
              className={`relative shrink-0 rounded-full px-4 py-2.5 outline-offset-2 focus-visible:outline-2 focus-visible:outline-oro ${
                seleccionado ? 'text-hueso' : 'text-ceniza ring-1 ring-inset ring-acero'
              }`}
            >
              {seleccionado && (
                <motion.span
                  layoutId="tab-activo"
                  className="absolute inset-0 rounded-full bg-fuego"
                  transition={{ type: 'spring', stiffness: 500, damping: 38 }}
                />
              )}
              <span className="relative flex items-center gap-2 font-display text-xl font-bold leading-none">
                <span aria-hidden="true">{g.emoji}</span>
                {g.label}
                <span
                  className={`rounded-full px-2 py-0.5 font-body text-sm font-semibold ${
                    seleccionado ? 'bg-carbon/30' : 'bg-acero'
                  }`}
                >
                  {conteos[g.id]}
                </span>
              </span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}

import { useState } from 'react'
import { emojiDe, tonoDe } from '../lib/categories'
import type { MenuItem } from '../lib/types'

/**
 * Imagen del producto. Si hay `imagenUrl` y carga bien, se muestra la foto;
 * si no viene o falla, cae a un degradado por categoría con su emoji.
 */
export default function ProductVisual({ item }: { item: MenuItem }) {
  const [fallo, setFallo] = useState(false)
  const [claro, oscuro] = tonoDe(item.categoria)
  const mostrarFoto = Boolean(item.imagenUrl) && !fallo

  return (
    <div
      className={`grid h-[76px] w-[76px] shrink-0 place-items-center overflow-hidden rounded-lg ring-1 ring-white/10 ${
        item.agotado ? 'opacity-50 grayscale' : ''
      }`}
      style={{ background: `linear-gradient(135deg, ${claro}, ${oscuro})` }}
    >
      {mostrarFoto ? (
        <img
          src={item.imagenUrl}
          alt=""
          loading="lazy"
          onError={() => setFallo(true)}
          className="h-full w-full object-cover"
        />
      ) : (
        <span className="text-4xl drop-shadow-md" aria-hidden="true">
          {emojiDe(item.categoria)}
        </span>
      )}
    </div>
  )
}

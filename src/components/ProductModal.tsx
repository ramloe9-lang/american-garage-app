import { motion, AnimatePresence } from 'motion/react'
import type { MenuItem } from '../lib/types'
import { formatearPrecio } from '../lib/format'
import ProductVisual from './ProductVisual'

interface Props {
  item: MenuItem | null
  onClose: () => void
}

export default function ProductModal({ item, onClose }: Props) {
  if (!item) return null

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          className="relative w-full max-w-sm overflow-hidden rounded-2xl bg-asfalto p-5 ring-1 ring-acero shadow-2xl"
        >
          {/* Botón de cerrar (X) */}
          <button
            onClick={onClose}
            className="absolute right-3 top-3 z-20 rounded-full bg-acero/80 p-2 text-hueso hover:bg-fuego transition-colors"
          >
            ✕
          </button>

          <div className="flex flex-col items-center text-center">
            {/* Visual del producto integrado sin espacios vacíos */}
            <div className="mb-3 flex justify-center">
              <ProductVisual item={item} />
            </div>

            {/* Categoría */}
            <span className="mb-1.5 rounded-full bg-acero px-3 py-0.5 text-xs font-semibold text-ceniza">
              {item.categoria}
            </span>

            {/* Nombre del producto */}
            <h3 className="font-display text-2xl font-extrabold text-hueso leading-tight">
              {item.nombre}
            </h3>

            {/* Precio */}
            <span className="font-display text-2xl font-extrabold text-oro my-1.5">
              {formatearPrecio(item.precio)}
            </span>

            {/* Descripción mediana del platillo */}
            {item.descripcion ? (
              <p className="mt-2 text-sm leading-relaxed text-hueso/90 font-body px-1">
                {item.descripcion}
              </p>
            ) : (
              <p className="mt-2 text-xs text-ceniza italic">
                Preparado al momento con ingredientes frescos de la más alta calidad.
              </p>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  )
}

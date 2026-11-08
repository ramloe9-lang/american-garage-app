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
          className="relative w-full max-w-md overflow-hidden rounded-2xl bg-asfalto p-6 ring-1 ring-acero shadow-2xl"
        >
          {/* Botón de cerrar (X) */}
          <button
            onClick={onClose}
            className="absolute right-4 top-4 z-10 rounded-full bg-acero/60 px-3 py-1 font-bold text-hueso hover:bg-fuego transition-colors"
          >
            ✕
          </button>

          <div className="flex flex-col items-center text-center">
            {/* Imagen o visual del platillo */}
            <div className="w-full h-48 mb-4 overflow-hidden rounded-xl">
              <ProductVisual item={item} />
            </div>

            {/* Categoría */}
            <span className="mb-1 rounded-full bg-acero px-3 py-0.5 text-xs font-semibold text-ceniza">
              {item.categoria}
            </span>

            {/* Nombre del producto */}
            <h3 className="font-display text-3xl font-extrabold text-hueso mt-1 leading-tight">
              {item.nombre}
            </h3>

            {/* Precio */}
            <span className="font-display text-3xl font-extrabold text-oro my-2">
              {formatearPrecio(item.precio)}
            </span>

            {/* Descripción mediana */}
            {item.descripcion ? (
              <p className="mt-2 text-sm leading-relaxed text-hueso/80 font-body px-2">
                {item.descripcion}
              </p>
            ) : (
              <p className="mt-2 text-sm text-ceniza italic">
                Preparado al momento con los mejores ingredientes de la casa.
              </p>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  )
}
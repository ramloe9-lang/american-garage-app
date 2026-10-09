import { motion } from 'motion/react'
import ProductCard from './ProductCard'
import type { MenuItem, ModoClima } from '../lib/types'

/**
 * Lista de una categoría. En App se monta con key={categoría}: al cambiar de pestaña,
 * la lista anterior sale y la nueva dispara la entrada de sus tarjetas.
 */
export default function ProductList({
  items,
  resaltar = false,
  modoClima,
}: {
  items: MenuItem[]
  resaltar?: boolean
  modoClima?: ModoClima
}) {
  return (
    <motion.ul
      role="tabpanel"
      className="space-y-3"
      initial="oculto"
      animate="visible"
      exit="salida"
      variants={{
        oculto: {},
        visible: { transition: { staggerChildren: 0.05 } },
        salida: { opacity: 0, y: -8, transition: { duration: 0.15 } },
      }}
    >
      {items.map((it, i) => (
        <ProductCard
          key={it.id}
          item={it}
          indice={i}
          resaltar={resaltar}
          modoClima={modoClima}
        />
      ))}
    </motion.ul>
  )
}
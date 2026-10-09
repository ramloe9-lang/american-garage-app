import type { ReactNode } from 'react'
import { motion } from 'motion/react'

export type TonoInsignia = 'chef' | 'oferta' | 'agotado' | 'info'

const ESTILOS: Record<TonoInsignia, string> = {
  chef: 'bg-oro text-carbon',
  oferta: 'bg-fuego text-hueso',
  agotado: 'bg-acero text-ceniza',
  info: 'bg-asfalto text-hueso ring-1 ring-inset ring-ceniza/40',
}

interface Props {
  tono: TonoInsignia
  retraso?: number // segundos; se escalona para que aparezcan después de su tarjeta
  children: ReactNode
}

/** Insignia que "salta" al aparecer con un resorte corto. */
export default function Badge({ tono, retraso = 0, children }: Props) {
  return (
    <motion.span
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 520, damping: 17, delay: retraso }}
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 font-display text-base font-bold leading-none ${ESTILOS[tono]}`}
    >
      {children}
    </motion.span>
  )
}

import { motion } from 'motion/react'

interface Props {
  emoji: string
  titulo: string
  descripcion: string
  tono?: 'normal' | 'error'
  accion?: { texto: string; onClick: () => void; ocupado?: boolean }
}

/** Mensaje centrado para errores y pantallas vacías: dice qué pasó y qué hacer. */
export default function EstadoMensaje({ emoji, titulo, descripcion, tono = 'normal', accion }: Props) {
  const esError = tono === 'error'
  return (
    <motion.div
      role={esError ? 'alert' : 'status'}
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 26 }}
      className={`rounded-xl p-6 text-center ring-1 ${
        esError ? 'bg-fuego/5 ring-fuego/50' : 'bg-asfalto ring-acero'
      }`}
    >
      <p className="text-5xl" aria-hidden="true">{emoji}</p>
      <h2 className="mt-3 font-display text-3xl font-extrabold leading-none">{titulo}</h2>
      <p className="mx-auto mt-2 max-w-[30ch] text-sm text-ceniza">{descripcion}</p>
      {accion && (
        <button
          type="button"
          onClick={accion.onClick}
          disabled={accion.ocupado}
          className="mt-5 rounded-full bg-fuego px-5 py-2.5 font-display text-xl font-bold leading-none text-hueso outline-offset-2 focus-visible:outline-2 focus-visible:outline-oro disabled:opacity-60"
        >
          {accion.ocupado ? 'Reintentando…' : accion.texto}
        </button>
      )}
    </motion.div>
  )
}

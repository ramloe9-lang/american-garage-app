import { motion } from 'motion/react'
import { TEMAS } from '../lib/clima'
import type { Clima, ModoClima } from '../lib/types'

interface Props {
  clima: Clima
  filtroActivo: boolean
  onToggle: () => void
}

const POSICION_GOTAS = [8, 18, 29, 41, 52, 63, 75, 86, 94] // % horizontal

function IconoClima({ modo, icono }: { modo: ModoClima; icono: string }) {
  if (modo === 'calor') {
    return (
      <div className="relative grid h-14 w-14 shrink-0 place-items-center">
        <motion.div
          aria-hidden="true"
          className="absolute inset-0 rounded-full bg-oro/40 blur-md"
          animate={{ scale: [1, 1.25, 1], opacity: [0.5, 0.9, 0.5] }}
          transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.span
          aria-hidden="true"
          className="relative text-4xl"
          animate={{ rotate: 360 }}
          transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
        >
          {icono}
        </motion.span>
      </div>
    )
  }
  return (
    <div className="grid h-14 w-14 shrink-0 place-items-center">
      <motion.span
        aria-hidden="true"
        className="text-4xl"
        animate={{ y: [-2, 3, -2] }}
        transition={{ duration: 2.6, repeat: Infinity, ease: 'easeInOut' }}
      >
        {icono}
      </motion.span>
    </div>
  )
}

/** Banner que refleja el clima y, si hay recomendación, ofrece el filtro de un solo toque. */
export default function WeatherBanner({ clima, filtroActivo, onToggle }: Props) {
  const tema = TEMAS[clima.modo]
  const descripcion = clima.descripcion
    ? clima.descripcion.charAt(0).toUpperCase() + clima.descripcion.slice(1)
    : ''

  return (
    <motion.section
      aria-label="Clima de hoy"
      initial={{ opacity: 0, y: -14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 260, damping: 26 }}
      className="relative mx-4 mt-4 overflow-hidden rounded-xl p-4 ring-1 ring-white/10"
      style={{ background: tema.fondo }}
    >
      {clima.modo === 'frio' && (
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
          {POSICION_GOTAS.map((left, i) => (
            <span
              key={left}
              className="gota"
              style={{
                left: `${left}%`,
                animationDelay: `${((i * 0.37) % 1.3).toFixed(2)}s`,
                animationDuration: `${1.1 + (i % 3) * 0.25}s`,
              }}
            />
          ))}
        </div>
      )}

      <div className="relative">
        <div className="flex items-center gap-3">
          <IconoClima modo={clima.modo} icono={tema.icono} />
          <div className="min-w-0 flex-1">
            <p className="font-display text-3xl font-extrabold leading-none">{tema.titulo}</p>
            <p className="mt-1 text-sm text-hueso/85">{tema.mensaje}</p>
          </div>
          <p
            className="font-display text-5xl font-black leading-none"
            aria-label={`${Math.round(clima.temperatura)} grados`}
          >
            {Math.round(clima.temperatura)}°
          </p>
        </div>

        {descripcion && (
          <p className="mt-2 text-xs text-hueso/70">
            {descripcion} en {clima.ciudad}
          </p>
        )}

        {tema.chip && (
          <motion.button
            type="button"
            aria-pressed={filtroActivo}
            onClick={onToggle}
            whileTap={{ scale: 0.96 }}
            className={`mt-4 inline-flex items-center rounded-full px-4 py-2.5 font-display text-xl font-bold leading-none outline-offset-2 focus-visible:outline-2 focus-visible:outline-oro ${
              filtroActivo
                ? 'bg-hueso text-carbon'
                : 'bg-carbon/70 text-hueso ring-1 ring-inset ring-hueso/40'
            }`}
          >
            <motion.span
              key={filtroActivo ? 'activo' : 'inactivo'}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.18 }}
            >
              {filtroActivo ? '✓ Mostrando lo ideal · Ver todo' : tema.chip}
            </motion.span>
          </motion.button>
        )}
      </div>
    </motion.section>
  )
}
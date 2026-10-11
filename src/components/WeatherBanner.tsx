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

  // Usamos directamente la temperatura que manda el backend (ya viene con la única resta aplicada)
  const tempRedondeada = Math.round(clima.temperatura)

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
            aria-label={`${tempRedondeada} grados`}
          >
            {tempRedondeada}°
          </p>
        </div>

        {/* Botón interactivo de especiales del clima */}
        {clima.modo !== 'templado' && (
          <div className="mt-3.5 flex flex-col gap-1.5 border-t border-white/10 pt-3">
            {descripcion && <p className="text-xs text-hueso/70">{descripcion}</p>}
            <button
              onClick={onToggle}
              type="button"
              className={`inline-flex items-center gap-2 self-start rounded-full px-4 py-2 font-display text-sm font-bold tracking-wide transition-all ${
                filtroActivo
                  ? 'bg-oro text-negro ring-2 ring-white shadow-lg scale-105'
                  : 'bg-white/15 text-hueso hover:bg-white/25 ring-1 ring-white/20'
              }`}
            >
              <span>{tema.icono}</span>
              <span>{filtroActivo ? 'Ver todo el menú' : 'Ver especiales de clima'}</span>
            </button>
          </div>
        )}
      </div>
    </motion.section>
  )
}

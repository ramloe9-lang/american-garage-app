import { motion } from 'motion/react'
import type { Variants } from 'motion/react'
import Badge from './Badge'
import ProductVisual from './ProductVisual'
import { formatearPrecio } from '../lib/format'
import type { MenuItem, ModoClima } from '../lib/types'
import { esIdealParaClima } from '../lib/clima'

// Entrada escalonada: el retraso se limita a 8 posiciones
const entrada: Variants = {
  oculto: { opacity: 0, x: -24 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: { type: 'spring', stiffness: 380, damping: 30, delay: Math.min(i, 8) * 0.05 },
  }),
}

export default function ProductCard({
  item,
  indice,
  resaltar = false,
  modoClima,
}: {
  item: MenuItem
  indice: number
  resaltar?: boolean
  modoClima?: ModoClima
}) {
  const retraso = 0.25 + Math.min(indice, 8) * 0.05
  const enOferta = !item.agotado && (item.descuentoPct ?? 0) > 0

  // 1. Verifica si este producto específico es ideal según la función esIdealParaClima
  const matchClimaDirecto = modoClima ? esIdealParaClima(item, modoClima) : false

  // 2. Verificación secundaria por si el Sheet trae la palabra en insignia_sugerida o insignias[]
  const textoInsignias = [
    item.insignia,
    item.insignia_sugerida,
    ...(item.insignias ?? []),
  ].filter(Boolean).join(' ').toLowerCase()

  const matchInsigniaCalor = modoClima === 'calor' && /calor|fresco|fresca|sol/.test(textoInsignias)
  const matchInsigniaFrio = modoClima === 'frio' && /frio|frío|calientito|fresco/.test(textoInsignias)

  const esIdealHoy = matchClimaDirecto || matchInsigniaCalor || matchInsigniaFrio

  return (
    <motion.li
      variants={entrada}
      custom={indice}
      className={`flex gap-3 rounded-xl bg-asfalto p-3 ring-1 ${resaltar ? 'ring-oro/60' : 'ring-acero'}`}
    >
      <ProductVisual item={item} />

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <h3
            className={`font-display text-2xl font-extrabold leading-[1.05] ${
              item.agotado ? 'text-ceniza' : 'text-hueso'
            }`}
          >
            {item.nombre}
          </h3>
          <div className="shrink-0 text-right leading-none">
            {enOferta && (
              <s className="mb-0.5 block text-sm text-ceniza">{formatearPrecio(item.precioOriginal ?? item.precio)}</s>
            )}
            <span
              className={`font-display text-2xl font-extrabold ${item.agotado ? 'text-ceniza' : 'text-oro'}`}
            >
              {formatearPrecio(item.precio)}
            </span>
          </div>
        </div>

        <p className="mt-1 text-sm text-ceniza">{item.categoria}</p>

        {/* Las insignias solo existen si el backend manda el dato o si hay match con el clima */}
        <div className="mt-2 flex flex-wrap gap-1.5 empty:hidden">
          {item.agotado && (
            <Badge tono="agotado" retraso={retraso}>
              Agotado
            </Badge>
          )}

          {!item.agotado && item.recomendado && (
            <Badge tono="chef" retraso={retraso}>
              <span aria-hidden="true">👨‍🍳</span> Recomendado del Chef
            </Badge>
          )}

          {enOferta && (
            <Badge tono="oferta" retraso={retraso + 0.06}>
              Oferta -{item.descuentoPct}%
            </Badge>
          )}

          {/* Insignia de Clima según el modo actual */}
          {!item.agotado && esIdealHoy && modoClima === 'calor' && (
            <Badge tono="info" retraso={retraso + 0.1}>
              ☀️ Ideal para Calor
            </Badge>
          )}

          {!item.agotado && esIdealHoy && modoClima === 'frio' && (
            <Badge tono="info" retraso={retraso + 0.1}>
              🌧️ Ideal para Frío
            </Badge>
          )}

          {!item.agotado && item.insignia && !esIdealHoy && (
            <Badge tono="info" retraso={retraso + 0.12}>
              {item.insignia}
            </Badge>
          )}
        </div>
      </div>
    </motion.li>
  )
}
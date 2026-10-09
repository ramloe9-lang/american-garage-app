import { useMemo, useState } from 'react'
import { AnimatePresence } from 'motion/react'
import CategoryTabs from './components/CategoryTabs'
import EstadoMensaje from './components/EstadoMensaje'
import Header from './components/Header'
import MenuSkeleton from './components/MenuSkeleton'
import ProductList from './components/ProductList'
import WeatherBanner from './components/WeatherBanner'
import { ErrorMenu } from './lib/api'
import { GRUPOS } from './lib/categories'
import { TEMAS, esIdealParaClima } from './lib/clima'
import type { GrupoId } from './lib/types'
import { useMenu } from './hooks/useMenu'

/** PASO 5: esqueleto de carga y estados de error/vacío. */
export default function App() {
  const { data, isPending, error, refetch, isFetching } = useMenu()
  const [elegido, setElegido] = useState<GrupoId | null>(null)
  const [soloClima, setSoloClima] = useState(false)

  const clima = data?.clima ?? null
  // El filtro solo aplica si el clima actual tiene una recomendación (calor o fresco).
  const filtroActivo = soloClima && clima !== null && TEMAS[clima.modo].chip !== null

  // Productos visibles: todo el menú o solo lo ideal para el clima de hoy, 
  // ORDENADOS dinámicamente para que las opciones acorde al clima aparezcan primero.
  const visibles = useMemo(() => {
    if (!data) return []

    // 1. Filtrar productos según la toggle de "solo clima"
    const filtrados = filtroActivo && clima
      ? data.items.filter((i) => esIdealParaClima(i, clima.modo))
      : data.items

    // 2. Ordenar automáticamente: los ideales para el clima van al principio
    const modoActual = clima?.modo
    if (!modoActual || modoActual === 'templado') return filtrados

    return [...filtrados].sort((a, b) => {
      const aEsIdeal = !a.agotado && esIdealParaClima(a, modoActual)
      const bEsIdeal = !b.agotado && esIdealParaClima(b, modoActual)

      if (aEsIdeal && !bEsIdeal) return -1
      if (!aEsIdeal && bEsIdeal) return 1
      return 0
    })
  }, [data, clima, filtroActivo])

  const conteos = useMemo(() => {
    const c: Partial<Record<GrupoId, number>> = {}
    visibles.forEach((i) => {
      if (i.grupo) {
        c[i.grupo] = (c[i.grupo] ?? 0) + 1
      }
    })
    return c
  }, [visibles])

  // Si la pestaña elegida deja de existir (refresco o filtro), cae a la primera disponible.
  const activo = elegido && conteos[elegido] ? elegido : GRUPOS.find((g) => conteos[g.id])?.id
  const items = visibles.filter((i) => i.grupo === activo)

  const reintentar = { texto: 'Reintentar', onClick: () => refetch(), ocupado: isFetching }

  return (
    <div className="mx-auto min-h-dvh max-w-md">
      <Header />

      {isPending && <MenuSkeleton />}

      {/* Sin datos y con error: pantalla de error completa. */}
      {error && !data && (
        <main className="px-4 py-8">
          {error instanceof ErrorMenu && error.tipo === 'red' ? (
            <EstadoMensaje
              tono="error"
              emoji="📡"
              titulo="Sin conexión"
              descripcion="No pudimos cargar el menú. Revisa tu internet e intenta de nuevo."
              accion={reintentar}
            />
          ) : (
            <EstadoMensaje
              tono="error"
              emoji="🔧"
              titulo="Estamos calentando motores"
              descripcion="El menú no está disponible ahora. Intenta en unos minutos o pide la carta a tu mesero."
              accion={reintentar}
            />
          )}
        </main>
      )}

      {data && (
        <>
          {clima && (
            <WeatherBanner
              clima={clima}
              filtroActivo={filtroActivo}
              onToggle={() => setSoloClima((v) => !v)}
            />
          )}

          {activo && <CategoryTabs activo={activo} conteos={conteos} onChange={setElegido} />}

          <main className="px-4 py-5">
            {/* Tenemos un menú guardado pero el último refresco falló. */}
            {error && (
              <p role="status" className="mb-4 rounded-lg bg-asfalto px-3 py-2 text-sm text-ceniza">
                No pudimos actualizar el menú. Mostramos la última versión disponible.
              </p>
            )}

            {!activo && filtroActivo && (
              <EstadoMensaje
                emoji="🌡️"
                titulo="Nada ideal por ahora"
                descripcion="No hay opciones disponibles que vayan con el clima de hoy."
                accion={{ texto: 'Ver todo el menú', onClick: () => setSoloClima(false) }}
              />
            )}

            {!activo && !filtroActivo && (
              <EstadoMensaje
                emoji="🍽️"
                titulo="Estamos preparando la carta"
                descripcion="Aún no hay productos disponibles. Pregúntale a tu mesero por las opciones de hoy."
              />
            )}

            {filtroActivo && activo && (
              <p role="status" className="mb-3 text-sm text-ceniza">
                {visibles.length} {visibles.length === 1 ? 'opción ideal' : 'opciones ideales'} para el clima de hoy.
              </p>
            )}

            <AnimatePresence mode="wait">
              {activo && (
                <ProductList key={`${activo}-${filtroActivo}`} items={items} resaltar={filtroActivo} modoClima={clima?.modo}/>
              )}
            </AnimatePresence>
          </main>
        </>
      )}
    </div>
  )
}
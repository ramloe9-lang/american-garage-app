/** Esqueleto con la misma forma que la pantalla final: banner, pestañas y tarjetas. */
export default function MenuSkeleton() {
  return (
    <div role="status">
      <span className="sr-only">Cargando el menú…</span>

      <div className="esqueleto mx-4 mt-4 h-[116px] rounded-xl" aria-hidden="true" />

      <div className="mt-4 flex gap-2 overflow-hidden border-b border-acero px-4 py-3" aria-hidden="true">
        {[104, 136, 92].map((ancho) => (
          <div key={ancho} className="esqueleto h-11 shrink-0 rounded-full" style={{ width: ancho }} />
        ))}
      </div>

      <div className="space-y-3 px-4 py-5" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="flex gap-3 rounded-xl bg-asfalto p-3 ring-1 ring-acero">
            <div className="esqueleto h-[76px] w-[76px] shrink-0 rounded-lg" />
            <div className="flex-1 space-y-2 pt-1">
              <div className="esqueleto h-6 w-3/4 rounded" />
              <div className="esqueleto h-4 w-1/3 rounded" />
              <div className="esqueleto h-6 w-1/4 rounded-full" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

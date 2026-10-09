/** Mesa desde la URL del QR (?mesa=5). Solo letras y números, máximo 3 caracteres. */
function leerMesa(): string | null {
  const valor = new URLSearchParams(window.location.search).get('mesa')
  return valor && /^[A-Za-z0-9]{1,3}$/.test(valor) ? valor.toUpperCase() : null
}

/** Logo tipográfico: letrero de garaje con cinta de precaución y placa dorada. */
export default function Header() {
  const mesa = leerMesa()

  return (
    <header className="border-b border-acero">
      <div className="cinta-peligro h-2.5" aria-hidden="true" />
      <div className="px-4 pb-6 pt-5">
        <h1 className="font-display font-black uppercase leading-[0.82] tracking-tight text-hueso text-[clamp(3rem,16vw,4.25rem)]">
          <span className="block">The American</span>
          <span className="block">Garage</span>
        </h1>

        <div className="mt-4 flex items-center justify-between gap-3">
          <p className="inline-flex -rotate-2 items-center gap-2 rounded-sm border-2 border-oro bg-carbon px-3 py-1 font-display text-xl font-extrabold uppercase tracking-wider text-oro">
            <span className="llama" aria-hidden="true">🔥</span>
            Wings &amp; Burgers
          </p>
          {mesa && (
            <p className="rounded-md px-3 py-1 font-display text-xl font-bold text-hueso ring-1 ring-inset ring-ceniza/50">
              Mesa {mesa}
            </p>
          )}
        </div>
      </div>
    </header>
  )
}

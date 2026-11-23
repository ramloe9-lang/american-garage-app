import React, { useCallback, useEffect, useMemo, useState } from "react";

export type TipoEstacion = "alimento" | "bebida";
export type FiltroEstacion = "todos" | "alimento" | "bebida";

export interface ItemComanda {
  id: string;
  producto_id: string;
  nombre: string;
  cantidad: number;
  categoria: string;
  notas: string | null;
  tipo: TipoEstacion;
  listo: boolean;
  completado_en: string | null;
}

export interface Comanda {
  id: string;
  mesa: string;
  numero_ronda: number;
  creada_en: string;
  items: ItemComanda[];
  completada_total: boolean;
  ultima_actualizacion: string;
}

const API_BASE =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL ||
  "https://american-garage-app.onrender.com";

const STORAGE_FILTRO_KEY = "visiak_cocina_filtro_estacion";

function obtenerEstadoTiempo(creadaEnIso: string, ahoraMs: number) {
  const inicioMs = new Date(creadaEnIso).getTime();
  const minutos = Math.max(0, Math.floor((ahoraMs - inicioMs) / 60000));

  if (minutos < 10) {
    return {
      minutos,
      label: `${minutos} min`,
      bgBarra: "bg-emerald-500",
      bordeTarjeta: "border-emerald-500/50",
      badgeTexto: "text-emerald-300 bg-emerald-950/70",
      porcentaje: Math.min(100, Math.max(8, (minutos / 10) * 100)),
    };
  }
  if (minutos < 25) {
    return {
      minutos,
      label: `${minutos} min`,
      bgBarra: "bg-amber-400",
      bordeTarjeta: "border-amber-400/60",
      badgeTexto: "text-amber-300 bg-amber-950/70",
      porcentaje: Math.min(100, Math.max(25, ((minutos - 10) / 15) * 100)),
    };
  }
  return {
    minutos,
    label: `${minutos} min`,
    bgBarra: "bg-rose-500",
    bordeTarjeta: "border-rose-500/70",
    badgeTexto: "text-rose-300 bg-rose-950/70",
    porcentaje: 100,
  };
}

export default function CocinaView() {
  const [filtro, setFiltro] = useState<FiltroEstacion>(() => {
    const guardado = localStorage.getItem(STORAGE_FILTRO_KEY);
    return guardado === "alimento" || guardado === "bebida" || guardado === "todos"
      ? guardado
      : "todos";
  });

  const [comandas, setComandas] = useState<Comanda[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mostrarAnteriores, setMostrarAnteriores] = useState(false);
  const [ahoraMs, setAhoraMs] = useState(() => Date.now());

  useEffect(() => {
    localStorage.setItem(STORAGE_FILTRO_KEY, filtro);
  }, [filtro]);

  // Reloj interno para actualizar colores y barras de tiempo cada segundo
  useEffect(() => {
    const timer = window.setInterval(() => setAhoraMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const cargarComandas = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/cocina/comandas?incluir_completadas=true`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: Comanda[] = await res.json();
      setComandas(data);
      setError(null);
    } catch {
      setError("No se pudieron sincronizar las comandas con el servidor.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargarComandas();
    const polling = window.setInterval(cargarComandas, 4000);
    return () => window.clearInterval(polling);
  }, [cargarComandas]);

  const itemCoincideEstacion = useCallback(
    (item: ItemComanda) => filtro === "todos" || item.tipo === filtro,
    [filtro]
  );

  // Comandas activas que tienen al menos un ítem pendiente en la estación seleccionada
  const comandasActivas = useMemo(() => {
    return comandas
      .map((c) => ({
        ...c,
        itemsVisiblesPendientes: c.items.filter((it) => !it.listo && itemCoincideEstacion(it)),
      }))
      .filter((c) => c.itemsVisiblesPendientes.length > 0);
  }, [comandas, itemCoincideEstacion]);

  // Historial reciente: comandas que tienen ítems ya marcados como listos en la estación actual
  const ordenesAnteriores = useMemo(() => {
    return [...comandas]
      .filter((c) => c.items.some((it) => it.listo && itemCoincideEstacion(it)))
      .reverse();
  }, [comandas, itemCoincideEstacion]);

  const handleMarcarListo = async (comandaId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/cocina/comandas/${comandaId}/completar`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ estacion: filtro }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const actualizada: Comanda = await res.json();
      setComandas((prev) => prev.map((c) => (c.id === comandaId ? actualizada : c)));
    } catch {
      setError("Error al marcar la orden como lista.");
    }
  };

  const handleRestaurar = async (comandaId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/cocina/comandas/${comandaId}/restaurar`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ estacion: filtro }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const actualizada: Comanda = await res.json();
      setComandas((prev) => prev.map((c) => (c.id === comandaId ? actualizada : c)));
    } catch {
      setError("Error al restaurar la orden.");
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-4 md:p-6 select-none">
      {/* Encabezado y 3 submenús de estación */}
      <header className="flex flex-wrap items-center justify-between gap-4 pb-5 border-b border-zinc-800">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
            Visiak KDS · Cocina &amp; Barra
          </h1>
          <p className="text-sm text-zinc-400">
            0–10m Verde · 10–25m Amarillo · 25m+ Rojo
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {(
            [
              { key: "todos", label: "Alimentos y bebidas" },
              { key: "alimento", label: "Solo alimentos" },
              { key: "bebida", label: "Solo bebidas" },
            ] as const
          ).map((tab) => {
            const activo = filtro === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setFiltro(tab.key)}
                className={`px-4 py-3 rounded-xl text-sm md:text-base font-semibold transition cursor-pointer ${
                  activo
                    ? "bg-amber-400 text-zinc-950 shadow-lg"
                    : "bg-zinc-900 text-zinc-300 hover:bg-zinc-800 border border-zinc-700"
                }`}
              >
                {tab.label}
              </button>
            );
          })}

          <button
            type="button"
            onClick={() => setMostrarAnteriores((v) => !v)}
            className="px-4 py-3 rounded-xl text-sm md:text-base font-semibold bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-zinc-600 cursor-pointer"
          >
            Órdenes anteriores ({ordenesAnteriores.length})
          </button>

          <button
            type="button"
            onClick={cargarComandas}
            className="px-3 py-3 rounded-xl text-sm font-semibold bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-700 cursor-pointer"
          >
            Actualizar
          </button>
        </div>
      </header>

      {error && (
        <div className="mt-4 p-3 rounded-xl bg-rose-950/80 border border-rose-500 text-rose-200 text-sm">
          {error}
        </div>
      )}

      {/* Panel de Órdenes anteriores */}
      {mostrarAnteriores && (
        <section className="mt-6 p-4 rounded-2xl bg-zinc-900 border border-zinc-700">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-bold">Órdenes anteriores (recuperación rápida)</h2>
            <button
              type="button"
              onClick={() => setMostrarAnteriores(false)}
              className="text-sm text-zinc-400 hover:text-white cursor-pointer"
            >
              Cerrar
            </button>
          </div>

          {ordenesAnteriores.length === 0 ? (
            <p className="text-sm text-zinc-400">No hay órdenes completadas en esta vista.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {ordenesAnteriores.map((c) => (
                <div
                  key={c.id}
                  className="p-3 rounded-xl bg-zinc-950 border border-zinc-800 flex items-center justify-between gap-3"
                >
                  <div>
                    <div className="font-bold text-base">
                      Mesa {c.mesa} · Ronda #{c.numero_ronda}
                    </div>
                    <div className="text-xs text-zinc-400 mt-0.5">
                      {c.items
                        .filter((it) => it.listo && itemCoincideEstacion(it))
                        .map((it) => `${it.cantidad}x ${it.nombre}`)
                        .join(", ")}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRestaurar(c.id)}
                    className="px-3 py-2 rounded-lg bg-amber-400/20 hover:bg-amber-400/30 text-amber-300 border border-amber-400/50 text-xs font-semibold shrink-0 cursor-pointer"
                  >
                    Restaurar
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Pantalla principal de comandas activas */}
      <main className="mt-6">
        {cargando ? (
          <div className="text-zinc-400 text-base py-12 text-center">Cargando comandas...</div>
        ) : comandasActivas.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-zinc-800 p-12 text-center text-zinc-400">
            No hay órdenes pendientes en{" "}
            <span className="text-zinc-200 font-semibold">
              {filtro === "todos"
                ? "Alimentos y bebidas"
                : filtro === "alimento"
                ? "Solo alimentos"
                : "Solo bebidas"}
            </span>
            .
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {comandasActivas.map((comanda) => {
              const tiempo = obtenerEstadoTiempo(comanda.creada_en, ahoraMs);
              return (
                <article
                  key={comanda.id}
                  className={`rounded-2xl bg-zinc-900 border-2 ${tiempo.bordeTarjeta} overflow-hidden flex flex-col justify-between shadow-lg`}
                >
                  <div>
                    {/* Barra dinámica de tiempo */}
                    <div className="w-full h-3 bg-zinc-800">
                      <div
                        className={`h-full ${tiempo.bgBarra} transition-all duration-500`}
                        style={{ width: `${tiempo.porcentaje}%` }}
                      />
                    </div>

                    <div className="p-4">
                      <div className="flex items-center justify-between gap-2 pb-3 border-b border-zinc-800">
                        <div>
                          <span className="text-xl font-extrabold text-white">
                            Mesa {comanda.mesa}
                          </span>
                          <span className="ml-2 text-sm font-medium text-zinc-400">
                            Ronda #{comanda.numero_ronda}
                          </span>
                        </div>
                        <span
                          className={`px-3 py-1 rounded-full text-sm font-bold ${tiempo.badgeTexto}`}
                        >
                          {tiempo.label}
                        </span>
                      </div>

                      <ul className="mt-3 space-y-2.5">
                        {comanda.itemsVisiblesPendientes.map((item) => (
                          <li
                            key={item.id}
                            className="p-2.5 rounded-xl bg-zinc-950/90 border border-zinc-800"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <span className="text-base font-semibold text-zinc-100">
                                <strong className="text-amber-400 mr-1.5">{item.cantidad}x</strong>
                                {item.nombre}
                              </span>
                              <span className="text-[11px] uppercase tracking-wider px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">
                                {item.tipo}
                              </span>
                            </div>
                            {item.notas && (
                              <p className="mt-1.5 text-sm font-medium text-amber-300 bg-amber-950/50 border border-amber-500/30 rounded-lg px-2.5 py-1">
                                Nota: {item.notas}
                              </p>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  <div className="p-4 pt-0">
                    <button
                      type="button"
                      onClick={() => handleMarcarListo(comanda.id)}
                      className="w-full py-3.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 active:scale-[0.99] text-zinc-950 font-extrabold text-base tracking-wide transition cursor-pointer"
                    >
                      LISTO
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}

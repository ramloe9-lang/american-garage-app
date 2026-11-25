import React, { useCallback, useEffect, useMemo, useState } from "react";

export type TipoEstacion = "alimento" | "bebida";
export type FiltroEstacion = "todos" | "alimento" | "bebida";
export type VistaActiva = FiltroEstacion | "estatus_mesas" | "cuentas";
export type MetodoPago = "efectivo" | "tarjeta";

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
  entregado?: boolean;
  entregado_en?: string | null;
  ya_entregado_antes?: boolean;
}

export interface Comanda {
  id: string;
  mesa: string;
  numero_ronda: number;
  cuenta_id?: string;
  creada_en: string;
  items: ItemComanda[];
  completada_total: boolean;
  ultima_actualizacion: string;
}

export interface EntregaPendienteMesa {
  id: string;
  comanda_id: string;
  mesa: string;
  numero_ronda: number;
  cuenta_id?: string;
  estacion: FiltroEstacion;
  listo_en: string;
  items: ItemComanda[];
}

export interface LlamadoMesero {
  id: string;
  mesa: string;
  motivo: string;
  creado_en: string;
  atendido: boolean;
  atendido_en: string | null;
}

export interface RegistroEntregaAnterior {
  id: string;
  comanda_id: string;
  mesa: string;
  numero_ronda: number;
  cuenta_id?: string;
  numero_cuenta?: number;
  estacion: FiltroEstacion;
  items: ItemComanda[];
  listo_en: string;
  entregado_en: string;
}

export interface EstatusMesasResponse {
  entregas_pendientes: EntregaPendienteMesa[];
  llamados_activos: LlamadoMesero[];
  llamados_atendidos: LlamadoMesero[];
  ordenes_anteriores: RegistroEntregaAnterior[];
}

export interface ItemRondaCuentaCobro {
  producto_id: string;
  nombre: string;
  categoria: string;
  precio: number;
  cantidad: number;
  comentarios?: string;
  subtotal: number;
}

export interface RondaCuentaCobro {
  numeroRonda: number;
  items: ItemRondaCuentaCobro[];
  subtotalRonda: number;
  confirmadaEn?: string;
}

export interface CuentaPorCobrar {
  id: string;
  mesa: string;
  cuenta_id: string;
  rondas: RondaCuentaCobro[];
  subtotal: number;
  solicitada_en: string;
}

interface EstadoCobroLocal {
  propinaMonto: number;
  tipoPropina: "ninguna" | "10" | "20" | "perso";
  montoPersoTexto: string;
  metodoPago: MetodoPago;
}

export interface ProductoMasVendidoInfo {
  nombre: string;
  cantidad: number;
}

export interface ResumenDiaResponse {
  cantidad_cuentas: number;
  subtotal_ventas: number;
  propinas_totales: number;
  total_general: number;
  total_efectivo: number;
  total_tarjeta: number;
  producto_mas_vendido: ProductoMasVendidoInfo | null;
  alimento_mas_vendido: ProductoMasVendidoInfo | null;
  bebida_mas_vendido: ProductoMasVendidoInfo | null;
  combo_mas_vendido: ProductoMasVendidoInfo | null;
}

const API_BASE =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL ||
  "https://american-garage-app.onrender.com";

const STORAGE_FILTRO_KEY = "visiak_cocina_filtro_estacion";

function formatoMoneda(valor: number): string {
  return valor.toLocaleString("es-MX", {
    style: "currency",
    currency: "MXN",
    minimumFractionDigits: 2,
  });
}

function obtenerEstadoTiempo(
  fechaIso: string,
  ahoraMs: number,
  umbrales: { verdeMaxMin: number; amarilloMaxMin: number }
) {
  const inicioMs = new Date(fechaIso).getTime();
  const minutos = Math.max(0, Math.floor((ahoraMs - inicioMs) / 60000));
  const totalUmbral = Math.max(1, umbrales.amarilloMaxMin);

  if (minutos < umbrales.verdeMaxMin) {
    return {
      minutos,
      label: `${minutos} min`,
      bgBarra: "bg-emerald-500",
      bordeTarjeta: "border-emerald-500/50",
      badgeTexto: "text-emerald-300 bg-emerald-950/70",
      porcentaje: Math.min(100, Math.max(10, (minutos / Math.max(1, umbrales.verdeMaxMin)) * 100)),
    };
  }
  if (minutos < umbrales.amarilloMaxMin) {
    const rango = Math.max(1, umbrales.amarilloMaxMin - umbrales.verdeMaxMin);
    return {
      minutos,
      label: `${minutos} min`,
      bgBarra: "bg-amber-400",
      bordeTarjeta: "border-amber-400/60",
      badgeTexto: "text-amber-300 bg-amber-950/70",
      porcentaje: Math.min(100, Math.max(25, ((minutos - umbrales.verdeMaxMin) / rango) * 100)),
    };
  }
  return {
    minutos,
    label: `${minutos} min`,
    bgBarra: "bg-rose-500",
    bordeTarjeta: "border-rose-500/70",
    badgeTexto: "text-rose-300 bg-rose-950/70",
    porcentaje: Math.min(100, Math.max(85, (minutos / totalUmbral) * 100)),
  };
}

export default function CocinaView() {
  const [vista, setVista] = useState<VistaActiva>(() => {
    const guardado = localStorage.getItem(STORAGE_FILTRO_KEY);
    return guardado === "alimento" ||
      guardado === "bebida" ||
      guardado === "todos" ||
      guardado === "estatus_mesas" ||
      guardado === "cuentas"
      ? guardado
      : "todos";
  });

  const filtroEstacion: FiltroEstacion =
    vista === "estatus_mesas" || vista === "cuentas" ? "todos" : vista;

  const [comandas, setComandas] = useState<Comanda[]>([]);
  const [estatusMesas, setEstatusMesas] = useState<EstatusMesasResponse>({
    entregas_pendientes: [],
    llamados_activos: [],
    llamados_atendidos: [],
    ordenes_anteriores: [],
  });
  const [cuentasPorCobrar, setCuentasPorCobrar] = useState<CuentaPorCobrar[]>([]);
  const [cobroPorCuentaId, setCobroPorCuentaId] = useState<Record<string, EstadoCobroLocal>>({});
  const [pagandoId, setPagandoId] = useState<string | null>(null);

  // Estados para "Terminar el día" y Resumen del día
  const [confirmarTerminarDia, setConfirmarTerminarDia] = useState(false);
  const [cargandoResumenDia, setCargandoResumenDia] = useState(false);
  const [resumenDia, setResumenDia] = useState<ResumenDiaResponse | null>(null);
  const [ventaEsperadaTexto, setVentaEsperadaTexto] = useState("");
  const [resultadoVentaEsperada, setResultadoVentaEsperada] = useState<{
    logrado: boolean;
    diferencia: number;
  } | null>(null);

  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mostrarAnteriores, setMostrarAnteriores] = useState(false);
  const [mostrarAnterioresMesas, setMostrarAnterioresMesas] = useState(false);
  const [ahoraMs, setAhoraMs] = useState(() => Date.now());

  useEffect(() => {
    localStorage.setItem(STORAGE_FILTRO_KEY, vista);
  }, [vista]);

  useEffect(() => {
    const timer = window.setInterval(() => setAhoraMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const cargarTodo = useCallback(async () => {
    try {
      const [resComandas, resMesas, resCuentas] = await Promise.all([
        fetch(`${API_BASE}/api/v1/cocina/comandas?incluir_completadas=true&t=${Date.now()}`, {
          cache: "no-store",
        }),
        fetch(`${API_BASE}/api/v1/cocina/estatus-mesas?t=${Date.now()}`, {
          cache: "no-store",
        }),
        fetch(`${API_BASE}/api/v1/cocina/cuentas-por-cobrar?t=${Date.now()}`, {
          cache: "no-store",
        }),
      ]);

      if (!resComandas.ok) throw new Error(`HTTP ${resComandas.status}`);
      const dataComandas: Comanda[] = await resComandas.json();
      setComandas(dataComandas);

      if (resMesas.ok) {
        const dataMesas: EstatusMesasResponse = await resMesas.json();
        setEstatusMesas(dataMesas);
      }

      if (resCuentas.ok) {
        const dataCuentas: CuentaPorCobrar[] = await resCuentas.json();
        setCuentasPorCobrar(dataCuentas);
      }

      setError(null);
    } catch {
      setError("No se pudieron sincronizar los datos con el servidor.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargarTodo();
    const polling = window.setInterval(cargarTodo, 3000);
    return () => window.clearInterval(polling);
  }, [cargarTodo]);

  const itemCoincideEstacion = useCallback(
    (item: ItemComanda) => filtroEstacion === "todos" || item.tipo === filtroEstacion,
    [filtroEstacion]
  );

  const comandasActivas = useMemo(() => {
    return comandas
      .map((c) => ({
        ...c,
        itemsVisiblesPendientes: c.items.filter((it) => !it.listo && itemCoincideEstacion(it)),
      }))
      .filter((c) => c.itemsVisiblesPendientes.length > 0);
  }, [comandas, itemCoincideEstacion]);

  const ordenesAnterioresCocina = useMemo(() => {
    return [...comandas]
      .filter((c) => c.items.some((it) => it.listo && itemCoincideEstacion(it)))
      .reverse();
  }, [comandas, itemCoincideEstacion]);

  const entregasConsolidadasMesas = useMemo(() => {
    const mapa = new Map<string, RegistroEntregaAnterior>();

    for (const reg of estatusMesas.ordenes_anteriores) {
      const clave = `${reg.mesa}__${reg.cuenta_id || reg.comanda_id}__${reg.numero_ronda}`;
      const existente = mapa.get(clave);
      if (!existente) {
        mapa.set(clave, {
          ...reg,
          items: [...reg.items],
        });
      } else {
        const itemsPorId = new Map<string, ItemComanda>();
        for (const it of existente.items) itemsPorId.set(it.id, it);
        for (const it of reg.items) itemsPorId.set(it.id, it);
        mapa.set(clave, {
          ...existente,
          items: Array.from(itemsPorId.values()),
          entregado_en:
            new Date(reg.entregado_en) > new Date(existente.entregado_en)
              ? reg.entregado_en
              : existente.entregado_en,
        });
      }
    }

    return Array.from(mapa.values());
  }, [estatusMesas.ordenes_anteriores]);

  const cuentasAgrupadasMesas = useMemo(() => {
    const mapaCuentas = new Map<
      string,
      {
        claveCuenta: string;
        mesa: string;
        cuentaId: string;
        numeroCuenta: number;
        rondas: RegistroEntregaAnterior[];
      }
    >();

    for (const reg of entregasConsolidadasMesas) {
      const cuentaId = reg.cuenta_id || `comanda-${reg.comanda_id}`;
      const claveCuenta = `${reg.mesa}__${cuentaId}`;

      if (!mapaCuentas.has(claveCuenta)) {
        mapaCuentas.set(claveCuenta, {
          claveCuenta,
          mesa: reg.mesa,
          cuentaId,
          numeroCuenta: reg.numero_cuenta ?? 1,
          rondas: [],
        });
      }

      mapaCuentas.get(claveCuenta)!.rondas.push(reg);
    }

    return Array.from(mapaCuentas.values())
      .map((grupo) => ({
        ...grupo,
        rondas: [...grupo.rondas].sort((a, b) => a.numero_ronda - b.numero_ronda),
      }))
      .sort((a, b) => a.numeroCuenta - b.numeroCuenta);
  }, [entregasConsolidadasMesas]);

  const totalAlertasEstatusMesas =
    estatusMesas.entregas_pendientes.length + estatusMesas.llamados_activos.length;

  const totalHistorialEstatusMesas =
    entregasConsolidadasMesas.length + estatusMesas.llamados_atendidos.length;

  const getEstadoCobro = (cuentaId: string): EstadoCobroLocal => {
    return (
      cobroPorCuentaId[cuentaId] || {
        propinaMonto: 0,
        tipoPropina: "ninguna",
        montoPersoTexto: "",
        metodoPago: "efectivo",
      }
    );
  };

  const actualizarEstadoCobro = (cuentaId: string, parcial: Partial<EstadoCobroLocal>) => {
    setCobroPorCuentaId((prev) => {
      const actual = prev[cuentaId] || {
        propinaMonto: 0,
        tipoPropina: "ninguna",
        montoPersoTexto: "",
        metodoPago: "efectivo",
      };
      return {
        ...prev,
        [cuentaId]: { ...actual, ...parcial },
      };
    });
  };

  const handleSeleccionarPropinaPorcentaje = (cuenta: CuentaPorCobrar, porcentaje: 10 | 20) => {
    const actual = getEstadoCobro(cuenta.id);
    const clave = String(porcentaje) as "10" | "20";
    if (actual.tipoPropina === clave) {
      actualizarEstadoCobro(cuenta.id, {
        propinaMonto: 0,
        tipoPropina: "ninguna",
        montoPersoTexto: "",
      });
      return;
    }
    const calculada = Math.round(cuenta.subtotal * (porcentaje / 100) * 100) / 100;
    actualizarEstadoCobro(cuenta.id, {
      propinaMonto: calculada,
      tipoPropina: clave,
      montoPersoTexto: "",
    });
  };

  const handleCambioMontoPerso = (cuentaId: string, texto: string) => {
    const limpio = texto.replace(/[^0-9.]/g, "");
    const numerico = parseFloat(limpio);
    actualizarEstadoCobro(cuentaId, {
      montoPersoTexto: limpio,
      tipoPropina: limpio === "" ? "ninguna" : "perso",
      propinaMonto: !Number.isNaN(numerico) && numerico >= 0 ? Math.round(numerico * 100) / 100 : 0,
    });
  };

  const handleCuentaPagada = async (cuenta: CuentaPorCobrar) => {
    const estado = getEstadoCobro(cuenta.id);
    setPagandoId(cuenta.id);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/cocina/cuentas-por-cobrar/${encodeURIComponent(cuenta.id)}/pagar`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            metodo_pago: estado.metodoPago,
            propina: estado.propinaMonto,
          }),
        }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setCuentasPorCobrar((prev) => prev.filter((c) => c.id !== cuenta.id));
      setCobroPorCuentaId((prev) => {
        const copia = { ...prev };
        delete copia[cuenta.id];
        return copia;
      });
      await cargarTodo();
    } catch {
      setError("Error al registrar el pago de la cuenta.");
    } finally {
      setPagandoId(null);
    }
  };

  const abrirConfirmacionTerminarDia = () => {
    setConfirmarTerminarDia(true);
  };

  const confirmarYMostrarResumenDia = async () => {
    setConfirmarTerminarDia(false);
    setCargandoResumenDia(true);
    setResultadoVentaEsperada(null);
    setVentaEsperadaTexto("");
    try {
      const res = await fetch(`${API_BASE}/api/v1/cocina/resumen-dia?t=${Date.now()}`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ResumenDiaResponse = await res.json();
      setResumenDia(data);
    } catch {
      setError("No se pudo generar el resumen del día.");
    } finally {
      setCargandoResumenDia(false);
    }
  };

  const calcularVentaEsperada = () => {
    if (!resumenDia) return;
    const esperado = parseFloat(ventaEsperadaTexto);
    if (Number.isNaN(esperado) || esperado < 0) {
      setResultadoVentaEsperada(null);
      return;
    }
    const subtotalHoy = resumenDia.subtotal_ventas;
    if (subtotalHoy >= esperado) {
      setResultadoVentaEsperada({
        logrado: true,
        diferencia: Math.round((subtotalHoy - esperado) * 100) / 100,
      });
    } else {
      setResultadoVentaEsperada({
        logrado: false,
        diferencia: Math.round((esperado - subtotalHoy) * 100) / 100,
      });
    }
  };

  const handleCerrarDiaDefinitivo = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/cocina/cerrar-dia`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setResumenDia(null);
      setVentaEsperadaTexto("");
      setResultadoVentaEsperada(null);
      await cargarTodo();
    } catch {
      setError("Error al cerrar el día.");
    }
  };

  const handleMarcarListo = async (comandaId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/cocina/comandas/${comandaId}/completar`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ estacion: filtroEstacion }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const actualizada: Comanda = await res.json();
      setComandas((prev) => prev.map((c) => (c.id === comandaId ? actualizada : c)));
      await cargarTodo();
    } catch {
      setError("Error al marcar la orden como lista.");
    }
  };

  const handleRestaurar = async (comandaId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/cocina/comandas/${comandaId}/restaurar`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ estacion: filtroEstacion }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const actualizada: Comanda = await res.json();
      setComandas((prev) => prev.map((c) => (c.id === comandaId ? actualizada : c)));
      await cargarTodo();
    } catch {
      setError("Error al restaurar la orden.");
    }
  };

  const handleMarcarEntregadoMesa = async (entrega: EntregaPendienteMesa) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/cocina/estatus-mesas/entregar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          comanda_id: entrega.comanda_id,
          estacion: entrega.estacion,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await cargarTodo();
    } catch {
      setError("Error al marcar la entrega de la mesa como completada.");
    }
  };

  const handleAtenderLlamado = async (llamadoId: string) => {
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/cocina/llamados-mesero/${encodeURIComponent(llamadoId)}/atender`,
        {
          method: "PATCH",
        }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await cargarTodo();
    } catch {
      setError("Error al marcar el llamado del mesero como atendido.");
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-4 md:p-6 select-none">
      <header className="flex flex-wrap items-center justify-between gap-4 pb-5 border-b border-zinc-800">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
            Visiak KDS · Cocina &amp; Barra
          </h1>
          <p className="text-sm text-zinc-400">
            {vista === "estatus_mesas"
              ? "Estatus mesas · 0–3m Verde · 3–8m Amarillo · 8m+ Rojo"
              : vista === "cuentas"
              ? "Cuentas por cobrar · Propinas y cierre de pago"
              : "0–10m Verde · 10–25m Amarillo · 25m+ Rojo"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {(
            [
              { key: "todos", label: "Alimentos y bebidas" },
              { key: "alimento", label: "Solo alimentos" },
              { key: "bebida", label: "Solo bebidas" },
              {
                key: "estatus_mesas",
                label: `Estatus mesas${totalAlertasEstatusMesas > 0 ? ` (${totalAlertasEstatusMesas})` : ""}`,
              },
              {
                key: "cuentas",
                label: `Cuentas${cuentasPorCobrar.length > 0 ? ` (${cuentasPorCobrar.length})` : ""}`,
              },
            ] as const
          ).map((tab) => {
            const activo = vista === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setVista(tab.key)}
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

          {vista === "estatus_mesas" && (
            <button
              type="button"
              onClick={() => setMostrarAnterioresMesas((v) => !v)}
              className="px-4 py-3 rounded-xl text-sm md:text-base font-semibold bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-zinc-600 cursor-pointer"
            >
              Órdenes anteriores ({totalHistorialEstatusMesas})
            </button>
          )}

          {vista !== "estatus_mesas" && vista !== "cuentas" && (
            <button
              type="button"
              onClick={() => setMostrarAnteriores((v) => !v)}
              className="px-4 py-3 rounded-xl text-sm md:text-base font-semibold bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-zinc-600 cursor-pointer"
            >
              Órdenes anteriores ({ordenesAnterioresCocina.length})
            </button>
          )}

          <button
            type="button"
            onClick={cargarTodo}
            className="px-3 py-3 rounded-xl text-sm font-semibold bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-700 cursor-pointer"
          >
            Actualizar
          </button>

          <button
            type="button"
            onClick={abrirConfirmacionTerminarDia}
            className="px-4 py-3 rounded-xl text-sm font-extrabold bg-rose-600 hover:bg-rose-500 text-white border border-rose-400/50 shadow-md transition cursor-pointer"
          >
            Terminar el día
          </button>
        </div>
      </header>

      {error && (
        <div className="mt-4 p-3 rounded-xl bg-rose-950/80 border border-rose-500 text-rose-200 text-sm">
          {error}
        </div>
      )}

      {/* MODAL CONFIRMACIÓN: ¿SEGURO QUE QUIERES TERMINAR EL DÍA? */}
      {confirmarTerminarDia && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-sm rounded-2xl bg-zinc-900 border border-rose-500/50 p-6 text-center shadow-2xl space-y-4">
            <h2 className="text-lg font-extrabold text-white">
              ¿Seguro que quieres terminar el día?
            </h2>
            <p className="text-xs text-zinc-400">
              Se generará el resumen de ventas y propinas registradas hoy.
            </p>
            <div className="grid grid-cols-2 gap-3 pt-2">
              <button
                type="button"
                onClick={() => setConfirmarTerminarDia(false)}
                className="py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-bold text-sm transition cursor-pointer"
              >
                No
              </button>
              <button
                type="button"
                onClick={confirmarYMostrarResumenDia}
                className="py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-extrabold text-sm transition cursor-pointer"
              >
                Sí
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL REPORTE: RESUMEN DEL DÍA */}
      {(cargandoResumenDia || resumenDia) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl bg-zinc-900 border border-zinc-700 p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
              <h2 className="text-xl font-extrabold text-amber-400">Resumen del día</h2>
              <button
                type="button"
                onClick={() => {
                  setResumenDia(null);
                  setResultadoVentaEsperada(null);
                  setVentaEsperadaTexto("");
                }}
                className="text-zinc-400 hover:text-white text-lg font-bold px-2 cursor-pointer"
              >
                ✕
              </button>
            </div>

            {cargandoResumenDia || !resumenDia ? (
              <p className="text-sm text-zinc-400 py-8 text-center">Calculando resumen...</p>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
                  <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800">
                    <span className="text-zinc-400 block">Producto más vendido en general</span>
                    <strong className="text-sm text-white mt-0.5 block">
                      {resumenDia.producto_mas_vendido
                        ? `${resumenDia.producto_mas_vendido.nombre} (${resumenDia.producto_mas_vendido.cantidad})`
                        : "Sin ventas registradas"}
                    </strong>
                  </div>

                  <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800">
                    <span className="text-zinc-400 block">Alimento más vendido</span>
                    <strong className="text-sm text-white mt-0.5 block">
                      {resumenDia.alimento_mas_vendido
                        ? `${resumenDia.alimento_mas_vendido.nombre} (${resumenDia.alimento_mas_vendido.cantidad})`
                        : "Sin alimentos vendidos"}
                    </strong>
                  </div>

                  <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800">
                    <span className="text-zinc-400 block">Bebida más vendida</span>
                    <strong className="text-sm text-white mt-0.5 block">
                      {resumenDia.bebida_mas_vendido
                        ? `${resumenDia.bebida_mas_vendido.nombre} (${resumenDia.bebida_mas_vendido.cantidad})`
                        : "Sin bebidas vendidas"}
                    </strong>
                  </div>

                  <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800">
                    <span className="text-zinc-400 block">Combo más vendido</span>
                    <strong className="text-sm text-amber-300 mt-0.5 block">
                      {resumenDia.combo_mas_vendido
                        ? `${resumenDia.combo_mas_vendido.nombre} (${resumenDia.combo_mas_vendido.cantidad})`
                        : "Sin combos vendidos"}
                    </strong>
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-2 text-sm">
                  <div className="flex justify-between text-zinc-300">
                    <span>Subtotal vendido hoy (productos):</span>
                    <span className="font-bold text-white">
                      {formatoMoneda(resumenDia.subtotal_ventas)}
                    </span>
                  </div>
                  <div className="flex justify-between text-zinc-300">
                    <span>Propinas recaudadas hoy:</span>
                    <span className="font-bold text-emerald-400">
                      {formatoMoneda(resumenDia.propinas_totales)}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-zinc-400 pt-1 border-t border-zinc-800/80">
                    <span>Efectivo: {formatoMoneda(resumenDia.total_efectivo)}</span>
                    <span>Tarjeta: {formatoMoneda(resumenDia.total_tarjeta)}</span>
                  </div>
                </div>

                {/* Apartado Total de venta esperada */}
                <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-2.5">
                  <label className="block text-xs font-bold uppercase tracking-wider text-zinc-300">
                    Total de venta esperada:
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400 text-sm">
                      $
                    </span>
                    <input
                      type="text"
                      inputMode="decimal"
                      placeholder="Ej. 5000 y presiona Enter"
                      value={ventaEsperadaTexto}
                      onChange={(e) => {
                        const limpio = e.target.value.replace(/[^0-9.]/g, "");
                        setVentaEsperadaTexto(limpio);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          calcularVentaEsperada();
                        }
                      }}
                      className="w-full pl-7 pr-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-white text-sm font-semibold focus:outline-none focus:border-amber-400"
                    />
                  </div>

                  {resultadoVentaEsperada && (
                    <p
                      className={`text-sm font-extrabold pt-1 ${
                        resultadoVentaEsperada.logrado ? "text-emerald-400" : "text-rose-400"
                      }`}
                    >
                      {resultadoVentaEsperada.logrado
                        ? `¡Se logró la venta esperada por ${formatoMoneda(
                            resultadoVentaEsperada.diferencia
                          )}!`
                        : `Faltó ${formatoMoneda(
                            resultadoVentaEsperada.diferencia
                          )} para llegar a lo esperado.`}
                    </p>
                  )}
                </div>

                <div className="flex items-center justify-between gap-2 pt-1">
                  <button
                    type="button"
                    onClick={handleCerrarDiaDefinitivo}
                    className="px-4 py-2.5 rounded-xl bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 text-xs font-bold transition cursor-pointer"
                  >
                    Reiniciar corte del día
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setResumenDia(null);
                      setResultadoVentaEsperada(null);
                      setVentaEsperadaTexto("");
                    }}
                    className="px-5 py-2.5 rounded-xl bg-amber-400 hover:bg-amber-300 text-zinc-950 text-xs font-extrabold transition cursor-pointer"
                  >
                    Listo
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {vista === "cuentas" ? (
        <main className="mt-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-amber-400">
              Cuentas finalizadas pendientes de cobro ({cuentasPorCobrar.length})
            </h2>
          </div>

          {cargando ? (
            <div className="text-zinc-400 text-base py-12 text-center">Cargando cuentas...</div>
          ) : cuentasPorCobrar.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-zinc-800 p-12 text-center text-zinc-400">
              No hay cuentas pendientes de cobro en este momento.
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-5">
              {cuentasPorCobrar.map((cuenta) => {
                const estado = getEstadoCobro(cuenta.id);
                const totalFinal = Math.round((cuenta.subtotal + estado.propinaMonto) * 100) / 100;
                const propina10 = Math.round(cuenta.subtotal * 0.1 * 100) / 100;
                const propina20 = Math.round(cuenta.subtotal * 0.2 * 100) / 100;

                return (
                  <article
                    key={cuenta.id}
                    className="rounded-2xl bg-zinc-900 border-2 border-amber-400/50 p-5 flex flex-col justify-between shadow-lg space-y-4"
                  >
                    <div className="space-y-3">
                      <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
                        <div>
                          <span className="text-xl font-extrabold text-white">
                            Mesa {cuenta.mesa}
                          </span>
                          <span className="ml-2 text-xs font-semibold uppercase px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300">
                            Por cobrar
                          </span>
                        </div>
                        <span className="text-xs text-zinc-400">
                          {new Date(cuenta.solicitada_en).toLocaleTimeString("es-MX", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>

                      <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
                        {cuenta.rondas.map((ronda) => (
                          <div
                            key={ronda.numeroRonda}
                            className="p-3 rounded-xl bg-zinc-950/90 border border-zinc-800 space-y-1.5"
                          >
                            <div className="flex items-center justify-between text-xs font-bold text-amber-300">
                              <span>Ronda #{ronda.numeroRonda}</span>
                              <span>{formatoMoneda(ronda.subtotalRonda)}</span>
                            </div>
                            <ul className="space-y-1">
                              {ronda.items.map((it, idx) => (
                                <li
                                  key={`${it.producto_id}-${idx}`}
                                  className="flex items-center justify-between text-xs text-zinc-200"
                                >
                                  <span>
                                    <strong className="text-zinc-400 mr-1">{it.cantidad}x</strong>
                                    {it.nombre}
                                  </span>
                                  <span className="text-zinc-300">
                                    {formatoMoneda(it.subtotal)}
                                  </span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>

                      <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                            Propina
                          </span>
                          <span className="text-sm font-bold text-emerald-400">
                            +{formatoMoneda(estado.propinaMonto)}
                          </span>
                        </div>

                        <div className="grid grid-cols-2 gap-2">
                          <button
                            type="button"
                            onClick={() => handleSeleccionarPropinaPorcentaje(cuenta, 10)}
                            className={`py-2.5 px-3 rounded-xl text-xs font-extrabold border transition cursor-pointer ${
                              estado.tipoPropina === "10"
                                ? "bg-amber-400 text-zinc-950 border-amber-300"
                                : "bg-zinc-900 text-zinc-200 border-zinc-700 hover:bg-zinc-800"
                            }`}
                          >
                            10% propina ({formatoMoneda(propina10)})
                          </button>
                          <button
                            type="button"
                            onClick={() => handleSeleccionarPropinaPorcentaje(cuenta, 20)}
                            className={`py-2.5 px-3 rounded-xl text-xs font-extrabold border transition cursor-pointer ${
                              estado.tipoPropina === "20"
                                ? "bg-amber-400 text-zinc-950 border-amber-300"
                                : "bg-zinc-900 text-zinc-200 border-zinc-700 hover:bg-zinc-800"
                            }`}
                          >
                            20% propina ({formatoMoneda(propina20)})
                          </button>
                        </div>

                        <label className="flex items-center justify-between gap-2 text-xs font-semibold text-zinc-300">
                          <span className="shrink-0">Monto perso:</span>
                          <div className="relative flex-1">
                            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400">
                              $
                            </span>
                            <input
                              type="text"
                              inputMode="decimal"
                              placeholder="0.00"
                              value={estado.montoPersoTexto}
                              onChange={(e) => handleCambioMontoPerso(cuenta.id, e.target.value)}
                              className="w-full pl-7 pr-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-zinc-100 text-sm font-semibold focus:outline-none focus:border-amber-400"
                            />
                          </div>
                        </label>
                      </div>

                      <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1.5 text-sm">
                        <div className="flex justify-between text-zinc-400">
                          <span>Subtotal consumo:</span>
                          <span>{formatoMoneda(cuenta.subtotal)}</span>
                        </div>
                        <div className="flex justify-between text-zinc-400">
                          <span>Propina:</span>
                          <span>{formatoMoneda(estado.propinaMonto)}</span>
                        </div>
                        <div className="flex justify-between text-base font-extrabold text-white pt-1.5 border-t border-zinc-800">
                          <span>Total final:</span>
                          <span className="text-emerald-400">{formatoMoneda(totalFinal)}</span>
                        </div>
                      </div>

                      <div className="space-y-1.5">
                        <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                          Método de pago
                        </span>
                        <div className="grid grid-cols-2 gap-2">
                          <button
                            type="button"
                            onClick={() =>
                              actualizarEstadoCobro(cuenta.id, { metodoPago: "efectivo" })
                            }
                            className={`py-2.5 rounded-xl text-xs font-extrabold border transition cursor-pointer ${
                              estado.metodoPago === "efectivo"
                                ? "bg-emerald-500/20 text-emerald-300 border-emerald-400"
                                : "bg-zinc-950 text-zinc-400 border-zinc-800 hover:text-zinc-200"
                            }`}
                          >
                            Efectivo
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              actualizarEstadoCobro(cuenta.id, { metodoPago: "tarjeta" })
                            }
                            className={`py-2.5 rounded-xl text-xs font-extrabold border transition cursor-pointer ${
                              estado.metodoPago === "tarjeta"
                                ? "bg-sky-500/20 text-sky-300 border-sky-400"
                                : "bg-zinc-950 text-zinc-400 border-zinc-800 hover:text-zinc-200"
                            }`}
                          >
                            Tarjeta (Terminal)
                          </button>
                        </div>
                      </div>
                    </div>

                    <button
                      type="button"
                      disabled={pagandoId === cuenta.id}
                      onClick={() => handleCuentaPagada(cuenta)}
                      className="w-full py-3.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 active:scale-[0.99] text-zinc-950 font-extrabold text-base tracking-wide transition cursor-pointer"
                    >
                      {pagandoId === cuenta.id ? "REGISTRANDO..." : "CUENTA PAGADA"}
                    </button>
                  </article>
                );
              })}
            </div>
          )}
        </main>
      ) : vista === "estatus_mesas" ? (
        <main className="mt-6 space-y-6">
          {mostrarAnterioresMesas && (
            <section className="p-4 rounded-2xl bg-zinc-900 border border-zinc-700">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-bold">Órdenes anteriores · Entregas y llamados</h2>
                <button
                  type="button"
                  onClick={() => setMostrarAnterioresMesas(false)}
                  className="text-sm text-zinc-400 hover:text-white cursor-pointer"
                >
                  Cerrar
                </button>
              </div>

              {totalHistorialEstatusMesas === 0 ? (
                <p className="text-sm text-zinc-400">
                  Aún no hay entregas ni llamados atendidos en el historial.
                </p>
              ) : (
                <div className="space-y-4">
                  {cuentasAgrupadasMesas.length > 0 && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      {cuentasAgrupadasMesas.map((cuenta) => (
                        <div
                          key={cuenta.claveCuenta}
                          className="p-4 rounded-2xl bg-zinc-950/90 border-2 border-zinc-700/80 space-y-3"
                        >
                          <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
                            <span className="font-extrabold text-base text-amber-300">
                              Mesa {cuenta.mesa} · Cuenta #{cuenta.numeroCuenta}
                            </span>
                            <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-zinc-800 text-zinc-300">
                              {cuenta.rondas.length}{" "}
                              {cuenta.rondas.length === 1 ? "ronda" : "rondas"}
                            </span>
                          </div>

                          <div className="space-y-2.5">
                            {cuenta.rondas.map((reg) => (
                              <div
                                key={reg.id}
                                className="p-3 rounded-xl bg-zinc-900 border border-zinc-800 space-y-1.5"
                              >
                                <div className="flex items-center justify-between">
                                  <span className="font-bold text-sm text-white">
                                    Ronda #{reg.numero_ronda}
                                  </span>
                                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-500/30">
                                    Entregado
                                  </span>
                                </div>
                                <p className="text-xs text-zinc-300">
                                  {reg.items.map((it) => `${it.cantidad}x ${it.nombre}`).join(", ")}
                                </p>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {estatusMesas.llamados_atendidos.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {estatusMesas.llamados_atendidos.map((ll) => (
                        <div
                          key={ll.id}
                          className="p-3 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-base text-white">
                              Mesa {ll.mesa} · Llamado mesero
                            </span>
                            <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-500/30">
                              Atendido
                            </span>
                          </div>
                          <p className="text-xs text-zinc-400">{ll.motivo}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </section>
          )}

          <section>
            <h2 className="text-lg font-bold text-amber-400 mb-3">
              Alertas de llamado al mesero ({estatusMesas.llamados_activos.length})
            </h2>
            {estatusMesas.llamados_activos.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-zinc-800 p-6 text-center text-sm text-zinc-400">
                No hay llamados activos de mesero en este momento.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {estatusMesas.llamados_activos.map((llamado) => {
                  const tiempo = obtenerEstadoTiempo(llamado.creado_en, ahoraMs, {
                    verdeMaxMin: 3,
                    amarilloMaxMin: 8,
                  });
                  return (
                    <article
                      key={llamado.id}
                      className={`rounded-2xl bg-zinc-900 border-2 ${tiempo.bordeTarjeta} overflow-hidden flex flex-col justify-between shadow-lg`}
                    >
                      <div>
                        <div className="w-full h-3 bg-zinc-800">
                          <div
                            className={`h-full ${tiempo.bgBarra} transition-all duration-500`}
                            style={{ width: `${tiempo.porcentaje}%` }}
                          />
                        </div>
                        <div className="p-4">
                          <div className="flex items-center justify-between gap-2 pb-2 border-b border-zinc-800">
                            <div>
                              <span className="text-xl font-extrabold text-white">
                                Mesa {llamado.mesa}
                              </span>
                              <span className="ml-2 text-xs font-semibold uppercase px-2 py-0.5 rounded bg-amber-500/20 text-amber-300">
                                Llamar al mesero
                              </span>
                            </div>
                            <span
                              className={`px-3 py-1 rounded-full text-sm font-bold ${tiempo.badgeTexto}`}
                            >
                              {tiempo.label}
                            </span>
                          </div>
                          <p className="mt-3 text-sm text-zinc-200">{llamado.motivo}</p>
                        </div>
                      </div>
                      <div className="p-4 pt-0">
                        <button
                          type="button"
                          onClick={() => handleAtenderLlamado(llamado.id)}
                          className="w-full py-3 rounded-xl bg-amber-400 hover:bg-amber-300 text-zinc-950 font-extrabold text-sm tracking-wide transition cursor-pointer"
                        >
                          MARCAR ATENDIDO
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>

          <section>
            <h2 className="text-lg font-bold text-emerald-400 mb-3">
              Platillos y bebidas listos para entregar ({estatusMesas.entregas_pendientes.length})
            </h2>
            {cargando ? (
              <div className="text-zinc-400 text-base py-8 text-center">
                Cargando estatus de mesas...
              </div>
            ) : estatusMesas.entregas_pendientes.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-zinc-800 p-8 text-center text-sm text-zinc-400">
                No hay platillos ni bebidas listos pendientes de entregar a las mesas.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {estatusMesas.entregas_pendientes.map((entrega) => {
                  const tiempo = obtenerEstadoTiempo(entrega.listo_en, ahoraMs, {
                    verdeMaxMin: 3,
                    amarilloMaxMin: 8,
                  });
                  const etiquetaEstacion =
                    entrega.estacion === "alimento"
                      ? "Alimentos"
                      : entrega.estacion === "bebida"
                      ? "Bebidas"
                      : "Alimentos y bebidas";

                  return (
                    <article
                      key={entrega.id}
                      className={`rounded-2xl bg-zinc-900 border-2 ${tiempo.bordeTarjeta} overflow-hidden flex flex-col justify-between shadow-lg`}
                    >
                      <div>
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
                                Mesa {entrega.mesa}
                              </span>
                              <span className="ml-2 text-sm font-medium text-zinc-400">
                                Ronda #{entrega.numero_ronda}
                              </span>
                            </div>
                            <span
                              className={`px-3 py-1 rounded-full text-sm font-bold ${tiempo.badgeTexto}`}
                            >
                              {tiempo.label}
                            </span>
                          </div>

                          <div className="mt-2">
                            <span className="text-[11px] uppercase tracking-wider px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">
                              {etiquetaEstacion}
                            </span>
                          </div>

                          <ul className="mt-3 space-y-2">
                            {entrega.items.map((item) => (
                              <li
                                key={item.id}
                                className="p-2.5 rounded-xl bg-zinc-950/90 border border-zinc-800"
                              >
                                <div className="flex items-start justify-between gap-2">
                                  <span className="text-base font-semibold text-zinc-100">
                                    <strong className="text-emerald-400 mr-1.5">
                                      {item.cantidad}x
                                    </strong>
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
                          onClick={() => handleMarcarEntregadoMesa(entrega)}
                          className="w-full py-3.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 active:scale-[0.99] text-zinc-950 font-extrabold text-base tracking-wide transition cursor-pointer"
                        >
                          ENTREGADO A MESA
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </main>
      ) : (
        <>
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

              {ordenesAnterioresCocina.length === 0 ? (
                <p className="text-sm text-zinc-400">No hay órdenes completadas en esta vista.</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {ordenesAnterioresCocina.map((c) => (
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

          <main className="mt-6">
            {cargando ? (
              <div className="text-zinc-400 text-base py-12 text-center">Cargando comandas...</div>
            ) : comandasActivas.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-zinc-800 p-12 text-center text-zinc-400">
                No hay órdenes pendientes en{" "}
                <span className="text-zinc-200 font-semibold">
                  {filtroEstacion === "todos"
                    ? "Alimentos y bebidas"
                    : filtroEstacion === "alimento"
                    ? "Solo alimentos"
                    : "Solo bebidas"}
                </span>
                .
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {comandasActivas.map((comanda) => {
                  const tiempo = obtenerEstadoTiempo(comanda.creada_en, ahoraMs, {
                    verdeMaxMin: 10,
                    amarilloMaxMin: 25,
                  });
                  return (
                    <article
                      key={comanda.id}
                      className={`rounded-2xl bg-zinc-900 border-2 ${tiempo.bordeTarjeta} overflow-hidden flex flex-col justify-between shadow-lg`}
                    >
                      <div>
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
                                    <strong className="text-amber-400 mr-1.5">
                                      {item.cantidad}x
                                    </strong>
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
        </>
      )}
    </div>
  );
}

import React, { useState, useEffect, useCallback } from 'react';
import { useMesa } from '../hooks/useMesa';

interface Producto {
  id: string | number;
  nombre: string;
  categoria?: string;
  precio?: number;
  precio_final?: number;
  precio_original?: number;
  [key: string]: any;
}

interface ItemCarrito {
  id: string | number;
  nombre: string;
  categoria: string;
  precio: number;
  cantidad: number;
  comentarios: string;
  subtotal: number;
}

interface RondaPedido {
  numeroRonda: number;
  items: ItemCarrito[];
  subtotalRonda: number;
}

interface BotonOrdenarHeaderProps {
  productosDisponibles?: Producto[];
}

const obtenerPrecio = (prod: Producto): number => {
  return Number(prod.precio_final ?? prod.precio_original ?? prod.precio ?? 0);
};

const TELEFONO_RESTAURANTE = '524425568390';
const API_BASE =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL ||
  'https://american-garage-app.onrender.com';

export function BotonOrdenarHeader({ productosDisponibles = [] }: BotonOrdenarHeaderProps) {
  const mesa = useMesa();
  const [mostrarCatalogo, setMostrarCatalogo] = useState(false);
  const [mostrarResumen, setMostrarResumen] = useState(false);
  const [productoSeleccionado, setProductoSeleccionado] = useState<Producto | null>(null);

  // Pantallita de confirmación al enviar ronda a cocina
  const [mostrarConfirmacionEnvio, setMostrarConfirmacionEnvio] = useState(false);

  // Estado para el modal de personalización
  const [cantidad, setCantidad] = useState<number>(1);
  const [comentarios, setComentarios] = useState<string>('');

  // Estado para el método de pago seleccionado (usado al finalizar cuenta)
  const [metodoPago, setMetodoPago] = useState<string>('Efectivo');

  // Estado para indicar si está enviando la ronda o cerrando cuenta
  const [enviandoCocina, setEnviandoCocina] = useState<boolean>(false);
  const [finalizandoCuenta, setFinalizandoCuenta] = useState<boolean>(false);

  // Carrito de compras actual (siempre inicia vacío al abrir la web app)
  const [carrito, setCarrito] = useState<ItemCarrito[]>([]);

  // Cuenta acumulada de la mesa (rondas ya confirmadas, sincronizada entre dispositivos)
  const [rondasConfirmadas, setRondasConfirmadas] = useState<RondaPedido[]>([]);

  const cargarCuentaMesa = useCallback(async () => {
    if (!mesa) {
      setRondasConfirmadas([]);
      return;
    }

    try {
      const res = await fetch(
        `${API_BASE}/api/v1/cocina/cuentas/${encodeURIComponent(String(mesa))}?t=${Date.now()}`,
        { cache: 'no-store' }
      );
      if (!res.ok) return;
      const data = await res.json();
      const rondasServidor = Array.isArray(data.rondas) ? data.rondas : [];
      setRondasConfirmadas(rondasServidor);

      // Si la cuenta en el servidor ya fue finalizada (0 rondas) y no hay ítems en el carrito actual,
      // limpiamos cualquier residuo local y cerramos el modal de resumen si estaba abierto.
      if (rondasServidor.length === 0) {
        localStorage.removeItem(`cuenta_mesa_${mesa}`);
        localStorage.removeItem(`carrito_pedidos_mesa_${mesa}`);
        setCarrito((carritoActual) => {
          if (carritoActual.length === 0) {
            setMostrarResumen(false);
          }
          return carritoActual;
        });
      }
    } catch (err) {
      console.error('Error al cargar la cuenta de la mesa:', err);
    }
  }, [mesa]);

  // Cada vez que se abre la web app o cambia la mesa, limpiamos cualquier borrador viejo no confirmado
  // y cargamos la cuenta compartida de esa mesa desde el backend.
  useEffect(() => {
    setCarrito([]);
    localStorage.removeItem('carrito_pedidos');
    if (mesa) {
      localStorage.removeItem(`carrito_pedidos_mesa_${mesa}`);
      localStorage.removeItem(`cuenta_mesa_${mesa}`);
    }
    cargarCuentaMesa();
  }, [mesa, cargarCuentaMesa]);

  // Actualización periódica para mantener sincronizada la cuenta de la mesa entre dispositivos
  useEffect(() => {
    if (!mesa) return;

    const interval = setInterval(() => {
      cargarCuentaMesa();
    }, 3000);

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        cargarCuentaMesa();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [mesa, cargarCuentaMesa]);

  const abrirPersonalizacion = (prod: Producto) => {
    setProductoSeleccionado(prod);
    setCantidad(1);
    setComentarios('');
  };

  const agregarAlCarrito = () => {
    if (!productoSeleccionado) return;

    const precioUnitario = obtenerPrecio(productoSeleccionado);

    const nuevoItem: ItemCarrito = {
      id: productoSeleccionado.id,
      nombre: productoSeleccionado.nombre,
      categoria: String(productoSeleccionado.categoria ?? ''),
      precio: precioUnitario,
      cantidad,
      comentarios,
      subtotal: precioUnitario * cantidad,
    };

    setCarrito((prev) => [...prev, nuevoItem]);
    setProductoSeleccionado(null);
  };

  const eliminarDelCarrito = (index: number) => {
    setCarrito((prev) => prev.filter((_, i) => i !== index));
  };

  const subtotalCarritoActual = carrito.reduce((acc, item) => acc + item.subtotal, 0);
  const totalRondasConfirmadas = rondasConfirmadas.reduce((acc, ronda) => acc + ronda.subtotalRonda, 0);
  const totalGeneralCuenta = totalRondasConfirmadas + subtotalCarritoActual;
  const totalItemsEnCuenta =
    carrito.length + rondasConfirmadas.reduce((acc, ronda) => acc + ronda.items.length, 0);

  const validarMesaActiva = (): boolean => {
    if (!mesa) {
      alert('⚠️ Para poder ordenar, debes escanear el código QR impreso en tu mesa.');
      return false;
    }
    return true;
  };

  // 1. CONFIRMAR PEDIDO (envía a cocina, registra en cuenta compartida de la mesa y muestra pantallita)
  const confirmarPedido = async () => {
    if (!validarMesaActiva()) return;
    if (carrito.length === 0 || enviandoCocina) return;

    setEnviandoCocina(true);

    try {
      let numeroRonda = rondasConfirmadas.length + 1;
      try {
        const cuentaRes = await fetch(
          `${API_BASE}/api/v1/cocina/cuentas/${encodeURIComponent(String(mesa))}?t=${Date.now()}`,
          { cache: 'no-store' }
        );
        if (cuentaRes.ok) {
          const cuentaData = await cuentaRes.json();
          if (typeof cuentaData.siguiente_numero_ronda === 'number') {
            numeroRonda = cuentaData.siguiente_numero_ronda;
          }
        }
      } catch {
        // Si falla la consulta previa, usamos el conteo actual como respaldo
      }

      const resCocina = await fetch(`${API_BASE}/api/v1/cocina/comandas`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mesa: String(mesa),
          numero_ronda: numeroRonda,
          items: carrito.map((item) => ({
            producto_id: String(item.id),
            nombre: item.nombre,
            cantidad: item.cantidad,
            categoria: item.categoria,
            notas: item.comentarios || null,
          })),
        }),
      });

      if (!resCocina.ok) {
        throw new Error(`Error al enviar comanda (${resCocina.status})`);
      }

      const resCuenta = await fetch(
        `${API_BASE}/api/v1/cocina/cuentas/${encodeURIComponent(String(mesa))}/rondas`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            items: carrito.map((item) => ({
              producto_id: String(item.id),
              nombre: item.nombre,
              categoria: item.categoria,
              precio: item.precio,
              cantidad: item.cantidad,
              comentarios: item.comentarios,
              subtotal: item.subtotal,
            })),
            subtotal_ronda: subtotalCarritoActual,
          }),
        }
      );

      if (!resCuenta.ok) {
        throw new Error(`Error al registrar ronda en cuenta (${resCuenta.status})`);
      }

      const cuentaActualizada = await resCuenta.json();
      if (Array.isArray(cuentaActualizada.rondas)) {
        setRondasConfirmadas(cuentaActualizada.rondas);
      } else {
        setRondasConfirmadas((prev) => [
          ...prev,
          {
            numeroRonda,
            items: carrito,
            subtotalRonda: subtotalCarritoActual,
          },
        ]);
      }

      setCarrito([]);
      localStorage.removeItem('carrito_pedidos');
      setMostrarConfirmacionEnvio(true);
    } catch (err) {
      console.error(err);
      alert('⚠️ No se pudo enviar la ronda a cocina. Intenta de nuevo.');
    } finally {
      setEnviandoCocina(false);
    }
  };

  // 2. FINALIZAR CUENTA (resumen completo + método de pago + WhatsApp + limpia cuenta compartida)
  const finalizarCuenta = async () => {
    if (!validarMesaActiva() || finalizandoCuenta) return;

    const rondasParaResumen: RondaPedido[] =
      carrito.length > 0
        ? [
            ...rondasConfirmadas,
            {
              numeroRonda: rondasConfirmadas.length + 1,
              items: carrito,
              subtotalRonda: subtotalCarritoActual,
            },
          ]
        : rondasConfirmadas;

    if (rondasParaResumen.length === 0) return;

    setFinalizandoCuenta(true);

    try {
      let mensaje = `🧾 *FINALIZAR CUENTA - MESA ${mesa}* 🧾\n\n`;

      rondasParaResumen.forEach((ronda) => {
        mensaje += `*Ronda #${ronda.numeroRonda}:*\n`;
        ronda.items.forEach((item, idx) => {
          mensaje += `  ${idx + 1}. *${item.cantidad}x* ${item.nombre} ($${item.subtotal.toFixed(2)})\n`;
          if (item.comentarios) {
            mensaje += `     _Nota: ${item.comentarios}_\n`;
          }
        });
        mensaje += `  _Subtotal ronda: $${ronda.subtotalRonda.toFixed(2)}_\n\n`;
      });

      mensaje += `💳 *Método de pago:* ${metodoPago}\n`;
      mensaje += `*TOTAL GENERAL DE LA CUENTA: $${totalGeneralCuenta.toFixed(2)}*`;

      const urlWhatsapp = `https://wa.me/${TELEFONO_RESTAURANTE}?text=${encodeURIComponent(mensaje)}`;
      window.open(urlWhatsapp, '_blank');

      await fetch(`${API_BASE}/api/v1/cocina/cuentas/${encodeURIComponent(String(mesa))}`, {
        method: 'DELETE',
      });

      setCarrito([]);
      setRondasConfirmadas([]);
      localStorage.removeItem('carrito_pedidos');
      if (mesa) {
        localStorage.removeItem(`cuenta_mesa_${mesa}`);
        localStorage.removeItem(`carrito_pedidos_mesa_${mesa}`);
      }
      setMostrarResumen(false);
      setMostrarCatalogo(false);
      await cargarCuentaMesa();
    } catch (err) {
      console.error(err);
      alert('⚠️ Hubo un problema al cerrar la cuenta en el servidor. Intenta de nuevo.');
    } finally {
      setFinalizandoCuenta(false);
    }
  };

  return (
    <>
      {/* BOTÓN EN LA CABECERA */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => {
            if (!validarMesaActiva()) return;
            cargarCuentaMesa();
            setMostrarCatalogo(true);
          }}
          className="bg-green-600 hover:bg-green-500 text-white text-xs font-bold px-3 py-1.5 rounded-full transition-transform active:scale-95 flex items-center gap-1.5 shadow-lg"
        >
          🛒 Ordenar ya {totalItemsEnCuenta > 0 && `(${totalItemsEnCuenta})`}
        </button>
      </div>

      {/* MODAL 1: CATÁLOGO DE PRODUCTOS DISPONIBLES */}
      {mostrarCatalogo && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex justify-center items-center p-4">
          <div className="bg-neutral-900 border border-neutral-800 w-full max-w-md rounded-2xl p-5 max-h-[85vh] flex flex-col relative shadow-2xl">
            <div className="flex justify-between items-center mb-3 pb-2 border-b border-neutral-800">
              <div>
                <h2 className="text-lg font-bold text-yellow-400">Selecciona tus platillos</h2>
                {rondasConfirmadas.length > 0 && (
                  <p className="text-[11px] text-neutral-400">
                    Cuenta abierta: ${totalRondasConfirmadas.toFixed(2)} ({rondasConfirmadas.length}{' '}
                    {rondasConfirmadas.length === 1 ? 'ronda' : 'rondas'})
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => setMostrarCatalogo(false)}
                className="text-neutral-400 hover:text-white text-xl font-bold p-1"
              >
                ✕
              </button>
            </div>

            <div className="space-y-2.5 overflow-y-auto pr-1 flex-1 mb-4">
              {productosDisponibles && productosDisponibles.length > 0 ? (
                productosDisponibles.map((prod: Producto) => {
                  const precioProd = obtenerPrecio(prod);
                  return (
                    <div
                      key={prod.id}
                      onClick={() => abrirPersonalizacion(prod)}
                      className="bg-neutral-800/60 hover:bg-neutral-800 border border-neutral-700/50 p-3 rounded-xl cursor-pointer flex justify-between items-center transition-colors"
                    >
                      <div>
                        <p className="font-semibold text-white text-sm">{prod.nombre}</p>
                        <p className="text-xs text-yellow-400 font-bold mt-0.5">
                          ${precioProd.toFixed(2)}
                        </p>
                      </div>
                      <span className="text-xs bg-yellow-500 hover:bg-yellow-400 text-neutral-950 font-bold px-2.5 py-1 rounded-lg">
                        + Agregar
                      </span>
                    </div>
                  );
                })
              ) : (
                <p className="text-neutral-400 text-center py-6 text-sm">
                  No hay productos disponibles por el momento.
                </p>
              )}
            </div>

            {/* ACCIONES DENTRO DEL MENÚ DE ORDENAR */}
            {(carrito.length > 0 || rondasConfirmadas.length > 0) && (
              <div className="space-y-2 pt-2 border-t border-neutral-800">
                {carrito.length > 0 && (
                  <button
                    type="button"
                    onClick={confirmarPedido}
                    disabled={enviandoCocina}
                    className="w-full bg-yellow-500 hover:bg-yellow-400 disabled:opacity-60 text-neutral-950 font-bold py-2.5 rounded-xl text-xs transition-colors shadow-lg flex justify-between px-4 items-center"
                  >
                    <span>
                      {enviandoCocina
                        ? 'Enviando a cocina...'
                        : `Confirmar pedido ($${subtotalCarritoActual.toFixed(2)})`}
                    </span>
                    <span className="bg-black/15 px-2 py-0.5 rounded-full text-[11px]">
                      {carrito.length} {carrito.length === 1 ? 'item' : 'items'}
                    </span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => {
                    cargarCuentaMesa();
                    setMostrarCatalogo(false);
                    setMostrarResumen(true);
                  }}
                  className="w-full bg-green-600 hover:bg-green-500 text-white font-bold py-2.5 rounded-xl text-xs transition-colors shadow-lg flex justify-between px-4 items-center"
                >
                  <span>Ver cuenta / Finalizar cuenta</span>
                  <span className="bg-white/20 px-2 py-0.5 rounded-full text-xs">
                    ${totalGeneralCuenta.toFixed(2)}
                  </span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* MODAL 2: DETALLE, CANTIDAD Y COMENTARIOS */}
      {productoSeleccionado && (
        <div className="fixed inset-0 bg-black/90 backdrop-blur-sm z-[60] flex justify-center items-center p-4">
          <div className="bg-neutral-900 border border-neutral-800 w-full max-w-md rounded-2xl p-5 relative shadow-2xl">
            <button
              type="button"
              onClick={() => setProductoSeleccionado(null)}
              className="absolute top-4 right-4 text-neutral-400 hover:text-white text-xl font-bold"
            >
              ✕
            </button>

            <h3 className="text-base font-bold text-white mb-1">{productoSeleccionado.nombre}</h3>
            <p className="text-xs text-yellow-400 font-semibold mb-4">
              Precio unitario: ${obtenerPrecio(productoSeleccionado).toFixed(2)}
            </p>

            {/* Ajustar Cantidad */}
            <div className="flex items-center justify-between mb-4 bg-neutral-800 p-3 rounded-xl border border-neutral-700/50">
              <span className="text-sm font-medium text-gray-200">Cantidad:</span>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setCantidad(Math.max(1, cantidad - 1))}
                  className="w-8 h-8 bg-neutral-700 rounded-lg font-bold text-white hover:bg-neutral-600 text-base"
                >
                  -
                </button>
                <span className="font-bold text-white text-base">{cantidad}</span>
                <button
                  type="button"
                  onClick={() => setCantidad(cantidad + 1)}
                  className="w-8 h-8 bg-neutral-700 rounded-lg font-bold text-white hover:bg-neutral-600 text-base"
                >
                  +
                </button>
              </div>
            </div>

            {/* Comentarios / Notas especiales */}
            <div className="mb-5">
              <label className="block text-xs font-medium text-gray-300 mb-1.5">
                Notas especiales (ej. sin cebolla, aderezo extra...):
              </label>
              <textarea
                value={comentarios}
                onChange={(e) => setComentarios(e.target.value)}
                placeholder="Escribe aquí tus especificaciones..."
                className="w-full bg-neutral-800 border border-neutral-700 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-yellow-500 resize-none h-20"
              />
            </div>

            {/* Botón Confirmar */}
            <button
              type="button"
              onClick={agregarAlCarrito}
              className="w-full bg-yellow-500 hover:bg-yellow-400 text-neutral-950 font-bold py-2.5 rounded-xl text-sm transition-colors shadow-lg"
            >
              Añadir a la orden (${(obtenerPrecio(productoSeleccionado) * cantidad).toFixed(2)})
            </button>
          </div>
        </div>
      )}

      {/* MODAL 3: RESUMEN COMPLETO Y FINALIZAR CUENTA */}
      {mostrarResumen && (
        <div className="fixed inset-0 bg-black/90 backdrop-blur-sm z-[70] flex justify-center items-center p-4">
          <div className="bg-neutral-900 border border-neutral-800 w-full max-w-md rounded-2xl p-5 max-h-[85vh] flex flex-col relative shadow-2xl">
            <div className="flex justify-between items-center mb-3 pb-2 border-b border-neutral-800">
              <h2 className="text-lg font-bold text-yellow-400">Cuenta de la Mesa {mesa}</h2>
              <button
                type="button"
                onClick={() => setMostrarResumen(false)}
                className="text-neutral-400 hover:text-white text-xl font-bold p-1"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 overflow-y-auto pr-1 flex-1 mb-3">
              {/* Rondas ya confirmadas */}
              {rondasConfirmadas.map((ronda) => (
                <div
                  key={ronda.numeroRonda}
                  className="bg-neutral-800/40 p-3 rounded-xl border border-neutral-700/40 space-y-2"
                >
                  <div className="flex justify-between items-center">
                    <span className="text-xs font-bold text-green-400">
                      ✓ Ronda #{ronda.numeroRonda} confirmada
                    </span>
                    <span className="text-xs font-bold text-neutral-300">
                      ${ronda.subtotalRonda.toFixed(2)}
                    </span>
                  </div>
                  {ronda.items.map((item, idx) => (
                    <div key={idx} className="text-xs text-neutral-200 flex justify-between">
                      <span>
                        {item.cantidad}x {item.nombre}
                        {item.comentarios ? ` (${item.comentarios})` : ''}
                      </span>
                      <span className="text-neutral-400">${item.subtotal.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              ))}

              {/* Ítems actuales aún sin confirmar */}
              {carrito.map((item, index) => (
                <div
                  key={index}
                  className="bg-neutral-800/80 p-3 rounded-xl border border-yellow-500/30 flex justify-between items-start"
                >
                  <div>
                    <span className="text-[10px] uppercase font-bold text-yellow-400 block mb-0.5">
                      Por confirmar
                    </span>
                    <p className="font-bold text-white text-sm">
                      {item.cantidad}x {item.nombre}
                    </p>
                    {item.comentarios && (
                      <p className="text-xs text-neutral-400 italic mt-0.5">Nota: {item.comentarios}</p>
                    )}
                    <p className="text-xs text-yellow-400 font-bold mt-1">${item.subtotal.toFixed(2)}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => eliminarDelCarrito(index)}
                    className="text-red-400 hover:text-red-300 text-xs font-bold px-2 py-1 bg-red-500/10 rounded-lg"
                  >
                    Quitar
                  </button>
                </div>
              ))}
            </div>

            {/* SECCIÓN DE MÉTODO DE PAGO PARA FINALIZAR CUENTA */}
            <div className="bg-neutral-800/50 border border-neutral-700/50 p-3 rounded-xl mb-3">
              <label className="block text-xs font-bold text-gray-300 mb-2">
                💳 Método de pago para finalizar cuenta:
              </label>
              <div className="grid grid-cols-2 gap-2">
                {['Efectivo', 'Tarjeta (Terminal)'].map((metodo) => (
                  <button
                    key={metodo}
                    type="button"
                    onClick={() => setMetodoPago(metodo)}
                    className={`py-2 px-1 text-xs font-bold rounded-lg border transition-all ${
                      metodoPago === metodo
                        ? 'bg-yellow-500 text-neutral-950 border-yellow-400 shadow-md'
                        : 'bg-neutral-800 text-neutral-400 border-neutral-700 hover:border-neutral-600'
                    }`}
                  >
                    {metodo}
                  </button>
                ))}
              </div>
            </div>

            <div className="border-t border-neutral-800 pt-3 mb-4">
              <div className="flex justify-between text-white font-bold text-base">
                <span>Total acumulado:</span>
                <span className="text-yellow-400">${totalGeneralCuenta.toFixed(2)}</span>
              </div>
              <p className="text-[11px] text-neutral-400 mt-0.5">
                Pago seleccionado: <span className="text-white font-semibold">{metodoPago}</span>
              </p>
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setMostrarResumen(false);
                  setMostrarCatalogo(true);
                }}
                className="w-1/2 bg-neutral-800 hover:bg-neutral-700 text-white font-bold py-2.5 rounded-xl text-xs transition-colors"
              >
                Seguir pidiendo
              </button>
              <button
                type="button"
                onClick={finalizarCuenta}
                disabled={finalizandoCuenta}
                className="w-1/2 bg-green-600 hover:bg-green-500 disabled:opacity-60 text-white font-bold py-2.5 rounded-xl text-xs transition-colors shadow-lg"
              >
                {finalizandoCuenta ? 'Finalizando...' : 'Finalizar cuenta 🧾'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 4: PANTALLITA DE CONFIRMACIÓN DE ENVÍO */}
      {mostrarConfirmacionEnvio && (
        <div className="fixed inset-0 bg-black/85 backdrop-blur-sm z-[80] flex justify-center items-center p-4">
          <div className="bg-neutral-900 border border-green-500/40 w-full max-w-sm rounded-2xl p-6 text-center shadow-2xl">
            <div className="w-12 h-12 rounded-full bg-green-500/20 text-green-400 flex items-center justify-center text-2xl mx-auto mb-3">
              ✓
            </div>
            <h3 className="text-base font-bold text-white mb-1">¡Listo!</h3>
            <p className="text-sm text-neutral-200 mb-5">
              Tu pedido ha sido confirmado y enviado correctamente!
            </p>
            <button
              type="button"
              onClick={() => setMostrarConfirmacionEnvio(false)}
              className="w-full bg-green-600 hover:bg-green-500 text-white font-bold py-2.5 rounded-xl text-xs transition-colors"
            >
              Aceptar
            </button>
          </div>
        </div>
      )}
    </>
  );
}

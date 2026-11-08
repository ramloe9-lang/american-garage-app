import React, { useState, useEffect } from 'react';
import { useMesa } from '../hooks/useMesa';

interface Producto {
  id: string | number;
  nombre: string;
  precio_final?: number;
  precio_original?: number;
  [key: string]: any;
}

interface BotonOrdenarHeaderProps {
  productosDisponibles?: Producto[];
}

export function BotonOrdenarHeader({ productosDisponibles = [] }: BotonOrdenarHeaderProps) {
  const mesa = useMesa();
  const [mostrarCatalogo, setMostrarCatalogo] = useState(false);
  const [productoSeleccionado, setProductoSeleccionado] = useState<Producto | null>(null);
  
  // Estado para el modal de personalización
  const [cantidad, setCantidad] = useState<number>(1);
  const [comentarios, setComentarios] = useState<string>('');
  
  // Carrito de compras persistente en el celular del cliente
  const [carrito, setCarrito] = useState<any[]>(() => {
    const saved = localStorage.getItem('carrito_pedidos');
    return saved ? JSON.parse(saved) : [];
  });

  useEffect(() => {
    localStorage.setItem('carrito_pedidos', JSON.stringify(carrito));
  }, [carrito]);

  const abrirPersonalizacion = (prod: Producto) => {
    setProductoSeleccionado(prod);
    setCantidad(1);
    setComentarios('');
  };

  const agregarAlCarrito = () => {
    if (!productoSeleccionado) return;

    const precioUnitario = productoSeleccionado.precio_final ?? productoSeleccionado.precio_original ?? 0;

    const nuevoItem = {
      id: productoSeleccionado.id,
      nombre: productoSeleccionado.nombre,
      precio: precioUnitario,
      cantidad,
      comentarios,
      subtotal: precioUnitario * cantidad
    };

    setCarrito([...carrito, nuevoItem]);
    setProductoSeleccionado(null);
    setMostrarCatalogo(false);
    alert(`¡Agregado! ${cantidad}x ${nuevoItem.nombre} a tu orden (Mesa ${mesa}).`);
  };

  return (
    <>
      {/* BOTÓN EN LA CABECERA */}
      <div className="flex items-center gap-2">
        {mesa && (
          <span className="text-xs bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 font-bold px-2.5 py-1 rounded-full">
            Mesa {mesa}
          </span>
        )}

        <button 
          onClick={() => {
            if (!mesa) {
              alert("Para hacer un pedido en autoservicio, debes escanear el código QR impreso en tu mesa.");
              return;
            }
            setMostrarCatalogo(true);
          }}
          className={`${
            mesa 
              ? 'bg-green-600 hover:bg-green-500 text-white shadow-lg' 
              : 'bg-neutral-700 text-neutral-400 cursor-not-allowed'
          } text-xs font-bold px-3 py-1.5 rounded-full transition-transform active:scale-95 flex items-center gap-1.5`}
        >
          🛒 Ordenar ya
        </button>
      </div>

      {/* MODAL 1: CATÁLOGO DE PRODUCTOS DISPONIBLES */}
      {mostrarCatalogo && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex justify-center items-center p-4">
          <div className="bg-neutral-900 border border-neutral-800 w-full max-w-md rounded-2xl p-5 max-h-[85vh] flex flex-col relative shadow-2xl">
            <div className="flex justify-between items-center mb-3 pb-2 border-b border-neutral-800">
              <h2 className="text-lg font-bold text-yellow-400">Selecciona para tu orden</h2>
              <button 
                onClick={() => setMostrarCatalogo(false)}
                className="text-neutral-400 hover:text-white text-xl font-bold p-1"
              >
                ✕
              </button>
            </div>
            
            <div className="space-y-2.5 overflow-y-auto pr-1 flex-1">
              {productosDisponibles && productosDisponibles.length > 0 ? (
                productosDisponibles.map((prod: Producto) => (
                  <div 
                    key={prod.id}
                    onClick={() => abrirPersonalizacion(prod)}
                    className="bg-neutral-800/60 hover:bg-neutral-800 border border-neutral-700/50 p-3 rounded-xl cursor-pointer flex justify-between items-center transition-colors"
                  >
                    <div>
                      <p className="font-semibold text-white text-sm">{prod.nombre}</p>
                      <p className="text-xs text-yellow-400 font-bold mt-0.5">
                        ${prod.precio_final ?? prod.precio_original ?? 0}
                      </p>
                    </div>
                    <span className="text-xs bg-yellow-500 hover:bg-yellow-400 text-neutral-950 font-bold px-2.5 py-1 rounded-lg">
                      + Pedir
                    </span>
                  </div>
                ))
              ) : (
                <p className="text-neutral-400 text-center py-6 text-sm">No hay productos disponibles por el momento.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: DETALLE, CANTIDAD Y COMENTARIOS */}
      {productoSeleccionado && (
        <div className="fixed inset-0 bg-black/90 backdrop-blur-sm z-[60] flex justify-center items-center p-4">
          <div className="bg-neutral-900 border border-neutral-800 w-full max-w-md rounded-2xl p-5 relative shadow-2xl">
            <button 
              onClick={() => setProductoSeleccionado(null)}
              className="absolute top-4 right-4 text-neutral-400 hover:text-white text-xl font-bold"
            >
              ✕
            </button>

            <h3 className="text-base font-bold text-white mb-1">{productoSeleccionado.nombre}</h3>
            <p className="text-xs text-yellow-400 font-semibold mb-4">
              Precio unitario: ${productoSeleccionado.precio_final ?? productoSeleccionado.precio_original ?? 0}
            </p>

            {/* Ajustar Cantidad */}
            <div className="flex items-center justify-between mb-4 bg-neutral-800 p-3 rounded-xl border border-neutral-700/50">
              <span className="text-sm font-medium text-gray-200">Cantidad:</span>
              <div className="flex items-center gap-3">
                <button 
                  onClick={() => setCantidad(Math.max(1, cantidad - 1))}
                  className="w-8 h-8 bg-neutral-700 rounded-lg font-bold text-white hover:bg-neutral-600 text-base"
                >-</button>
                <span className="font-bold text-white text-base">{cantidad}</span>
                <button 
                  onClick={() => setCantidad(cantidad + 1)}
                  className="w-8 h-8 bg-neutral-700 rounded-lg font-bold text-white hover:bg-neutral-600 text-base"
                >+</button>
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
              onClick={agregarAlCarrito}
              className="w-full bg-yellow-500 hover:bg-yellow-400 text-neutral-950 font-bold py-2.5 rounded-xl text-sm transition-colors shadow-lg"
            >
              Agregar a la orden (${(productoSeleccionado.precio_final ?? productoSeleccionado.precio_original ?? 0) * cantidad})
            </button>
          </div>
        </div>
      )}
    </>
  );
}

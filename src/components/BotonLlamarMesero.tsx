import React, { useState, useEffect } from 'react';
import { useMesa } from '../hooks/useMesa';

export function BotonLlamarMesero() {
  const mesa = useMesa();
  const [cooldown, setCooldown] = useState<number>(0);

  // Efecto para manejar la cuenta regresiva del cooldown
  useEffect(() => {
    let timer: any; // <-- Cambiado de NodeJS.Timeout a 'any' para evitar el error en el navegador
    if (cooldown > 0) {
      timer = setInterval(() => {
        setCooldown((prev) => prev - 1);
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [cooldown]);

  const llamarMesero = () => {
    if (!mesa) {
      alert("Debes escanear el código QR de tu mesa para poder llamar al mesero.");
      return;
    }

    if (cooldown > 0) {
      alert(`Por favor espera ${cooldown} segundos antes de volver a llamar al mesero.`);
      return;
    }

    // Mensaje preconfigurado para WhatsApp
    const mensaje = `🔔 *LLAMADA DE ASISTENCIA - MESA ${mesa}* 🔔\n\nEl cliente de la Mesa ${mesa} solicita la presencia de un mesero en la mesa. ¡Por favor atender!`;

    // ⚠️ REEMPLAZA ESTE NÚMERO con el teléfono real del restaurante o del mesero encargado
    const telefonoRestaurante = "524425568390"; 

    const urlWhatsapp = `https://wa.me/${telefonoRestaurante}?text=${encodeURIComponent(mensaje)}`;
    window.open(urlWhatsapp, '_blank');

    // Activamos un cooldown de 60 segundos para evitar spam
    setCooldown(60);
  };

  return (
    <button
      onClick={llamarMesero}
      disabled={cooldown > 0}
      className={`${
        !mesa
          ? 'bg-neutral-800 text-neutral-500 cursor-not-allowed border border-neutral-700/50'
          : cooldown > 0
          ? 'bg-amber-600/50 text-white cursor-not-allowed border border-amber-500/30'
          : 'bg-amber-600 hover:bg-amber-500 text-white shadow-lg border border-amber-500/40'
      } text-xs font-bold px-3 py-1.5 rounded-full transition-transform active:scale-95 flex items-center gap-1.5`}
    >
      {cooldown > 0 ? `⏳ Espera ${cooldown}s` : '🔔 Llamar mesero'}
    </button>
  );
}

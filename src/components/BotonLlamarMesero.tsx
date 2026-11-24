import React, { useState, useEffect } from 'react';
import { useMesa } from '../hooks/useMesa';

const API_BASE =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL ||
  'https://american-garage-app.onrender.com';

export function BotonLlamarMesero() {
  const mesa = useMesa();
  const [cooldown, setCooldown] = useState<number>(0);
  const [enviando, setEnviando] = useState<boolean>(false);

  // Efecto para manejar la cuenta regresiva del cooldown
  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;
    if (cooldown > 0) {
      timer = setInterval(() => {
        setCooldown((prev) => Math.max(0, prev - 1));
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [cooldown]);

  const llamarMesero = async () => {
    if (!mesa) {
      alert('Debes escanear el código QR de tu mesa para poder llamar al mesero.');
      return;
    }

    if (cooldown > 0 || enviando) {
      if (cooldown > 0) {
        alert(`Por favor espera ${cooldown} segundos antes de volver a llamar al mesero.`);
      }
      return;
    }

    setEnviando(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/cocina/llamar-mesero`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mesa: String(mesa),
          motivo: `El cliente de la Mesa ${mesa} solicita atención en mesa.`,
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      setCooldown(60);
      alert(`🔔 ¡Listo! Se envió la alerta de la Mesa ${mesa} a Estatus mesas.`);
    } catch (err) {
      console.error('Error al llamar al mesero:', err);
      alert('⚠️ No se pudo enviar el llamado al mesero. Intenta de nuevo.');
    } finally {
      setEnviando(false);
    }
  };

  return (
    <button
      type="button"
      onClick={llamarMesero}
      disabled={!mesa || cooldown > 0 || enviando}
      className={`${
        !mesa
          ? 'bg-neutral-800 text-neutral-500 cursor-not-allowed border border-neutral-700/50'
          : cooldown > 0 || enviando
          ? 'bg-amber-600/50 text-white cursor-not-allowed border border-amber-500/30'
          : 'bg-amber-600 hover:bg-amber-500 text-white shadow-lg border border-amber-500/40'
      } text-xs font-bold px-3 py-1.5 rounded-full transition-transform active:scale-95 flex items-center gap-1.5`}
    >
      {enviando
        ? '🔔 Enviando...'
        : cooldown > 0
        ? `⏳ Espera ${cooldown}s`
        : '🔔 Llamar mesero'}
    </button>
  );
}

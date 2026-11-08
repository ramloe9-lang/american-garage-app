import { useEffect, useState } from 'react';

export function useMesa(): string | null {
  const [mesa, setMesa] = useState<string | null>(null);

  useEffect(() => {
    // 1. Revisar si viene la mesa en la URL (?mesa=4)
    const params = new URLSearchParams(window.location.search);
    const mesaUrl = params.get('mesa');

    if (mesaUrl && /^[A-Za-z0-9]{1,3}$/.test(mesaUrl)) {
      const mesaUpper = mesaUrl.toUpperCase();
      localStorage.setItem('mesa_actual', mesaUpper);
      setMesa(mesaUpper);
    } else {
      // 2. Si NO viene en la URL, limpiamos cualquier rastro anterior 
      // para obligar a que se escanee el QR real de la mesa.
      localStorage.removeItem('mesa_actual');
      setMesa(null);
    }
  }, []);

  return mesa;
}

import { useEffect, useState } from 'react';

export function useMesa(): string | null {
  const [mesa, setMesa] = useState<string | null>(null);

  useEffect(() => {
    // 1. Revisar si viene la mesa en la URL (?mesa=4)
    const params = new URLSearchParams(window.location.search);
    const mesaUrl = params.get('mesa');

    if (mesaUrl) {
      localStorage.setItem('mesa_actual', mesaUrl);
      setMesa(mesaUrl);
    } else {
      // 2. Si no viene en la URL, revisar si ya estaba guardada en el celular
      const mesaGuardada = localStorage.getItem('mesa_actual');
      if (mesaGuardada) setMesa(mesaGuardada);
    }
  }, []);

  return mesa;
}

import { useQuery } from '@tanstack/react-query'
import { fetchMenu } from '../lib/api'

/** Carga el menú y lo refresca solo cada 5 min (igual que la caché del backend). */
export function useMenu() {
  return useQuery({
    queryKey: ['menu'],
    queryFn: ({ signal }) => fetchMenu(signal),
    refetchInterval: 5 * 60_000,
    staleTime: 60_000,
    retry: 2,
  })
}

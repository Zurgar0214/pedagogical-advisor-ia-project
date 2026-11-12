import { createContext, useContext } from 'react'
import type { Usuario } from '../api/cliente'

export interface ValorAuth {
  usuario: Usuario | null
  cargando: boolean
  iniciarSesion: (correo: string, contrasena: string) => Promise<Usuario>
  cerrarSesion: () => void
}

export const ContextoAuth = createContext<ValorAuth | null>(null)

export function useAuth(): ValorAuth {
  const valor = useContext(ContextoAuth)
  if (!valor) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return valor
}

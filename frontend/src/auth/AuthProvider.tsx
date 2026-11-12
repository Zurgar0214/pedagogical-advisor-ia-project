import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, obtenerYo, registrarSesionExpirada, type Usuario } from '../api/cliente'
import { ContextoAuth, type ValorAuth } from './contexto'
import { borrarToken, guardarToken, leerToken } from './token'

export default function AuthProvider({ children }: { children: ReactNode }) {
  const navegar = useNavigate()
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [cargando, setCargando] = useState<boolean>(() => leerToken() !== null)

  const cerrarSesion = useCallback(() => {
    borrarToken()
    setUsuario(null)
  }, [])

  useEffect(() => {
    registrarSesionExpirada(() => {
      setUsuario(null)
      navegar('/login', { replace: true })
    })
    return () => registrarSesionExpirada(null)
  }, [navegar])

  useEffect(() => {
    if (leerToken() === null) return
    let activo = true
    obtenerYo()
      .then((u) => {
        if (activo) setUsuario(u)
      })
      .catch(() => {
        if (activo) cerrarSesion()
      })
      .finally(() => {
        if (activo) setCargando(false)
      })
    return () => {
      activo = false
    }
  }, [cerrarSesion])

  const iniciarSesion = useCallback(async (correo: string, contrasena: string) => {
    const r = await login(correo, contrasena)
    guardarToken(r.access_token)
    setUsuario(r.usuario)
    return r.usuario
  }, [])

  const valor = useMemo<ValorAuth>(
    () => ({ usuario, cargando, iniciarSesion, cerrarSesion }),
    [usuario, cargando, iniciarSesion, cerrarSesion],
  )
  return <ContextoAuth.Provider value={valor}>{children}</ContextoAuth.Provider>
}

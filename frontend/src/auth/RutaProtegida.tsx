import type { ReactNode } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import type { Rol } from '../api/cliente'
import { useAuth } from './contexto'

interface Props {
  /** Roles permitidos; si se omite, basta con estar autenticado. */
  roles?: Rol[]
  children: ReactNode
}

export default function RutaProtegida({ roles, children }: Props) {
  const { usuario, cargando } = useAuth()
  const ubicacion = useLocation()

  if (cargando) {
    return (
      <p role="status" className="mx-auto max-w-6xl px-4 py-10 text-slate-600">
        Verificando sesión…
      </p>
    )
  }
  if (!usuario) {
    return <Navigate to="/login" replace state={{ desde: ubicacion.pathname + ubicacion.search }} />
  }
  if (roles && !roles.includes(usuario.rol)) {
    return (
      <section className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="font-display text-[1.95rem] font-semibold leading-tight text-tinta">Acceso denegado</h1>
        <p className="mt-2 text-slate-700">Tu rol no tiene permiso para ver esta sección.</p>
        <Link to="/" className="mt-4 inline-block text-marca underline">
          Volver al inicio
        </Link>
      </section>
    )
  }
  return <>{children}</>
}

import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ErrorApi } from '../api/cliente'
import { useAuth } from '../auth/contexto'
import { botonPrim, campo } from '../componentes/estilos'

export default function Login() {
  const { usuario, cargando, iniciarSesion } = useAuth()
  const navegar = useNavigate()
  const ubicacion = useLocation()
  const desde = (ubicacion.state as { desde?: string } | null)?.desde ?? '/'

  const [correo, setCorreo] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  if (!cargando && usuario && !enviando) return <Navigate to={desde} replace />

  async function enviar(e: FormEvent) {
    e.preventDefault()
    const c = correo.trim()
    if (!c || !contrasena) {
      setError('Ingresa tu correo y tu contraseña.')
      return
    }
    if (!/^\S+@\S+\.\S+$/.test(c)) {
      setError('Ingresa un correo electrónico válido.')
      return
    }
    setError(null)
    setEnviando(true)
    try {
      await iniciarSesion(c, contrasena)
      navegar(desde, { replace: true })
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : 'No se pudo iniciar sesión.')
      setEnviando(false)
    }
  }

  return (
    <section className="mx-auto grid max-w-5xl gap-10 px-4 py-12 lg:grid-cols-[1fr_25rem] lg:items-center lg:gap-16 lg:px-10 lg:py-20">
      <div className="order-2 lg:order-1">
        <h1 className="font-display text-[2.2rem] font-semibold leading-tight text-tinta">Iniciar sesión</h1>
        <p className="mt-3 max-w-md text-lg leading-relaxed text-slate-700">
          Entra con la cuenta que te asignó el administrador para ver tu portafolio, revisar evaluaciones o consultar informes.
        </p>
        <ul className="mt-6 max-w-md space-y-2 text-sm text-slate-600">
          <li className="border-l-2 border-resaltador pl-3">Docentes: laboratorios, rúbricas y revisión de evaluaciones.</li>
          <li className="border-l-2 border-slate-300 pl-3">Estudiantes: entregas, notas publicadas, informe y mapa mental.</li>
        </ul>
      </div>
      <form onSubmit={enviar} noValidate className="order-1 space-y-5 rounded-lg border border-slate-200 bg-white p-6 sm:p-7 lg:order-2">
        {error && (
          <p role="alert" className="rounded-md border-l-4 border-red-600 bg-red-50 px-3.5 py-2.5 text-sm text-red-900">
            {error}
          </p>
        )}
        <div>
          <label htmlFor="correo" className="block text-sm font-medium text-slate-800">
            Correo electrónico
          </label>
          <input id="correo" type="email" autoComplete="username" required value={correo} onChange={(e) => setCorreo(e.target.value)} className={campo} />
        </div>
        <div>
          <label htmlFor="contrasena" className="block text-sm font-medium text-slate-800">
            Contraseña
          </label>
          <input id="contrasena" type="password" autoComplete="current-password" required value={contrasena} onChange={(e) => setContrasena(e.target.value)} className={campo} />
        </div>
        <button type="submit" disabled={enviando} className={`w-full ${botonPrim}`}>
          {enviando ? 'Ingresando…' : 'Ingresar'}
        </button>
      </form>
    </section>
  )
}

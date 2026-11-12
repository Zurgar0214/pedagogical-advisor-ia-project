import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ErrorApi } from '../api/cliente'
import { useAuth } from '../auth/contexto'

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

  const campo =
    'mt-1 block w-full rounded border border-slate-400 bg-white px-3 py-2 text-slate-900 focus:outline-2 focus:outline-marca'

  return (
    <section className="mx-auto max-w-md px-4 py-10">
      <h1 className="font-serif text-2xl font-semibold text-tinta">Iniciar sesión</h1>
      <p className="mt-1 text-sm text-slate-600">Accede con tu cuenta institucional.</p>
      <form onSubmit={enviar} noValidate className="mt-6 space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        {error && (
          <p role="alert" className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
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
        <button
          type="submit"
          disabled={enviando}
          className="w-full rounded bg-marca px-4 py-2 font-medium text-white hover:bg-tinta focus:outline-2 focus:outline-offset-2 focus:outline-marca disabled:opacity-60"
        >
          {enviando ? 'Ingresando…' : 'Ingresar'}
        </button>
      </form>
    </section>
  )
}

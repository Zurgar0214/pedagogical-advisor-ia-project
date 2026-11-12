import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  actualizarUsuario,
  crearUsuario,
  ErrorApi,
  listarUsuarios,
  type CambiosUsuario,
  type Rol,
  type Usuario,
} from '../api/cliente'
import { useAuth } from '../auth/contexto'

const ROLES: { valor: Rol; texto: string }[] = [
  { valor: 'admin', texto: 'Administrador' },
  { valor: 'docente', texto: 'Docente' },
  { valor: 'estudiante', texto: 'Estudiante' },
]
const textoRol = (r: Rol) => ROLES.find((x) => x.valor === r)?.texto ?? r

const campo =
  'mt-1 block w-full rounded border border-slate-400 bg-white px-3 py-2 text-slate-900 focus:outline-2 focus:outline-marca'
const botonSec =
  'rounded border border-slate-400 bg-white px-2.5 py-1 text-sm text-slate-800 hover:bg-slate-100 focus:outline-2 focus:outline-marca disabled:opacity-50'

const mensajeError = (e: unknown) => (e instanceof ErrorApi ? e.message : 'Ocurrió un error inesperado.')

export default function Usuarios() {
  const { usuario: yo } = useAuth()
  const [filtro, setFiltro] = useState<Rol | ''>('')
  const [lista, setLista] = useState<Usuario[]>([])
  const [cargando, setCargando] = useState(true)
  const [errorLista, setErrorLista] = useState<string | null>(null)
  const [aviso, setAviso] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null)
  const [ocupado, setOcupado] = useState<number | null>(null)
  const [recarga, setRecarga] = useState(0)

  // formulario de creación
  const [nombre, setNombre] = useState('')
  const [correo, setCorreo] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [rol, setRol] = useState<Rol>('estudiante')
  const [errorForm, setErrorForm] = useState<string | null>(null)
  const [creando, setCreando] = useState(false)

  // restablecer contraseña
  const [objetivo, setObjetivo] = useState<Usuario | null>(null)
  const [nueva, setNueva] = useState('')
  const [errorClave, setErrorClave] = useState<string | null>(null)

  useEffect(() => {
    let activo = true
    listarUsuarios(filtro || undefined)
      .then((u) => {
        if (!activo) return
        setLista(u)
        setErrorLista(null)
      })
      .catch((e) => {
        if (activo) setErrorLista(mensajeError(e))
      })
      .finally(() => {
        if (activo) setCargando(false)
      })
    return () => {
      activo = false
    }
  }, [filtro, recarga])

  const recargar = useCallback(() => setRecarga((n) => n + 1), [])

  async function aplicar(u: Usuario, cambios: CambiosUsuario, exito: string) {
    setOcupado(u.id)
    setAviso(null)
    try {
      await actualizarUsuario(u.id, cambios)
      setAviso({ tipo: 'ok', texto: exito })
      recargar()
      return true
    } catch (e) {
      setAviso({ tipo: 'error', texto: mensajeError(e) })
      return false
    } finally {
      setOcupado(null)
    }
  }

  async function crear(e: FormEvent) {
    e.preventDefault()
    if (!nombre.trim() || !correo.trim()) return setErrorForm('Completa el nombre y el correo.')
    if (!/^\S+@\S+\.\S+$/.test(correo.trim())) return setErrorForm('Ingresa un correo electrónico válido.')
    if (contrasena.length < 8) return setErrorForm('La contraseña debe tener al menos 8 caracteres.')
    setErrorForm(null)
    setCreando(true)
    try {
      await crearUsuario({ nombre: nombre.trim(), correo: correo.trim(), contrasena, rol })
      setNombre('')
      setCorreo('')
      setContrasena('')
      setRol('estudiante')
      setAviso({ tipo: 'ok', texto: 'Usuario creado correctamente.' })
      recargar()
    } catch (err) {
      setErrorForm(mensajeError(err))
    } finally {
      setCreando(false)
    }
  }

  async function restablecer(e: FormEvent) {
    e.preventDefault()
    if (!objetivo) return
    if (nueva.length < 8) return setErrorClave('La contraseña debe tener al menos 8 caracteres.')
    setErrorClave(null)
    const ok = await aplicar(objetivo, { contrasena: nueva }, `Contraseña de ${objetivo.nombre} restablecida.`)
    if (ok) {
      setObjetivo(null)
      setNueva('')
    }
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="font-serif text-2xl font-semibold text-tinta">Gestión de usuarios</h1>
      <p className="mt-1 text-sm text-slate-600">Crea cuentas, asigna roles y controla el acceso a la plataforma.</p>

      <div aria-live="polite">
        {aviso && (
          <p
            role={aviso.tipo === 'error' ? 'alert' : 'status'}
            className={`mt-4 rounded border px-3 py-2 text-sm ${
              aviso.tipo === 'error' ? 'border-red-300 bg-red-50 text-red-800' : 'border-emerald-300 bg-emerald-50 text-emerald-900'
            }`}
          >
            {aviso.texto}
          </p>
        )}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div className="min-w-0 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 className="text-lg font-semibold text-tinta">Usuarios</h2>
            <div>
              <label htmlFor="filtro-rol" className="block text-sm font-medium text-slate-800">
                Filtrar por rol
              </label>
              <select
                id="filtro-rol"
                value={filtro}
                onChange={(e) => {
                  setCargando(true)
                  setFiltro(e.target.value as Rol | '')
                }}
                className="mt-1 rounded border border-slate-400 bg-white px-3 py-1.5 text-slate-900 focus:outline-2 focus:outline-marca"
              >
                <option value="">Todos</option>
                {ROLES.map((r) => (
                  <option key={r.valor} value={r.valor}>
                    {r.texto}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {errorLista && (
            <p role="alert" className="mt-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
              {errorLista}
            </p>
          )}
          {cargando ? (
            <p role="status" className="mt-4 text-slate-600">
              Cargando usuarios…
            </p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[40rem] text-left text-sm">
                <caption className="sr-only">Lista de usuarios</caption>
                <thead>
                  <tr className="border-b border-slate-300 text-slate-700">
                    <th scope="col" className="py-2 pr-3 font-semibold">Nombre</th>
                    <th scope="col" className="py-2 pr-3 font-semibold">Correo</th>
                    <th scope="col" className="py-2 pr-3 font-semibold">Rol</th>
                    <th scope="col" className="py-2 pr-3 font-semibold">Estado</th>
                    <th scope="col" className="py-2 font-semibold">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {lista.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-slate-600">
                        No hay usuarios para mostrar.
                      </td>
                    </tr>
                  )}
                  {lista.map((u) => {
                    const esYo = yo?.id === u.id
                    return (
                      <tr key={u.id} className="border-b border-slate-100 align-middle">
                        <td className="py-2 pr-3 font-medium text-slate-900">
                          {u.nombre}
                          {esYo && <span className="ml-1 text-xs text-slate-500">(tú)</span>}
                        </td>
                        <td className="py-2 pr-3 break-all">{u.correo}</td>
                        <td className="py-2 pr-3">
                          <label htmlFor={`rol-${u.id}`} className="sr-only">
                            Rol de {u.nombre}
                          </label>
                          <select
                            id={`rol-${u.id}`}
                            value={u.rol}
                            disabled={ocupado === u.id || esYo}
                            onChange={(e) => aplicar(u, { rol: e.target.value as Rol }, `Rol de ${u.nombre} actualizado a ${textoRol(e.target.value as Rol)}.`)}
                            className="rounded border border-slate-400 bg-white px-2 py-1 text-slate-900 focus:outline-2 focus:outline-marca disabled:bg-slate-100"
                          >
                            {ROLES.map((r) => (
                              <option key={r.valor} value={r.valor}>
                                {r.texto}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="py-2 pr-3">
                          <span
                            className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                              u.activo ? 'bg-emerald-100 text-emerald-900' : 'bg-slate-200 text-slate-800'
                            }`}
                          >
                            {u.activo ? 'Activo' : 'Inactivo'}
                          </span>
                        </td>
                        <td className="py-2">
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              className={botonSec}
                              disabled={ocupado === u.id || esYo}
                              onClick={() => aplicar(u, { activo: !u.activo }, `${u.nombre} ahora está ${u.activo ? 'inactivo' : 'activo'}.`)}
                              aria-label={`${u.activo ? 'Desactivar' : 'Activar'} a ${u.nombre}`}
                            >
                              {u.activo ? 'Desactivar' : 'Activar'}
                            </button>
                            <button
                              type="button"
                              className={botonSec}
                              onClick={() => {
                                setObjetivo(u)
                                setNueva('')
                                setErrorClave(null)
                              }}
                              aria-label={`Restablecer contraseña de ${u.nombre}`}
                            >
                              Restablecer contraseña
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {objetivo && (
            <form onSubmit={restablecer} noValidate className="mt-4 rounded border border-slate-300 bg-slate-50 p-4" aria-labelledby="titulo-clave">
              <h3 id="titulo-clave" className="font-semibold text-tinta">
                Restablecer contraseña de {objetivo.nombre}
              </h3>
              {errorClave && (
                <p role="alert" className="mt-2 text-sm text-red-800">
                  {errorClave}
                </p>
              )}
              <label htmlFor="nueva-clave" className="mt-2 block text-sm font-medium text-slate-800">
                Nueva contraseña (mínimo 8 caracteres)
              </label>
              <input id="nueva-clave" type="password" autoComplete="new-password" value={nueva} onChange={(e) => setNueva(e.target.value)} className={campo} />
              <div className="mt-3 flex gap-2">
                <button type="submit" disabled={ocupado === objetivo.id} className="rounded bg-marca px-3 py-1.5 text-sm font-medium text-white hover:bg-tinta focus:outline-2 focus:outline-offset-2 focus:outline-marca disabled:opacity-60">
                  Guardar contraseña
                </button>
                <button type="button" className={botonSec} onClick={() => setObjetivo(null)}>
                  Cancelar
                </button>
              </div>
            </form>
          )}
        </div>

        <form onSubmit={crear} noValidate className="h-fit space-y-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm" aria-labelledby="titulo-crear">
          <h2 id="titulo-crear" className="text-lg font-semibold text-tinta">
            Crear usuario
          </h2>
          {errorForm && (
            <p role="alert" className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
              {errorForm}
            </p>
          )}
          <div>
            <label htmlFor="nu-nombre" className="block text-sm font-medium text-slate-800">Nombre completo</label>
            <input id="nu-nombre" type="text" required value={nombre} onChange={(e) => setNombre(e.target.value)} className={campo} />
          </div>
          <div>
            <label htmlFor="nu-correo" className="block text-sm font-medium text-slate-800">Correo electrónico</label>
            <input id="nu-correo" type="email" required autoComplete="off" value={correo} onChange={(e) => setCorreo(e.target.value)} className={campo} />
          </div>
          <div>
            <label htmlFor="nu-clave" className="block text-sm font-medium text-slate-800">Contraseña (mínimo 8 caracteres)</label>
            <input id="nu-clave" type="password" required autoComplete="new-password" value={contrasena} onChange={(e) => setContrasena(e.target.value)} className={campo} />
          </div>
          <div>
            <label htmlFor="nu-rol" className="block text-sm font-medium text-slate-800">Rol</label>
            <select id="nu-rol" value={rol} onChange={(e) => setRol(e.target.value as Rol)} className={campo}>
              {ROLES.map((r) => (
                <option key={r.valor} value={r.valor}>
                  {r.texto}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" disabled={creando} className="w-full rounded bg-marca px-4 py-2 font-medium text-white hover:bg-tinta focus:outline-2 focus:outline-offset-2 focus:outline-marca disabled:opacity-60">
            {creando ? 'Creando…' : 'Crear usuario'}
          </button>
        </form>
      </div>
    </section>
  )
}

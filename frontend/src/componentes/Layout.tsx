import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import type { Rol } from '../api/cliente'
import { useAuth } from '../auth/contexto'
import EstadoApi from './EstadoApi'

const TODOS: Rol[] = ['admin', 'docente', 'estudiante']
const DOCENTES: Rol[] = ['admin', 'docente']
const ETIQUETA_ROL: Record<Rol, string> = { admin: 'Administrador', docente: 'Docente', estudiante: 'Estudiante' }

const enlaces: { to: string; texto: string; fin?: boolean; roles: Rol[] | null }[] = [
  { to: '/', texto: 'Proyecto', fin: true, roles: null },
  { to: '/portafolio', texto: 'Portafolio', roles: TODOS },
  { to: '/laboratorios', texto: 'Laboratorios', roles: DOCENTES },
  { to: '/revision', texto: 'Revisión docente', roles: DOCENTES },
  { to: '/informe', texto: 'Informe', roles: TODOS },
  { to: '/mapa-mental', texto: 'Mapa mental', roles: TODOS },
  { to: '/usuarios', texto: 'Usuarios', roles: ['admin'] },
]

export default function Layout() {
  const { usuario, cerrarSesion } = useAuth()
  const navegar = useNavigate()
  const visibles = enlaces.filter((e) => e.roles === null || (usuario !== null && e.roles.includes(usuario.rol)))

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#contenido" className="sr-only focus:not-sr-only focus:absolute focus:m-2 focus:bg-white focus:p-2">
        Saltar al contenido
      </a>
      <header className="bg-marca text-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="font-serif text-lg font-semibold leading-tight">Asesor Pedagógico Inteligente</p>
            <p className="text-xs text-blue-100">Universidad de Manizales · Proyecto Final IA</p>
          </div>
          <nav aria-label="Principal">
            <ul className="flex flex-wrap gap-1">
              {visibles.map((e) => (
                <li key={e.to}>
                  <NavLink
                    to={e.to}
                    end={e.fin}
                    className={({ isActive }) =>
                      `block rounded px-3 py-1.5 text-sm font-medium transition-colors focus:outline-2 focus:outline-white ${
                        isActive ? 'bg-white text-marca' : 'text-blue-50 hover:bg-white/15'
                      }`
                    }
                  >
                    {e.texto}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
          <div className="flex items-center gap-3 text-sm">
            {usuario ? (
              <>
                <p className="leading-tight">
                  <span className="block font-medium">{usuario.nombre}</span>
                  <span className="block text-xs text-blue-100">{ETIQUETA_ROL[usuario.rol]}</span>
                </p>
                <button
                  type="button"
                  onClick={() => {
                    cerrarSesion()
                    navegar('/login')
                  }}
                  className="rounded border border-white/60 px-3 py-1.5 font-medium hover:bg-white/15 focus:outline-2 focus:outline-white"
                >
                  Cerrar sesión
                </button>
              </>
            ) : (
              <NavLink
                to="/login"
                className="rounded border border-white/60 px-3 py-1.5 font-medium hover:bg-white/15 focus:outline-2 focus:outline-white"
              >
                Iniciar sesión
              </NavLink>
            )}
          </div>
        </div>
      </header>
      <main id="contenido" className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-slate-600">© 2026 Asesor Pedagógico Inteligente · Universidad de Manizales</p>
          <EstadoApi />
        </div>
      </footer>
    </div>
  )
}

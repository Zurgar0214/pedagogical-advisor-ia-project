import { useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import type { Rol } from '../api/cliente'
import { useAuth } from '../auth/contexto'
import EstadoApi from './EstadoApi'

const TODOS: Rol[] = ['admin', 'docente', 'estudiante']
const DOCENTES: Rol[] = ['admin', 'docente']
const ETIQUETA_ROL: Record<Rol, string> = { admin: 'Administrador', docente: 'Docente', estudiante: 'Estudiante' }

// Agrupados por lo que hace la persona: conocer el proyecto, trabajar con entregas, ver resultados, administrar.
const grupos: { titulo: string | null; enlaces: { to: string; texto: string; fin?: boolean; roles: Rol[] | null }[] }[] = [
  { titulo: null, enlaces: [{ to: '/', texto: 'Proyecto', fin: true, roles: null }] },
  {
    titulo: 'Evaluación',
    enlaces: [
      { to: '/portafolio', texto: 'Portafolio', roles: TODOS },
      { to: '/laboratorios', texto: 'Laboratorios y rúbricas', roles: DOCENTES },
      { to: '/revision', texto: 'Revisión docente', roles: DOCENTES },
    ],
  },
  {
    titulo: 'Resultados',
    enlaces: [
      { to: '/informe', texto: 'Informe integral', roles: TODOS },
      { to: '/mapa-mental', texto: 'Mapa mental', roles: TODOS },
    ],
  },
  { titulo: 'Administración', enlaces: [{ to: '/usuarios', texto: 'Usuarios', roles: ['admin'] }] },
]

function iniciales(nombre: string) {
  return nombre
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('')
}

function Marca() {
  return (
    <NavLink to="/" className="group flex items-center gap-3 rounded-lg">
      {/* Monograma: una casilla de rúbrica marcada */}
      <svg viewBox="0 0 32 32" className="h-9 w-9 shrink-0" aria-hidden="true">
        <rect x="1.5" y="1.5" width="29" height="29" rx="7" fill="none" stroke="currentColor" strokeOpacity="0.35" strokeWidth="1.5" />
        <path d="M9 9h14M9 16h14M9 23h14" stroke="currentColor" strokeOpacity="0.35" strokeWidth="1.5" />
        <rect x="18" y="12.5" width="7" height="7" rx="1.5" fill="var(--color-resaltador)" />
      </svg>
      <span className="leading-tight">
        <span className="block font-display text-[1.05rem] font-semibold">Asesor Pedagógico</span>
        <span className="block text-xs text-white/65">Universidad de Manizales</span>
      </span>
    </NavLink>
  )
}

export default function Layout() {
  const { usuario, cerrarSesion } = useAuth()
  const navegar = useNavigate()
  const ubicacion = useLocation()
  // El menú móvil queda abierto solo en la ruta donde se abrió: al navegar se cierra solo.
  const [menuEnRuta, setMenuEnRuta] = useState<string | null>(null)
  const menuAbierto = menuEnRuta === ubicacion.pathname

  const visibles = grupos
    .map((g) => ({
      ...g,
      enlaces: g.enlaces.filter((e) => e.roles === null || (usuario !== null && e.roles.includes(usuario.rol))),
    }))
    .filter((g) => g.enlaces.length > 0)

  const claseBotonClaro =
    'rounded-md border border-white/30 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/10 focus-visible:outline-resaltador'

  const navegacion = (
    <nav aria-label="Principal" className="flex-1 space-y-6">
      {visibles.map((g) => (
        <div key={g.titulo ?? 'inicio'}>
          {g.titulo && <p className="mb-1.5 px-3 text-xs font-medium text-white/50">{g.titulo}</p>}
          <ul className="space-y-0.5">
            {g.enlaces.map((e) => (
              <li key={e.to}>
                <NavLink
                  to={e.to}
                  end={e.fin}
                  className={({ isActive }) =>
                    `relative flex items-center rounded-md px-3 py-2 text-[0.95rem] transition-colors focus-visible:outline-resaltador ${
                      isActive
                        ? 'bg-white/10 font-semibold text-white before:absolute before:inset-y-2 before:left-0 before:w-1 before:rounded-full before:bg-resaltador'
                        : 'text-white/75 hover:bg-white/5 hover:text-white'
                    }`
                  }
                >
                  {e.texto}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  )

  const sesion = usuario ? (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-resaltador text-sm font-semibold text-pizarra"
        >
          {iniciales(usuario.nombre)}
        </span>
        <p className="min-w-0 leading-tight">
          <span className="block truncate text-sm font-medium text-white">{usuario.nombre}</span>
          <span className="block text-xs text-white/60">{ETIQUETA_ROL[usuario.rol]}</span>
        </p>
      </div>
      <button
        type="button"
        onClick={() => {
          cerrarSesion()
          navegar('/login')
        }}
        className={`w-full ${claseBotonClaro}`}
      >
        Cerrar sesión
      </button>
    </div>
  ) : (
    <NavLink to="/login" className={`block text-center ${claseBotonClaro}`}>
      Iniciar sesión
    </NavLink>
  )

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[16.5rem_1fr]">
      <a
        href="#contenido"
        className="sr-only z-50 focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:rounded focus:bg-white focus:p-2 focus:text-tinta"
      >
        Saltar al contenido
      </a>

      {/* Barra superior en móvil y tableta */}
      <header className="sticky top-0 z-40 bg-pizarra text-white lg:hidden">
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <Marca />
          <button
            type="button"
            aria-expanded={menuAbierto}
            aria-controls="menu-movil"
            onClick={() => setMenuEnRuta(menuAbierto ? null : ubicacion.pathname)}
            className={claseBotonClaro}
          >
            {menuAbierto ? 'Cerrar' : 'Menú'}
          </button>
        </div>
        {menuAbierto && (
          <div id="menu-movil" className="space-y-6 border-t border-white/10 px-4 pb-5 pt-4">
            {navegacion}
            {sesion}
          </div>
        )}
      </header>

      {/* Barra lateral en escritorio */}
      <aside className="sticky top-0 hidden h-screen flex-col gap-8 overflow-y-auto bg-pizarra px-4 py-6 text-white lg:flex">
        <Marca />
        {navegacion}
        <div className="space-y-5 border-t border-white/10 pt-5">
          {sesion}
          <EstadoApi enOscuro />
        </div>
      </aside>

      <div className="flex min-w-0 flex-col">
        <main id="contenido" className="flex-1">
          <Outlet />
        </main>
        <footer className="border-t border-slate-200">
          <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-4 text-sm text-slate-600 sm:flex-row sm:items-center sm:justify-between lg:px-8">
            <p>Asesor Pedagógico Inteligente, proyecto final de Inteligencia Artificial (2026)</p>
            <span className="lg:hidden">
              <EstadoApi />
            </span>
          </div>
        </footer>
      </div>
    </div>
  )
}

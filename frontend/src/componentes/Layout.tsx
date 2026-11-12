import { NavLink, Outlet } from 'react-router-dom'
import EstadoApi from './EstadoApi'

const enlaces = [
  { to: '/', texto: 'Proyecto', fin: true },
  { to: '/portafolio', texto: 'Portafolio' },
  { to: '/rubricas', texto: 'Rúbricas' },
  { to: '/revision', texto: 'Revisión docente' },
  { to: '/informe', texto: 'Informe' },
  { to: '/mapa-mental', texto: 'Mapa mental' },
  { to: '/login', texto: 'Iniciar sesión' },
]

export default function Layout() {
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
              {enlaces.map((e) => (
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

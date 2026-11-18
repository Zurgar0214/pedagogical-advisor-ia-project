import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  crearEntrega,
  listarEstudiantes,
  obtenerPortafolio,
  type EntradaPortafolio,
  type EstudianteResumen,
  type Portafolio as TipoPortafolio,
} from '../api/iteracion2'
import { useAuth } from '../auth/contexto'
import { botonPrim, campo, mensajeError, tarjeta } from '../componentes/estilos'
import { Aviso, Insignia } from '../componentes/ui'
import { ETIQUETA_ESTADO, ETIQUETA_FALTANTE, TONO_ESTADO } from './estadoEntrega'

function Tarjeta({ item, estudianteId, esEstudiante }: { item: EntradaPortafolio; estudianteId: number; esEstudiante: boolean }) {
  const navegar = useNavigate()
  const [creando, setCreando] = useState(esEstudiante)
  const [error, setError] = useState<string | null>(null)
  const { laboratorio: lab, entrega } = item
  const r = lab.rubrica_vigente

  async function iniciar() {
    setCreando(true)
    setError(null)
    try {
      const e = await crearEntrega(lab.id, esEstudiante ? undefined : estudianteId)
      navegar(`/entregas/${e.id}`)
    } catch (err) {
      setError(mensajeError(err))
      setCreando(false)
    }
  }

  return (
    <li className={tarjeta}>
      <p className="text-sm text-slate-600">{lab.codigo}</p>
      <h3 className="font-semibold text-tinta">{lab.titulo}</h3>
      <div className="mt-2">
        {entrega ? (
          <Insignia tono={TONO_ESTADO[entrega.estado]}>{ETIQUETA_ESTADO[entrega.estado]}</Insignia>
        ) : (
          <Insignia tono="gris">Sin iniciar</Insignia>
        )}
      </div>
      {entrega && entrega.faltantes.length > 0 && (
        <p className="mt-2 text-sm text-amber-900">Faltan: {entrega.faltantes.map((f) => ETIQUETA_FALTANTE[f] ?? f).join(', ')}.</p>
      )}
      <div className="mt-3">
        {entrega ? (
          <Link to={`/entregas/${entrega.id}`} className="text-sm font-medium text-marca underline">
            Ver entrega
          </Link>
        ) : r?.valida ? (
          <button type="button" onClick={iniciar} disabled={creando} className={botonPrim}>
            {creando ? 'Iniciando…' : 'Iniciar entrega'}
          </button>
        ) : (
          <p className="text-sm text-slate-700">
            {r ? 'La rúbrica de este laboratorio tiene inconsistencias; aún no se puede entregar.' : 'Este laboratorio aún no tiene rúbrica; aún no se puede entregar.'}
          </p>
        )}
      </div>
      {error && <div className="mt-2"><Aviso tipo="error">{error}</Aviso></div>}
    </li>
  )
}

export default function Portafolio() {
  const { usuario } = useAuth()
  const esEstudiante = usuario?.rol === 'estudiante'
  const [estudiantes, setEstudiantes] = useState<EstudianteResumen[]>([])
  const [seleccion, setSeleccion] = useState<number | ''>('')
  const [datos, setDatos] = useState<TipoPortafolio | null>(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (esEstudiante) return
    let activo = true
    listarEstudiantes()
      .then((l) => activo && setEstudiantes(l))
      .catch((e) => activo && setError(mensajeError(e)))
    return () => {
      activo = false
    }
  }, [esEstudiante])

  useEffect(() => {
    if (!esEstudiante && seleccion === '') return
    let activo = true
    obtenerPortafolio(esEstudiante ? undefined : Number(seleccion))
      .then((p) => {
        if (!activo) return
        setDatos(p)
        setError(null)
      })
      .catch((e) => activo && setError(mensajeError(e)))
      .finally(() => activo && setCargando(false))
    return () => {
      activo = false
    }
  }, [esEstudiante, seleccion])

  return (
    <section className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10">
      <h1 className="font-display text-[1.95rem] font-semibold leading-tight text-tinta">Portafolio</h1>
      <p className="mt-1 text-sm text-slate-600">Laboratorios de las cohortes 1 y 2 y el estado de cada entrega.</p>

      {!esEstudiante && (
        <div className="mt-4 max-w-sm">
          <label htmlFor="sel-est" className="block text-sm font-medium text-slate-800">Estudiante</label>
          <select id="sel-est" value={seleccion} onChange={(e) => {
              setCargando(e.target.value !== '')
              setSeleccion(e.target.value === '' ? '' : Number(e.target.value))
            }} className={campo}>
            <option value="">Selecciona un estudiante…</option>
            {estudiantes.map((s) => (
              <option key={s.id} value={s.id}>
                {s.nombre} ({s.correo})
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="mt-4">{error && <Aviso tipo="error">{error}</Aviso>}</div>
      {cargando && <p role="status" className="mt-4 text-slate-600">Cargando portafolio…</p>}
      {!esEstudiante && seleccion === '' && !error && <p className="mt-6 text-slate-600">Elige un estudiante para ver su portafolio.</p>}

      {datos && (esEstudiante || seleccion !== '') && (
        <div className="mt-6 space-y-8">
          <p className="text-slate-700">
            Portafolio de <strong>{datos.estudiante.nombre}</strong>
          </p>
          {datos.cohortes.map((c) => (
            <section key={c.cohorte} aria-labelledby={`pc-${c.cohorte}`}>
              <h2 id={`pc-${c.cohorte}`} className="text-lg font-semibold text-tinta">Cohorte {c.cohorte}</h2>
              {c.laboratorios.length === 0 ? (
                <p className="mt-2 text-sm text-slate-600">No hay laboratorios en esta cohorte.</p>
              ) : (
                <ul className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {c.laboratorios.map((it) => (
                    <Tarjeta key={it.laboratorio.id} item={it} estudianteId={datos.estudiante.id} esEstudiante={esEstudiante} />
                  ))}
                </ul>
              )}
            </section>
          ))}
        </div>
      )}
    </section>
  )
}

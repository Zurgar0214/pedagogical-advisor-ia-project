import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { colaEvaluaciones, type Evaluacion, type EstadoEvaluacion } from '../api/iteracion3'
import { campo, formatoFecha, mensajeError, tarjeta } from '../componentes/estilos'
import { Aviso, Insignia } from '../componentes/ui'
import { ETIQUETA_EVAL, formatoNota, TONO_EVAL } from './estadoEvaluacion'

const ESTADOS: EstadoEvaluacion[] = ['en_revision', 'aprobada', 'publicada', 'error']

export default function Revision() {
  const [estado, setEstado] = useState<EstadoEvaluacion>('en_revision')
  const [lista, setLista] = useState<{ estado: EstadoEvaluacion; items: Evaluacion[] } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let activo = true
    colaEvaluaciones(estado)
      .then((items) => {
        if (!activo) return
        setLista({ estado, items })
        setError(null)
      })
      .catch((e) => activo && setError(mensajeError(e)))
    return () => {
      activo = false
    }
  }, [estado])

  const cargando = lista === null || lista.estado !== estado
  const items = !cargando && lista ? lista.items : []

  return (
    <section className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10">
      <h1 className="font-serif text-[1.95rem] font-semibold leading-tight text-tinta">Revisión docente</h1>
      <p className="mt-1 text-sm text-slate-600">Evaluaciones generadas con IA pendientes de revisión, aprobación o publicación.</p>

      <div className="mt-4 max-w-xs">
        <label htmlFor="filtro-estado" className="block text-sm font-medium text-slate-800">Estado</label>
        <select id="filtro-estado" className={campo} value={estado} onChange={(e) => setEstado(e.target.value as EstadoEvaluacion)}>
          {ESTADOS.map((s) => (
            <option key={s} value={s}>{ETIQUETA_EVAL[s]}</option>
          ))}
        </select>
      </div>

      <div className="mt-4" aria-live="polite">
        {error && <Aviso tipo="error">{error}</Aviso>}
        {cargando && !error && <p role="status" className="text-sm text-slate-600">Cargando…</p>}
      </div>

      {!cargando && items.length === 0 && !error && (
        <p className={`${tarjeta} mt-4 text-sm text-slate-700`}>No hay evaluaciones en estado «{ETIQUETA_EVAL[estado]}».</p>
      )}

      {items.length > 0 && (
        <div className={`${tarjeta} mt-4 overflow-x-auto p-0`}>
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Evaluaciones en estado {ETIQUETA_EVAL[estado]}</caption>
            <thead className="bg-slate-100 text-xs text-slate-700">
              <tr>
                <th scope="col" className="px-3 py-2">Estudiante</th>
                <th scope="col" className="px-3 py-2">Laboratorio</th>
                <th scope="col" className="px-3 py-2">Nota preliminar</th>
                <th scope="col" className="px-3 py-2">Estado</th>
                <th scope="col" className="px-3 py-2">Revisión requerida</th>
                <th scope="col" className="px-3 py-2">Fecha</th>
                <th scope="col" className="px-3 py-2"><span className="sr-only">Acciones</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((e) => (
                <tr key={e.id}>
                  <td className="px-3 py-2">{e.estudiante.nombre}</td>
                  <td className="px-3 py-2">{e.laboratorio.codigo} · {e.laboratorio.titulo}</td>
                  <td className="px-3 py-2 font-medium">{formatoNota(e.nota_preliminar)}</td>
                  <td className="px-3 py-2"><Insignia tono={TONO_EVAL[e.estado]}>{ETIQUETA_EVAL[e.estado]}</Insignia></td>
                  <td className="px-3 py-2">{e.requiere_revision ? <Insignia tono="ambar">Sí, prioritaria</Insignia> : <span className="text-slate-600">No</span>}</td>
                  <td className="px-3 py-2">{formatoFecha(e.creado_en)}</td>
                  <td className="px-3 py-2">
                    <Link to={`/evaluaciones/${e.id}`} className="text-marca underline" aria-label={`Abrir evaluación de ${e.estudiante.nombre}, ${e.laboratorio.codigo}`}>Abrir</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

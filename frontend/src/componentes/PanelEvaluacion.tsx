import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  configuracionIA,
  evaluarEntrega,
  listarEvaluacionesEntrega,
  type ConfiguracionIA,
  type Evaluacion,
} from '../api/iteracion3'
import type { EstadoEntrega } from '../api/iteracion2'
import { ETIQUETA_EVAL, formatoNota, TONO_EVAL } from '../paginas/estadoEvaluacion'
import { botonPrim, formatoFecha, mensajeError, tarjeta } from './estilos'
import { Aviso, Insignia } from './ui'

const INTERVALO_MS = 3000

interface Props {
  entregaId: number
  estadoEntrega: EstadoEntrega
  esDocente: boolean
  /** Se invoca cuando cambia el estado de alguna evaluación (para refrescar la entrega). */
  alCambiar: () => void
}

export default function PanelEvaluacion({ entregaId, estadoEntrega, esDocente, alCambiar }: Props) {
  const [evaluaciones, setEvaluaciones] = useState<Evaluacion[] | null>(null)
  const [config, setConfig] = useState<ConfiguracionIA | null>(null)
  const [errorConfig, setErrorConfig] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lanzando, setLanzando] = useState(false)
  const procesandoAntes = useRef(false)
  const alCambiarRef = useRef(alCambiar)
  useEffect(() => {
    alCambiarRef.current = alCambiar
  }, [alCambiar])

  const recargar = useCallback(async () => {
    try {
      const lista = await listarEvaluacionesEntrega(entregaId)
      setEvaluaciones(lista)
      setError(null)
      const hay = lista.some((e) => e.estado === 'procesando')
      if (procesandoAntes.current && !hay) alCambiarRef.current()
      procesandoAntes.current = hay
    } catch (e) {
      setError(mensajeError(e))
    }
  }, [entregaId])

  useEffect(() => {
    let activo = true
    listarEvaluacionesEntrega(entregaId)
      .then((lista) => {
        if (!activo) return
        setEvaluaciones(lista)
        procesandoAntes.current = lista.some((e) => e.estado === 'procesando')
      })
      .catch((e) => activo && setError(mensajeError(e)))
    if (esDocente) {
      configuracionIA()
        .then((c) => activo && setConfig(c))
        .catch((e) => activo && setErrorConfig(mensajeError(e)))
    }
    return () => {
      activo = false
    }
  }, [entregaId, esDocente])

  const procesando = evaluaciones?.some((e) => e.estado === 'procesando') ?? false
  useEffect(() => {
    if (!procesando) return
    const t = window.setInterval(() => void recargar(), INTERVALO_MS)
    return () => window.clearInterval(t)
  }, [procesando, recargar])

  async function lanzar() {
    setLanzando(true)
    setError(null)
    try {
      await evaluarEntrega(entregaId)
      procesandoAntes.current = true
      await recargar()
      alCambiarRef.current()
    } catch (e) {
      setError(mensajeError(e))
    } finally {
      setLanzando(false)
    }
  }

  if (!esDocente) {
    const publicada = (evaluaciones ?? []).find((e) => e.estado === 'publicada')
    if (!publicada) return null
    return (
      <section className={`${tarjeta} mt-6`} aria-labelledby="h-eval-est">
        <h2 id="h-eval-est" className="text-lg font-semibold text-tinta">Tu evaluación</h2>
        <p className="mt-2 text-sm text-slate-700">
          Nota final: <strong className="text-2xl text-tinta">{formatoNota(publicada.nota_final)}</strong> <span className="text-slate-600">/ 5,0</span>
        </p>
        {publicada.publicado_en && <p className="text-xs text-slate-600">Publicada el {formatoFecha(publicada.publicado_en)}</p>}
        <Link to={`/evaluaciones/${publicada.id}`} className="mt-2 inline-block text-marca underline">Ver retroalimentación detallada</Link>
      </section>
    )
  }

  const puedeEvaluar = (estadoEntrega === 'lista' || estadoEntrega === 'evaluada') && config?.disponible === true && !procesando
  let razon = ''
  if (estadoEntrega !== 'lista' && estadoEntrega !== 'evaluada') razon = 'La entrega debe estar en estado "Lista" o "Evaluada" para evaluarla.'
  else if (config && !config.disponible) razon = `Proveedor no disponible: ${config.motivo}`
  else if (procesando) razon = 'Hay una evaluación en curso.'

  return (
    <section className={`${tarjeta} mt-6`} aria-labelledby="h-eval">
      <h2 id="h-eval" className="text-lg font-semibold text-tinta">Evaluación con IA</h2>

      {errorConfig && <div className="mt-2"><Aviso tipo="error">{errorConfig}</Aviso></div>}
      {config && (
        <div className="mt-2 text-sm text-slate-700">
          <p className="flex flex-wrap items-center gap-2">
            Proveedor: <strong>{config.proveedor}</strong>
            <Insignia tono={config.disponible ? 'verde' : 'rojo'}>{config.disponible ? 'Disponible' : 'No disponible'}</Insignia>
          </p>
          <p>Modelo principal: <strong>{config.modelo_principal}</strong> · Escalamiento: <strong>{config.modelo_escalamiento}</strong></p>
          <p className="text-xs text-slate-600">Umbral de confianza: {config.umbral_confianza}{config.motivo ? ` · ${config.motivo}` : ''}</p>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button type="button" className={botonPrim} disabled={!puedeEvaluar || lanzando} onClick={() => void lanzar()}>
          {lanzando ? 'Iniciando…' : 'Evaluar con IA'}
        </button>
        {razon && <span className="text-xs text-slate-600">{razon}</span>}
      </div>

      <div className="mt-3" aria-live="polite">
        {procesando && <Aviso tipo="advertencia">Evaluación en proceso… se actualiza automáticamente cada 3 segundos.</Aviso>}
      </div>
      {error && <div className="mt-2"><Aviso tipo="error">{error}</Aviso></div>}

      <h3 className="mt-4 text-sm font-semibold text-slate-800">Evaluaciones de esta entrega</h3>
      {evaluaciones === null && <p className="text-sm text-slate-600">Cargando…</p>}
      {evaluaciones?.length === 0 && <p className="text-sm text-slate-600">Aún no hay evaluaciones.</p>}
      <ul className="mt-1 divide-y divide-slate-100">
        {evaluaciones?.map((e) => (
          <li key={e.id} className="py-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Insignia tono={TONO_EVAL[e.estado]}>{ETIQUETA_EVAL[e.estado]}</Insignia>
              <span className="text-slate-700">{formatoFecha(e.creado_en)}</span>
              {e.estado !== 'procesando' && e.estado !== 'error' && (
                <span className="text-slate-700">
                  Nota final <strong>{formatoNota(e.nota_final)}</strong>
                  {e.nota_preliminar != null && <span className="text-slate-600"> (IA {formatoNota(e.nota_preliminar)})</span>}
                </span>
              )}
              {e.estado !== 'procesando' && e.estado !== 'error' && (
                <Link to={`/evaluaciones/${e.id}`} className="text-marca underline">Ver detalle</Link>
              )}
            </div>
            {e.estado === 'error' && e.error && (
              <p role="alert" className="mt-1 rounded border border-red-300 bg-red-50 px-2 py-1 text-red-800">{e.error}</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

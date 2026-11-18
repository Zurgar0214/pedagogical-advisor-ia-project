import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../auth/contexto'
import {
  ajustarCriterio,
  aprobarEvaluacion,
  obtenerEvaluacion,
  publicarEvaluacion,
  type Aprendizaje,
  type CriterioEvaluado,
  type Evaluacion,
  type HallazgoCodigo,
  type VerificacionTecnica,
} from '../api/iteracion3'
import { botonPrim, botonSec, campo, formatoFecha, mensajeError, tarjeta } from '../componentes/estilos'
import { Aviso, Insignia } from '../componentes/ui'
import { ETIQUETA_DOMINIO, ETIQUETA_EVAL, formatoNota, TONO_DOMINIO, TONO_EVAL } from './estadoEvaluacion'

function Lista({ titulo, items, tono }: { titulo: string; items: string[]; tono?: 'verde' | 'ambar' | 'azul' }) {
  if (!items || items.length === 0) return null
  const color = tono === 'verde' ? 'text-emerald-900' : tono === 'ambar' ? 'text-amber-900' : 'text-slate-800'
  return (
    <div>
      <h4 className={`text-sm font-semibold ${color}`}>{titulo}</h4>
      <ul className="list-disc pl-5 text-sm text-slate-700">
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </div>
  )
}

function Nota({ etiqueta, valor, destacada }: { etiqueta: string; valor: number | null | undefined; destacada?: boolean }) {
  return (
    <div className={`rounded-lg border px-4 py-3 text-center ${destacada ? 'border-marca bg-blue-50' : 'border-slate-200 bg-slate-50'}`}>
      <p className="text-xs font-semibold text-slate-600">{etiqueta}</p>
      <p className={`font-serif font-semibold text-tinta ${destacada ? 'text-4xl' : 'text-3xl'}`}>
        {formatoNota(valor)} <span className="text-sm font-normal text-slate-600">/ 5,0</span>
      </p>
    </div>
  )
}

function BarraConfianza({ valor }: { valor: number }) {
  const pct = Math.round(valor * 100)
  return (
    <div className="flex items-center gap-2" role="img" aria-label={`Confianza de la IA: ${pct} %`}>
      <div className="h-2 w-28 overflow-hidden rounded bg-slate-200">
        <div className="h-full bg-marca" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-700">{pct} %</span>
    </div>
  )
}

function AjusteCriterio({ evaluacionId, criterio, alActualizar }: { evaluacionId: number; criterio: CriterioEvaluado; alActualizar: (e: Evaluacion) => void }) {
  const [nivel, setNivel] = useState(criterio.nivel_final)
  const [justificacion, setJustificacion] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)
  const idBase = `ajuste-${criterio.criterio_id}`
  const descriptor = criterio.niveles_disponibles.find((n) => n.nombre === nivel)?.descriptor

  async function enviar(e: FormEvent) {
    e.preventDefault()
    if (justificacion.trim().length < 10) return setError('La justificación debe tener al menos 10 caracteres.')
    setError(null)
    setGuardando(true)
    try {
      const nueva = await ajustarCriterio(evaluacionId, criterio.criterio_id, nivel, justificacion.trim())
      setJustificacion('')
      alActualizar(nueva)
    } catch (err) {
      setError(mensajeError(err))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="mt-3 rounded border border-slate-200 bg-slate-50 p-3">
      <h4 className="text-sm font-semibold text-slate-800">Ajustar nivel (docente)</h4>
      <label htmlFor={`${idBase}-nivel`} className="mt-2 block text-sm text-slate-800">Nivel</label>
      <select id={`${idBase}-nivel`} className={campo} value={nivel} onChange={(e) => setNivel(e.target.value)}>
        {criterio.niveles_disponibles.map((n) => (
          <option key={n.nombre} value={n.nombre}>{`${n.nombre} (${formatoNota(n.valor)})`}</option>
        ))}
      </select>
      {descriptor && <p className="mt-1 text-xs text-slate-600">{descriptor}</p>}
      <label htmlFor={`${idBase}-just`} className="mt-2 block text-sm text-slate-800">Justificación del ajuste (mínimo 10 caracteres)</label>
      <textarea id={`${idBase}-just`} rows={3} className={campo} value={justificacion} onChange={(e) => setJustificacion(e.target.value)} />
      {error && <p role="alert" className="mt-2 text-sm text-red-800">{error}</p>}
      <button type="submit" className={`${botonPrim} mt-2`} disabled={guardando}>
        {guardando ? 'Guardando…' : 'Guardar ajuste'}
      </button>
    </form>
  )
}

function TarjetaCriterio({ ev, c, esDocente, alActualizar }: { ev: Evaluacion; c: CriterioEvaluado; esDocente: boolean; alActualizar: (e: Evaluacion) => void }) {
  const cambiado = c.nivel_ia !== undefined && c.nivel_ia !== c.nivel_final
  return (
    <article className={tarjeta} aria-labelledby={`crit-${c.criterio_id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 id={`crit-${c.criterio_id}`} className="text-base font-semibold text-tinta">{c.criterio}</h3>
          <p className="text-xs text-slate-600">Competencia: {c.competencia} · Peso: {c.peso} %</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {esDocente && c.escalado && <Insignia tono="ambar">Escalado</Insignia>}
          {esDocente && c.nivel_ia !== undefined && <Insignia tono="gris">IA: {c.nivel_ia}</Insignia>}
          <Insignia tono={cambiado ? 'azul' : 'verde'}>{esDocente ? 'Final' : 'Nivel'}: {c.nivel_final} ({formatoNota(c.valor_nivel_final)})</Insignia>
        </div>
      </div>

      {esDocente && (c.confianza !== undefined || c.modelo) && (
        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-600">
          {c.confianza !== undefined && <BarraConfianza valor={c.confianza} />}
          {c.modelo && <span>Modelo: {c.modelo}</span>}
        </div>
      )}

      <p className="mt-3 whitespace-pre-line text-sm text-slate-800">{c.justificacion}</p>

      {c.evidencias.length > 0 && (
        <div className="mt-3">
          <h4 className="text-sm font-semibold text-slate-800">Evidencias citadas</h4>
          <ul className="space-y-2">
            {c.evidencias.map((e, i) => (
              <li key={i} className="text-sm">
                <p className="text-xs text-slate-600"><strong>{e.fuente}</strong>{e.ubicacion && ` · ${e.ubicacion}`}</p>
                {e.fragmento && <blockquote className="border-l-4 border-slate-300 pl-3 italic text-slate-700">“{e.fragmento}”</blockquote>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <Lista titulo="Fortalezas" items={c.fortalezas} tono="verde" />
        <Lista titulo="Aspectos por mejorar" items={c.debilidades} tono="ambar" />
        <Lista titulo="Recomendaciones" items={c.recomendaciones} tono="azul" />
      </div>

      {c.ajuste_docente && (
        <div className="mt-3 rounded border border-blue-200 bg-blue-50 p-3 text-sm">
          <h4 className="font-semibold text-blue-900">Ajuste docente</h4>
          <p className="text-slate-800">Nivel: <strong>{c.ajuste_docente.nivel}</strong></p>
          <p className="text-slate-800">{c.ajuste_docente.justificacion}</p>
          <p className="text-xs text-slate-600">{c.ajuste_docente.usuario.nombre} · {formatoFecha(c.ajuste_docente.fecha)}</p>
        </div>
      )}

      {esDocente && ev.estado === 'en_revision' && <AjusteCriterio evaluacionId={ev.id} criterio={c} alActualizar={alActualizar} />}
    </article>
  )
}

function TablaHallazgos({ titulo, filas }: { titulo: string; filas: HallazgoCodigo[] }) {
  if (filas.length === 0) return <p className="text-sm text-slate-600">{titulo}: ninguno.</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <caption className="pb-1 text-left text-sm font-semibold text-slate-800">{titulo} ({filas.length})</caption>
        <thead className="bg-slate-100 text-xs text-slate-700">
          <tr>
            <th scope="col" className="px-2 py-1">Archivo</th>
            <th scope="col" className="px-2 py-1">Línea</th>
            <th scope="col" className="px-2 py-1">Regla</th>
            <th scope="col" className="px-2 py-1">Mensaje</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {filas.map((h, i) => (
            <tr key={i}>
              <td className="break-all px-2 py-1">{h.archivo}</td>
              <td className="px-2 py-1">{h.linea ?? '—'}</td>
              <td className="px-2 py-1">{h.regla || '—'}</td>
              <td className="px-2 py-1">{h.mensaje}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PanelVerificacion({ v }: { v: VerificacionTecnica }) {
  const lenguajes = Object.entries(v.archivos_por_lenguaje)
  return (
    <section className={`${tarjeta} space-y-3`} aria-labelledby="h-verif">
      <h2 id="h-verif" className="text-lg font-semibold text-tinta">Verificación técnica</h2>
      <p className="text-sm text-slate-700">Archivos analizados: <strong>{v.archivos_analizados}</strong></p>
      {lenguajes.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Archivos por lenguaje">
          {lenguajes.map(([l, n]) => (
            <li key={l}><Insignia tono="azul">{l}: {n}</Insignia></li>
          ))}
        </ul>
      )}
      <TablaHallazgos titulo="Errores de sintaxis" filas={v.errores_sintaxis} />
      <TablaHallazgos titulo="Hallazgos estáticos" filas={v.hallazgos_estaticos} />
      <div className="text-sm text-slate-700">
        <h3 className="font-semibold text-slate-800">Pruebas</h3>
        {v.pruebas.ejecutadas ? (
          <>
            <p>
              Total: {v.pruebas.total} · Exitosas: {v.pruebas.exitosas} · Fallidas: {v.pruebas.fallidas}
              {!!v.pruebas.errores && ` · Con error: ${v.pruebas.errores}`}
              {!!v.pruebas.omitidas && ` · Omitidas: ${v.pruebas.omitidas}`}
            </p>
            {v.pruebas.tiempo_agotado && <p className="font-medium text-amber-800">Las pruebas superaron el tiempo límite y se detuvieron.</p>}
            <p className="text-xs text-slate-500">Ejecutadas en una sandbox aislada: sin red, con límites de CPU, memoria y tiempo, y usuario sin privilegios.</p>
          </>
        ) : (
          <p>No se ejecutaron pruebas{v.pruebas.motivo ? `: ${v.pruebas.motivo}` : '.'}</p>
        )}
        {v.pruebas.ejecutadas && v.pruebas.salida && <pre className="mt-1 max-h-48 overflow-auto rounded bg-slate-100 p-2 text-xs">{v.pruebas.salida}</pre>}
      </div>
      {v.repositorios_no_analizados.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-800">Repositorios no analizados</h3>
          <ul className="list-disc pl-5 text-sm text-slate-700">
            {v.repositorios_no_analizados.map((r) => (
              <li key={r} className="break-all">{r}</li>
            ))}
          </ul>
        </div>
      )}
      <Lista titulo="Notas" items={v.notas} />
    </section>
  )
}

function Trazabilidad({ ev }: { ev: Evaluacion }) {
  const uso = ev.uso ?? []
  return (
    <section className={`${tarjeta} space-y-3`} aria-labelledby="h-traza">
      <h2 id="h-traza" className="text-lg font-semibold text-tinta">Trazabilidad</h2>
      <p className="text-sm text-slate-700">
        Proveedor: <strong>{ev.proveedor ?? '—'}</strong> · Modelo principal: <strong>{ev.modelo_principal ?? '—'}</strong> · Versión de prompt: <strong>{ev.version_prompt ?? '—'}</strong>
      </p>
      {ev.requiere_revision && (
        <div className="rounded border-2 border-amber-500 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900" role="status">
          Esta evaluación requiere revisión docente detallada.
        </div>
      )}
      {ev.advertencias && ev.advertencias.length > 0 && (
        <div role="alert" className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <p className="font-semibold">Advertencias</p>
          <ul className="list-disc pl-5">
            {ev.advertencias.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Uso de modelos por llamada</caption>
          <thead className="bg-slate-100 text-xs text-slate-700">
            <tr>
              <th scope="col" className="px-2 py-1">Propósito</th>
              <th scope="col" className="px-2 py-1">Modelo</th>
              <th scope="col" className="px-2 py-1 text-right">Entrada</th>
              <th scope="col" className="px-2 py-1 text-right">Salida</th>
              <th scope="col" className="px-2 py-1 text-right">Caché (lect./escr.)</th>
              <th scope="col" className="px-2 py-1 text-right">Duración</th>
              <th scope="col" className="px-2 py-1 text-right">Intentos</th>
              <th scope="col" className="px-2 py-1 text-right">Costo (USD)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {uso.map((u, i) => (
              <tr key={i}>
                <td className="px-2 py-1">{u.proposito}</td>
                <td className="px-2 py-1">{u.proveedor} / {u.modelo}</td>
                <td className="px-2 py-1 text-right">{u.tokens_entrada.toLocaleString('es-CO')}</td>
                <td className="px-2 py-1 text-right">{u.tokens_salida.toLocaleString('es-CO')}</td>
                <td className="px-2 py-1 text-right">{u.tokens_cache_lectura.toLocaleString('es-CO')} / {u.tokens_cache_escritura.toLocaleString('es-CO')}</td>
                <td className="px-2 py-1 text-right">{u.duracion_s.toFixed(1)} s</td>
                <td className="px-2 py-1 text-right">{u.intentos}</td>
                <td className="px-2 py-1 text-right">{u.costo_usd_estimado.toFixed(4)}</td>
              </tr>
            ))}
            {uso.length === 0 && (
              <tr><td colSpan={8} className="px-2 py-2 text-slate-600">Sin registros de uso.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-sm text-slate-800">Costo total estimado: <strong>USD {(ev.costo_usd_estimado ?? 0).toFixed(4)}</strong></p>
    </section>
  )
}

function Aprendizajes({ items }: { items: Aprendizaje[] }) {
  if (items.length === 0) return null
  return (
    <section className={tarjeta} aria-labelledby="h-apr">
      <h2 id="h-apr" className="text-lg font-semibold text-tinta">Aprendizajes por tema</h2>
      <ul className="mt-2 space-y-3">
        {items.map((a, i) => (
          <li key={i} className="rounded border border-slate-200 p-3 text-sm">
            <p className="flex flex-wrap items-center gap-2">
              <strong className="text-slate-900">{a.tema}</strong>
              <Insignia tono={TONO_DOMINIO[a.nivel_dominio]}>Dominio: {ETIQUETA_DOMINIO[a.nivel_dominio]}</Insignia>
            </p>
            <p className="mt-1 text-slate-700"><strong>Qué aprendió:</strong> {a.que_aprendio}</p>
            <p className="text-slate-700"><strong>Cómo lo aplicó:</strong> {a.como_aplico}</p>
            <p className="text-slate-700"><strong>Qué fortalecer:</strong> {a.que_fortalecer}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function EvaluacionDetalle() {
  const { id } = useParams()
  const evalId = Number(id)
  const { usuario } = useAuth()
  const esDocente = usuario?.rol === 'docente' || usuario?.rol === 'admin'
  const [ev, setEv] = useState<Evaluacion | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const [aviso, setAviso] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null)
  const [accion, setAccion] = useState(false)

  useEffect(() => {
    let activo = true
    obtenerEvaluacion(evalId)
      .then((e) => activo && setEv(e))
      .catch((err) => activo && setError(mensajeError(err)))
      .finally(() => activo && setCargando(false))
    return () => {
      activo = false
    }
  }, [evalId])

  if (!Number.isInteger(evalId)) return <p className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10 text-red-800">Evaluación no válida.</p>
  if (cargando) return <p role="status" className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10 text-slate-600">Cargando evaluación…</p>
  if (error || !ev) {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10">
        <Aviso tipo="error">{error ?? 'No se pudo cargar la evaluación.'}</Aviso>
        <Link to={esDocente ? '/revision' : '/portafolio'} className="mt-4 inline-block text-marca underline">Volver</Link>
      </section>
    )
  }

  async function ejecutar(tipo: 'aprobar' | 'publicar') {
    if (!ev) return
    const texto =
      tipo === 'aprobar'
        ? 'Vas a aprobar esta evaluación. Ya no podrás ajustar niveles. ¿Continuar?'
        : 'Vas a publicar esta evaluación: el estudiante podrá ver la nota final y la retroalimentación. ¿Continuar?'
    if (!window.confirm(texto)) return
    setAccion(true)
    setAviso(null)
    try {
      const nueva = tipo === 'aprobar' ? await aprobarEvaluacion(ev.id) : await publicarEvaluacion(ev.id)
      setEv(nueva)
      setAviso({ tipo: 'ok', texto: tipo === 'aprobar' ? 'Evaluación aprobada.' : 'Evaluación publicada al estudiante.' })
    } catch (e) {
      setAviso({ tipo: 'error', texto: mensajeError(e) })
    } finally {
      setAccion(false)
    }
  }

  function alAjustar(nueva: Evaluacion) {
    setEv(nueva)
    setAviso({ tipo: 'ok', texto: 'Ajuste guardado. La nota final fue recalculada.' })
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10">
      <Link to={esDocente ? '/revision' : `/entregas/${ev.entrega_id}`} className="text-sm text-marca underline">
        {esDocente ? '← Revisión docente' : '← Mi entrega'}
      </Link>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <h1 className="font-serif text-[1.95rem] font-semibold leading-tight text-tinta">
          {esDocente ? 'Evaluación' : 'Retroalimentación'} · {ev.laboratorio.codigo} {ev.laboratorio.titulo}
        </h1>
        <Insignia tono={TONO_EVAL[ev.estado]}>{ETIQUETA_EVAL[ev.estado]}</Insignia>
      </div>
      <p className="mt-1 text-sm text-slate-600">
        Estudiante: {ev.estudiante.nombre} · Cohorte {ev.laboratorio.cohorte} · Rúbrica versión {ev.rubrica_version.numero}
        {ev.revisado_por && ` · Revisó: ${ev.revisado_por.nombre}`}
        {ev.publicado_en && ` · Publicada el ${formatoFecha(ev.publicado_en)}`}
      </p>

      <div aria-live="polite" className="mt-4">{aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}</div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {esDocente && ev.nota_preliminar !== undefined && <Nota etiqueta="Nota preliminar (IA)" valor={ev.nota_preliminar} />}
        <Nota etiqueta="Nota final" valor={ev.nota_final} destacada />
      </div>
      <p className="mt-2 text-xs text-slate-600">La nota la calcula el sistema a partir de la rúbrica; la IA solo propone niveles.</p>

      {esDocente && (ev.estado === 'en_revision' || ev.estado === 'aprobada') && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {ev.estado === 'en_revision' && (
            <button type="button" className={botonPrim} disabled={accion} onClick={() => void ejecutar('aprobar')}>Aprobar</button>
          )}
          {ev.estado === 'aprobada' && (
            <button type="button" className={botonPrim} disabled={accion} onClick={() => void ejecutar('publicar')}>Publicar al estudiante</button>
          )}
          <span className="text-xs text-slate-600">
            {ev.estado === 'en_revision' ? 'Ajusta los niveles que consideres necesarios antes de aprobar.' : 'La evaluación está aprobada pero aún no es visible para el estudiante.'}
          </span>
        </div>
      )}
      {esDocente && ev.estado === 'error' && ev.error && <div className="mt-4"><Aviso tipo="error">{ev.error}</Aviso></div>}

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <section className={tarjeta} aria-labelledby="h-resumen">
            <h2 id="h-resumen" className="text-lg font-semibold text-tinta">Resumen general</h2>
            <p className="mt-2 whitespace-pre-line text-sm text-slate-800">{ev.resumen || 'Sin resumen.'}</p>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <Lista titulo="Fortalezas" items={ev.fortalezas} tono="verde" />
              <Lista titulo={esDocente ? 'Debilidades' : 'Aspectos por mejorar'} items={ev.debilidades} tono="ambar" />
              <Lista titulo="Recomendaciones" items={ev.recomendaciones} tono="azul" />
            </div>
          </section>

          <section aria-labelledby="h-crit" className="space-y-4">
            <h2 id="h-crit" className="text-lg font-semibold text-tinta">{esDocente ? 'Evaluación por criterio' : 'Retroalimentación por criterio'}</h2>
            {ev.criterios.map((c) => (
              <TarjetaCriterio key={c.criterio_id} ev={ev} c={c} esDocente={esDocente} alActualizar={alAjustar} />
            ))}
          </section>

          <Aprendizajes items={ev.aprendizajes} />
        </div>

        <div className="space-y-6">
          {ev.verificacion && <PanelVerificacion v={ev.verificacion} />}
          {esDocente && <Trazabilidad ev={ev} />}
          <button type="button" className={`${botonSec} lg:hidden`} onClick={() => window.scrollTo({ top: 0 })}>Volver arriba</button>
        </div>
      </div>
    </section>
  )
}

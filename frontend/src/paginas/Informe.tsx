import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  descargarPdfInforme,
  generarInforme,
  guardarJson,
  nombreArchivoSeguro,
  obtenerInforme,
  type Informe as TipoInforme,
  type InformeResumen,
} from '../api/iteracion4'
import { ErrorApi } from '../api/cliente'
import { useAuth } from '../auth/contexto'
import { botonPrim, botonSec, formatoFecha, mensajeError, tarjeta } from '../componentes/estilos'
import { BarrasCompetencias, GraficoEvolucion } from '../componentes/GraficosInforme'
import { InsigniaDominio } from '../componentes/InsigniaDominio'
import { SelectorEstudiante } from '../componentes/SelectorEstudiante'
import { useEstudianteActivo } from '../componentes/useEstudianteActivo'
import { Aviso, Insignia } from '../componentes/ui'
import { useInformes } from '../componentes/useInformes'
import { formatoNota } from './estadoEvaluacion'

const ETIQUETA_BRECHA: Record<string, string> = {
  competencia: 'Competencia',
  tema: 'Tema',
  criterio: 'Criterio',
  sin_evidencia: 'Sin evidencia',
}

function Seccion({ id, titulo, children }: { id: string; titulo: string; children: React.ReactNode }) {
  return (
    <section className={tarjeta} aria-labelledby={id}>
      <h2 id={id} className="text-lg font-semibold text-tinta">{titulo}</h2>
      <div className="mt-3">{children}</div>
    </section>
  )
}

function Cifra({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
      <p className="text-xs font-semibold text-slate-600">{etiqueta}</p>
      <div className="mt-1 text-tinta">{children}</div>
    </div>
  )
}

function Lista({ titulo, items }: { titulo: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div>
      <h4 className="text-sm font-semibold text-slate-800">{titulo}</h4>
      <ul className="list-disc pl-5 text-sm text-slate-700">
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </div>
  )
}

function VistaInforme({ informe, esDocente }: { informe: TipoInforme; esDocente: boolean }) {
  const [descargando, setDescargando] = useState(false)
  const [errorDescarga, setErrorDescarga] = useState<string | null>(null)
  const ag = informe.agregado
  const si = informe.sintesis
  const base = `informe-${nombreArchivoSeguro(informe.estudiante.nombre)}-${informe.id}`

  async function pdf() {
    setDescargando(true)
    setErrorDescarga(null)
    try {
      await descargarPdfInforme(informe.id, `${base}.pdf`)
    } catch (e) {
      setErrorDescarga(mensajeError(e))
    } finally {
      setDescargando(false)
    }
  }

  if (!ag || !si) return <Aviso tipo="advertencia">Este informe no contiene datos para mostrar.</Aviso>

  const plan = [...si.plan].sort((a, b) => a.prioridad - b.prioridad)
  const cohortes = Object.entries(ag.promedio_cohorte).sort(([a], [b]) => a.localeCompare(b))

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" className={botonPrim} onClick={() => void pdf()} disabled={descargando}>
          {descargando ? 'Descargando…' : 'Descargar PDF'}
        </button>
        <button type="button" className={botonSec} onClick={() => guardarJson(informe, `${base}.json`)}>
          Descargar JSON
        </button>
        <Link to="/mapa-mental" className="text-sm text-marca underline">Ver mapa mental</Link>
        <span className="text-xs text-slate-600">Generado el {formatoFecha(informe.generado_en)}</span>
      </div>
      {errorDescarga && <Aviso tipo="error">{errorDescarga}</Aviso>}

      <Seccion id="h-cab" titulo={`Informe de ${informe.estudiante.nombre}`}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Cifra etiqueta="Promedio general">
            <span className="font-display text-3xl font-semibold">{formatoNota(ag.promedio_general)}</span>
            <span className="text-sm text-slate-600"> / 5,0</span>
          </Cifra>
          <Cifra etiqueta="Nivel general"><InsigniaDominio nivel={ag.nivel_general} /></Cifra>
          <Cifra etiqueta="Laboratorios evaluados">
            <span className="font-display text-3xl font-semibold">{ag.laboratorios.length}</span>
            <span className="text-sm text-slate-600"> de {ag.laboratorios_totales}</span>
          </Cifra>
          <Cifra etiqueta="Promedio por cohorte">
            {cohortes.length === 0 ? (
              <span className="text-sm text-slate-600">Sin datos</span>
            ) : (
              <ul className="text-sm">
                {cohortes.map(([c, v]) => (
                  <li key={c}>Cohorte {c}: <strong>{formatoNota(v)}</strong></li>
                ))}
              </ul>
            )}
            {ag.tendencia !== null && (
              <p className="mt-1 text-xs text-slate-600">
                Tendencia: {ag.tendencia > 0 ? '+' : ''}{ag.tendencia.toFixed(1).replace('.', ',')} entre cohortes
              </p>
            )}
          </Cifra>
        </div>
        <p className="mt-3 text-xs text-slate-600">Solo se incluyen las evaluaciones publicadas.</p>
      </Seccion>

      <Seccion id="h-res" titulo="Resumen y evolución">
        <p className="text-slate-800">{si.resumen}</p>
        <h3 className="mt-3 text-sm font-semibold text-slate-800">Evolución</h3>
        <p className="text-slate-800">{si.evolucion}</p>
        <p className="mt-3 text-xs italic text-slate-600">Texto generado con IA; las cifras las calcula el sistema.</p>
      </Seccion>

      <Seccion id="h-evo" titulo="Evolución de notas por laboratorio">
        <GraficoEvolucion laboratorios={ag.laboratorios} />
      </Seccion>

      <Seccion id="h-comp" titulo="Competencias">
        <BarrasCompetencias competencias={ag.competencias} />
      </Seccion>

      <Seccion id="h-labs" titulo="Laboratorios">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[32rem] text-left text-sm">
            <caption className="sr-only">Laboratorios evaluados con su nota final</caption>
            <thead>
              <tr className="border-b border-slate-300 text-slate-700">
                <th scope="col" className="py-2 pr-3">Código</th>
                <th scope="col" className="py-2 pr-3">Laboratorio</th>
                <th scope="col" className="py-2 pr-3">Cohorte</th>
                <th scope="col" className="py-2 pr-3">Nota final</th>
                <th scope="col" className="py-2">Evaluación</th>
              </tr>
            </thead>
            <tbody>
              {ag.laboratorios.map((l) => (
                <tr key={l.evaluacion_id} className="border-b border-slate-100">
                  <td className="py-2 pr-3 font-medium">{l.codigo}</td>
                  <td className="py-2 pr-3">{l.titulo}</td>
                  <td className="py-2 pr-3">{l.cohorte}</td>
                  <td className="py-2 pr-3 font-semibold text-tinta">{formatoNota(l.nota_final)}</td>
                  <td className="py-2">
                    <Link to={`/evaluaciones/${l.evaluacion_id}`} className="text-marca underline">Ver evaluación</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Seccion>

      <Seccion id="h-temas" titulo="Temas, aprendizajes y qué fortalecer">
        {ag.temas.length === 0 && <p className="text-sm text-slate-600">No hay temas registrados.</p>}
        <ul className="grid gap-3 lg:grid-cols-2">
          {ag.temas.map((t) => (
            <li key={t.tema} className="rounded border border-slate-200 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold capitalize text-tinta">{t.tema}</h3>
                <InsigniaDominio nivel={t.nivel_dominio} />
              </div>
              <p className="text-xs text-slate-600">
                {informe.temas_categoria[t.tema] ?? 'Sin categoría'}
                {t.promedio !== null && <> · Promedio {formatoNota(t.promedio)}</>}
                {t.laboratorios.length > 0 && <> · {t.laboratorios.join(', ')}</>}
              </p>
              {t.nivel_dominio === null && t.laboratorios_sin_evidencia.length > 0 && (
                <p className="mt-1 text-sm text-slate-700">Sin evaluación publicada en: {t.laboratorios_sin_evidencia.join(', ')}.</p>
              )}
              {t.aprendizajes.length > 0 && (
                <div className="mt-2">
                  <h4 className="text-sm font-semibold text-slate-800">Aprendizajes</h4>
                  <ul className="list-disc pl-5 text-sm text-slate-700">
                    {t.aprendizajes.map((a, i) => (
                      <li key={i}><span className="font-medium">{a.laboratorio}:</span> {a.que_aprendio}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="mt-2">
                <Lista titulo="Qué fortalecer" items={t.que_fortalecer} />
              </div>
            </li>
          ))}
        </ul>
      </Seccion>

      <Seccion id="h-brechas" titulo="Brechas destacadas">
        {ag.brechas.length === 0 ? (
          <p className="text-sm text-slate-600">No se detectaron brechas.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {ag.brechas.map((b, i) => (
              <li key={i} className="py-2 text-sm">
                <Insignia tono={b.tipo === 'sin_evidencia' ? 'gris' : 'ambar'}>{ETIQUETA_BRECHA[b.tipo] ?? b.tipo}</Insignia>{' '}
                <strong>{b.nombre}</strong>
                <p className="text-slate-700">{b.detalle}</p>
              </li>
            ))}
          </ul>
        )}
      </Seccion>

      <Seccion id="h-plan" titulo="Plan de fortalecimiento">
        <ol className="grid gap-3 lg:grid-cols-2">
          {plan.map((a, i) => (
            <li key={i} className="rounded border border-slate-200 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <Insignia tono={a.prioridad <= 2 ? 'rojo' : a.prioridad === 3 ? 'ambar' : 'azul'}>Prioridad {a.prioridad}</Insignia>
                <h3 className="font-semibold capitalize text-tinta">{a.tema}</h3>
              </div>
              <p className="mt-2 text-sm text-slate-800"><strong>Objetivo:</strong> {a.objetivo}</p>
              <div className="mt-2"><Lista titulo="Actividades" items={a.actividades} /></div>
              <div className="mt-2"><Lista titulo="Recursos" items={a.recursos} /></div>
              <p className="mt-2 text-sm text-slate-800"><strong>Indicador de logro:</strong> {a.indicador_logro}</p>
              <p className="text-sm text-slate-800"><strong>Plazo:</strong> {a.plazo_semanas} {a.plazo_semanas === 1 ? 'semana' : 'semanas'}</p>
            </li>
          ))}
        </ol>
        <p className="mt-3 text-xs italic text-slate-600">Plan propuesto con IA; revísalo con tu docente.</p>
      </Seccion>

      {esDocente && (
        <Seccion id="h-traza" titulo="Trazabilidad">
          <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
            <div><dt className="inline font-semibold">Proveedor: </dt><dd className="inline">{informe.proveedor ?? '—'}</dd></div>
            <div><dt className="inline font-semibold">Modelo: </dt><dd className="inline">{informe.modelo ?? '—'}</dd></div>
            <div><dt className="inline font-semibold">Versión del prompt: </dt><dd className="inline">{informe.version_prompt ?? '—'}</dd></div>
            <div><dt className="inline font-semibold">Costo estimado: </dt><dd className="inline">{typeof informe.costo_usd_estimado === 'number' ? `US$ ${informe.costo_usd_estimado.toFixed(4)}` : '—'}</dd></div>
            <div><dt className="inline font-semibold">Generado por: </dt><dd className="inline">{informe.generado_por.nombre}</dd></div>
            <div><dt className="inline font-semibold">Evaluaciones incluidas: </dt><dd className="inline">{informe.evaluaciones_incluidas.join(', ') || '—'}</dd></div>
          </dl>
          {informe.advertencias && informe.advertencias.length > 0 && (
            <div className="mt-3 space-y-2">
              {informe.advertencias.map((w, i) => (
                <Aviso key={i} tipo="advertencia">{w}</Aviso>
              ))}
            </div>
          )}
        </Seccion>
      )}
    </div>
  )
}

function Contenido({ estudianteId, esDocente }: { estudianteId: number; esDocente: boolean }) {
  const { lista, error, procesando, recargar } = useInformes(estudianteId)
  const [generando, setGenerando] = useState(false)
  const [errorAccion, setErrorAccion] = useState<string | null>(null)
  const [elegido, setElegido] = useState<number | null>(null)
  const [detalle, setDetalle] = useState<TipoInforme | null>(null)
  const [errorDetalle, setErrorDetalle] = useState<string | null>(null)

  const listos = (lista ?? []).filter((i) => i.estado === 'listo')
  const verId = elegido !== null && listos.some((i) => i.id === elegido) ? elegido : (listos[0]?.id ?? null)

  useEffect(() => {
    if (verId === null) return
    let activo = true
    obtenerInforme(verId)
      .then((i) => {
        if (!activo) return
        setDetalle(i)
        setErrorDetalle(null)
      })
      .catch((e) => activo && setErrorDetalle(mensajeError(e)))
    return () => {
      activo = false
    }
  }, [verId])

  async function generar() {
    setGenerando(true)
    setErrorAccion(null)
    try {
      await generarInforme(estudianteId)
    } catch (e) {
      if (!(e instanceof ErrorApi && e.estado === 409)) setErrorAccion(mensajeError(e))
    } finally {
      await recargar()
      setGenerando(false)
    }
  }

  const tono = (e: InformeResumen['estado']) => (e === 'listo' ? 'verde' : e === 'error' ? 'rojo' : 'azul')
  const etiqueta = (e: InformeResumen['estado']) => (e === 'listo' ? 'Listo' : e === 'error' ? 'Error' : 'Procesando')

  return (
    <div className="mt-6 space-y-6">
      <section className={tarjeta} aria-labelledby="h-gen">
        <h2 id="h-gen" className="text-lg font-semibold text-tinta">Generar informe</h2>
        <p className="mt-1 text-sm text-slate-700">
          El informe solo usa evaluaciones <strong>publicadas</strong>: lo que aún está en revisión o sin publicar no se incluye.
          Puede tardar unos segundos y se actualiza solo.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button type="button" className={botonPrim} disabled={generando || procesando} onClick={() => void generar()}>
            {generando ? 'Iniciando…' : 'Generar informe'}
          </button>
        </div>
        <div className="mt-3" aria-live="polite">
          {procesando && <Aviso tipo="advertencia">Generando informe… se actualiza automáticamente cada 3 segundos.</Aviso>}
        </div>
        {(errorAccion || error) && <div className="mt-2"><Aviso tipo="error">{errorAccion ?? error}</Aviso></div>}

        <h3 className="mt-4 text-sm font-semibold text-slate-800">Historial</h3>
        {lista === null && !error && <p className="text-sm text-slate-600">Cargando…</p>}
        {lista?.length === 0 && <p className="text-sm text-slate-600">Aún no hay informes generados.</p>}
        <ul className="mt-1 divide-y divide-slate-100">
          {lista?.map((i) => (
            <li key={i.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
              <Insignia tono={tono(i.estado)}>{etiqueta(i.estado)}</Insignia>
              <span>{formatoFecha(i.generado_en)}</span>
              <span className="text-slate-600">{i.evaluaciones_incluidas.length} evaluaciones</span>
              {i.promedio_general !== null && <span>Promedio <strong>{formatoNota(i.promedio_general)}</strong></span>}
              {i.estado === 'listo' &&
                (i.id === verId ? (
                  <span className="text-slate-600">(mostrando)</span>
                ) : (
                  <button type="button" className="text-marca underline" onClick={() => setElegido(i.id)}>Ver este informe</button>
                ))}
              {i.estado === 'error' && i.error && <span role="alert" className="text-red-800">{i.error}</span>}
            </li>
          ))}
        </ul>
      </section>

      {errorDetalle && <Aviso tipo="error">{errorDetalle}</Aviso>}
      {lista !== null && verId === null && !procesando && (
        <Aviso tipo="advertencia">Todavía no hay un informe listo. Genera uno con el botón de arriba.</Aviso>
      )}
      {detalle && verId !== null && detalle.id === verId && <VistaInforme informe={detalle} esDocente={esDocente} />}
    </div>
  )
}

export default function Informe() {
  const { usuario } = useAuth()
  const { esEstudiante, estudiantes, seleccion, setSeleccion, estudianteId, error } = useEstudianteActivo()

  return (
    <section className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10">
      <h1 className="font-display text-[1.95rem] font-semibold leading-tight text-tinta">Informe integral</h1>
      <p className="mt-1 text-sm text-slate-600">Resumen del aprendizaje a lo largo de las cohortes 1 y 2, descargable en PDF.</p>

      {!esEstudiante && (
        <div className="mt-4">
          <SelectorEstudiante id="inf-est" estudiantes={estudiantes} valor={seleccion} alCambiar={setSeleccion} error={error} />
        </div>
      )}
      {!esEstudiante && estudianteId === null && !error && <p className="mt-6 text-slate-600">Elige un estudiante para ver o generar su informe.</p>}

      {estudianteId !== null && <Contenido key={estudianteId} estudianteId={estudianteId} esDocente={usuario?.rol !== 'estudiante'} />}
    </section>
  )
}

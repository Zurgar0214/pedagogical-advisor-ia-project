import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  crearVersionRubrica,
  obtenerLaboratorio,
  obtenerRubricasLaboratorio,
  obtenerVersionRubrica,
  validarRubrica,
  type CriterioRubrica,
  type Laboratorio,
  type RubricaContenido,
  type RubricaVersion,
} from '../api/iteracion2'
import { botonPrim, botonSec, campo, formatoFecha, mensajeError, tarjeta } from '../componentes/estilos'
import { Aviso, Insignia } from '../componentes/ui'
import ImportarRubrica from '../componentes/ImportarRubrica'

const PLANTILLA: RubricaContenido = {
  competencias: [{ id: 'c1', nombre: 'Competencia 1', descripcion: '' }],
  criterios: [
    {
      id: 'k1',
      nombre: 'Criterio 1',
      descripcion: '',
      competencia_id: 'c1',
      peso: 100,
      niveles: [
        { nombre: 'Insuficiente', descriptor: '', valor: 1.0 },
        { nombre: 'Básico', descriptor: '', valor: 3.0 },
        { nombre: 'Competente', descriptor: '', valor: 4.0 },
        { nombre: 'Sobresaliente', descriptor: '', valor: 5.0 },
      ],
    },
  ],
}

const copia = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T

function mover<T>(arr: T[], i: number, d: number): T[] {
  const j = i + d
  if (j < 0 || j >= arr.length) return arr
  const r = [...arr]
  ;[r[i], r[j]] = [r[j], r[i]]
  return r
}

function idLibre(prefijo: string, usados: string[]): string {
  let n = usados.length + 1
  while (usados.includes(`${prefijo}${n}`)) n++
  return `${prefijo}${n}`
}

const redondear = (n: number) => Math.round(n * 100) / 100

export default function RubricaEditor() {
  const { id } = useParams()
  const labId = Number(id)
  const [lab, setLab] = useState<Laboratorio | null>(null)
  const [versiones, setVersiones] = useState<RubricaVersion[]>([])
  const [contenido, setContenido] = useState<RubricaContenido | null>(null)
  const [baseNumero, setBaseNumero] = useState<number | null>(null)
  const [vista, setVista] = useState<RubricaVersion | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [aviso, setAviso] = useState<{ tipo: 'ok' | 'advertencia'; texto: string } | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [errorGuardar, setErrorGuardar] = useState<string | null>(null)

  const [inconsistencias, setInconsistencias] = useState<string[] | null>(null)
  const [validaServidor, setValidaServidor] = useState<boolean | null>(null)
  const [validando, setValidando] = useState(false)
  const [errorValidar, setErrorValidar] = useState<string | null>(null)
  const [pedirValidar, setPedirValidar] = useState(0)
  const [importando, setImportando] = useState(false)
  const [sucio, setSucio] = useState(false)

  const cargar = useCallback(async () => {
    try {
      const [l, r] = await Promise.all([obtenerLaboratorio(labId), obtenerRubricasLaboratorio(labId)])
      setLab(l)
      setVersiones(r.versiones)
      return r
    } catch (e) {
      setError(mensajeError(e))
      return null
    }
  }, [labId])

  useEffect(() => {
    let activo = true
    Promise.all([obtenerLaboratorio(labId), obtenerRubricasLaboratorio(labId)]).then(([l, r]) => {
      if (!activo) return
      setLab(l)
      setVersiones(r.versiones)
      if (r.vigente?.contenido) {
        setContenido(copia(r.vigente.contenido))
        setBaseNumero(r.vigente.numero)
      } else {
        setContenido(copia(PLANTILLA))
      }
      setCargando(false)
    }).catch((e) => {
      if (!activo) return
      setError(mensajeError(e))
      setCargando(false)
    })
    return () => {
      activo = false
    }
  }, [labId])

  const sumaPesos = useMemo(() => redondear((contenido?.criterios ?? []).reduce((s, c) => s + (Number.isFinite(c.peso) ? c.peso : 0), 0)), [contenido])
  const pesosOk = sumaPesos === 100

  // Validación en el servidor con debounce al editar (o manual con el botón).
  useEffect(() => {
    if (!contenido) return
    let activo = true
    const t = setTimeout(() => {
      setValidando(true)
      validarRubrica(contenido)
        .then((r) => {
          if (!activo) return
          setInconsistencias(r.inconsistencias)
          setValidaServidor(r.valida)
          setErrorValidar(null)
        })
        .catch((e) => activo && setErrorValidar(mensajeError(e)))
        .finally(() => activo && setValidando(false))
    }, 900)
    return () => {
      activo = false
      clearTimeout(t)
    }
  }, [contenido, pedirValidar])

  function cambiar(fn: (c: RubricaContenido) => void) {
    setContenido((prev) => {
      if (!prev) return prev
      const n = copia(prev)
      fn(n)
      return n
    })
    setSucio(true)
    setAviso(null)
  }

  function cargarImportada(r: RubricaContenido) {
    setContenido(copia(r))
    setSucio(true) // propuesta de la IA sin guardar
    setImportando(false)
    setVista(null)
    setAviso({
      tipo: 'advertencia',
      texto: 'Se cargó la propuesta de la IA en el editor. Revísala: la IA puede equivocarse. Nada se guarda hasta que pulses «Guardar como nueva versión».',
    })
    document.getElementById('editor-rubrica')?.scrollIntoView({ behavior: 'smooth' })
  }

  function cambiarCriterio(i: number, fn: (c: CriterioRubrica) => void) {
    cambiar((c) => fn(c.criterios[i]))
  }

  async function guardar() {
    if (!contenido) return
    setGuardando(true)
    setErrorGuardar(null)
    try {
      const v = await crearVersionRubrica(labId, contenido)
      setAviso(
        v.valida
          ? { tipo: 'ok', texto: `Se guardó la versión ${v.numero}. Es válida y quedó vigente para nuevas entregas.` }
          : {
              tipo: 'advertencia',
              texto: `Se guardó la versión ${v.numero}, pero tiene inconsistencias: no se podrá usar para entregas mientras no sea válida.`,
            },
      )
      setBaseNumero(v.numero)
      setSucio(false)
      await cargar()
    } catch (e) {
      setErrorGuardar(mensajeError(e))
    } finally {
      setGuardando(false)
    }
  }

  async function verVersion(v: RubricaVersion) {
    setErrorGuardar(null)
    try {
      setVista(await obtenerVersionRubrica(v.id))
    } catch (e) {
      setErrorGuardar(mensajeError(e))
    }
  }

  function usarComoBase(v: RubricaVersion) {
    if (!v.contenido) return
    setContenido(copia(v.contenido))
    setBaseNumero(v.numero)
    setSucio(false)
    setVista(null)
    setAviso({ tipo: 'ok', texto: `Se cargó la versión ${v.numero} en el editor. Guarda para crear una nueva versión.` })
    document.getElementById('editor-rubrica')?.scrollIntoView({ behavior: 'smooth' })
  }

  if (!Number.isInteger(labId)) return <p className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10 text-red-800">Laboratorio no válido.</p>
  if (cargando) return <p role="status" className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10 text-slate-600">Cargando rúbrica…</p>
  if (error || !contenido) return (
    <section className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10">
      <Aviso tipo="error">{error ?? 'No se pudo cargar la rúbrica.'}</Aviso>
      <Link to="/laboratorios" className="mt-4 inline-block text-marca underline">Volver a laboratorios</Link>
    </section>
  )

  const compIds = contenido.competencias.map((c) => c.id)

  return (
    <section className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10">
      <Link to="/laboratorios" className="text-sm text-marca underline">← Laboratorios</Link>
      <h1 className="mt-2 font-display text-[1.95rem] font-semibold leading-tight text-tinta">Rúbrica de {lab ? `${lab.codigo} · ${lab.titulo}` : 'laboratorio'}</h1>
      <p className="mt-1 text-sm text-slate-600">
        {baseNumero ? `Editando a partir de la versión ${baseNumero}.` : 'Aún no hay versiones; se parte de una plantilla inicial.'} Guardar siempre crea una versión nueva.
      </p>

      <div className="mt-3">
        <button type="button" className={botonSec} onClick={() => setImportando(true)}>Importar con IA (PDF o texto)</button>
      </div>
      {importando && (
        <ImportarRubrica requiereConfirmacion={sucio || baseNumero !== null} onCerrar={() => setImportando(false)} onCargar={cargarImportada} />
      )}

      <div aria-live="polite" className="mt-4 space-y-2">
        {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}
        {errorGuardar && <Aviso tipo="error">{errorGuardar}</Aviso>}
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div id="editor-rubrica" className="min-w-0 space-y-6">
          {/* Competencias */}
          <section className={tarjeta} aria-labelledby="h-comp">
            <div className="flex items-center justify-between">
              <h2 id="h-comp" className="text-lg font-semibold text-tinta">Competencias</h2>
              <button type="button" className={botonSec} onClick={() => cambiar((c) => c.competencias.push({ id: idLibre('c', compIds), nombre: '', descripcion: '' }))}>
                Agregar competencia
              </button>
            </div>
            {contenido.competencias.length === 0 && <p className="mt-3 text-sm text-slate-600">No hay competencias.</p>}
            <ul className="mt-3 space-y-3">
              {contenido.competencias.map((comp, i) => (
                <li key={i} className="rounded border border-slate-200 bg-slate-50 p-3">
                  <div className="grid gap-3 sm:grid-cols-[8rem_1fr]">
                    <div>
                      <label htmlFor={`comp-id-${i}`} className="block text-sm font-medium text-slate-800">Id</label>
                      <input id={`comp-id-${i}`} value={comp.id} onChange={(e) => cambiar((c) => (c.competencias[i].id = e.target.value))} className={campo} />
                    </div>
                    <div>
                      <label htmlFor={`comp-nom-${i}`} className="block text-sm font-medium text-slate-800">Nombre</label>
                      <input id={`comp-nom-${i}`} value={comp.nombre} onChange={(e) => cambiar((c) => (c.competencias[i].nombre = e.target.value))} className={campo} />
                    </div>
                  </div>
                  <label htmlFor={`comp-desc-${i}`} className="mt-3 block text-sm font-medium text-slate-800">Descripción</label>
                  <textarea id={`comp-desc-${i}`} rows={2} value={comp.descripcion} onChange={(e) => cambiar((c) => (c.competencias[i].descripcion = e.target.value))} className={campo} />
                  <div className="mt-2 flex gap-2">
                    <button type="button" className={botonSec} disabled={i === 0} onClick={() => cambiar((c) => (c.competencias = mover(c.competencias, i, -1)))} aria-label={`Subir competencia ${comp.nombre || comp.id}`}>↑</button>
                    <button type="button" className={botonSec} disabled={i === contenido.competencias.length - 1} onClick={() => cambiar((c) => (c.competencias = mover(c.competencias, i, 1)))} aria-label={`Bajar competencia ${comp.nombre || comp.id}`}>↓</button>
                    <button type="button" className={botonSec} onClick={() => cambiar((c) => c.competencias.splice(i, 1))} aria-label={`Quitar competencia ${comp.nombre || comp.id}`}>Quitar</button>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          {/* Criterios */}
          <section className={tarjeta} aria-labelledby="h-crit">
            <div className="flex items-center justify-between">
              <h2 id="h-crit" className="text-lg font-semibold text-tinta">Criterios</h2>
              <button
                type="button"
                className={botonSec}
                onClick={() =>
                  cambiar((c) =>
                    c.criterios.push({
                      id: idLibre('k', c.criterios.map((k) => k.id)),
                      nombre: '',
                      descripcion: '',
                      competencia_id: c.competencias[0]?.id ?? '',
                      peso: 0,
                      niveles: copia(PLANTILLA.criterios[0].niveles),
                    }),
                  )
                }
              >
                Agregar criterio
              </button>
            </div>
            {contenido.criterios.length === 0 && <p className="mt-3 text-sm text-slate-600">No hay criterios.</p>}
            <ul className="mt-3 space-y-4">
              {contenido.criterios.map((cr, i) => (
                <li key={i} className="rounded border border-slate-300 p-3">
                  <div className="grid gap-3 sm:grid-cols-[6rem_1fr_7rem]">
                    <div>
                      <label htmlFor={`cr-id-${i}`} className="block text-sm font-medium text-slate-800">Id</label>
                      <input id={`cr-id-${i}`} value={cr.id} onChange={(e) => cambiarCriterio(i, (k) => (k.id = e.target.value))} className={campo} />
                    </div>
                    <div>
                      <label htmlFor={`cr-nom-${i}`} className="block text-sm font-medium text-slate-800">Nombre</label>
                      <input id={`cr-nom-${i}`} value={cr.nombre} onChange={(e) => cambiarCriterio(i, (k) => (k.nombre = e.target.value))} className={campo} />
                    </div>
                    <div>
                      <label htmlFor={`cr-peso-${i}`} className="block text-sm font-medium text-slate-800">Peso (%)</label>
                      <input id={`cr-peso-${i}`} type="number" min={0} max={100} step="any" value={cr.peso} onChange={(e) => cambiarCriterio(i, (k) => (k.peso = e.target.value === '' ? 0 : Number(e.target.value)))} className={campo} />
                    </div>
                  </div>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <div>
                      <label htmlFor={`cr-comp-${i}`} className="block text-sm font-medium text-slate-800">Competencia</label>
                      <select id={`cr-comp-${i}`} value={cr.competencia_id} onChange={(e) => cambiarCriterio(i, (k) => (k.competencia_id = e.target.value))} className={campo}>
                        {!compIds.includes(cr.competencia_id) && <option value={cr.competencia_id}>{cr.competencia_id || '(sin competencia)'} — no existe</option>}
                        {contenido.competencias.map((c) => (
                          <option key={c.id} value={c.id}>{c.nombre || c.id}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label htmlFor={`cr-desc-${i}`} className="block text-sm font-medium text-slate-800">Descripción</label>
                      <textarea id={`cr-desc-${i}`} rows={2} value={cr.descripcion} onChange={(e) => cambiarCriterio(i, (k) => (k.descripcion = e.target.value))} className={campo} />
                    </div>
                  </div>

                  <fieldset className="mt-3">
                    <legend className="text-sm font-semibold text-slate-800">Niveles de desempeño (valor 0–5)</legend>
                    <ul className="mt-2 space-y-2">
                      {cr.niveles.map((n, j) => (
                        <li key={j} className="grid gap-2 rounded bg-slate-50 p-2 sm:grid-cols-[10rem_1fr_6rem_auto]">
                          <div>
                            <label htmlFor={`n-nom-${i}-${j}`} className="block text-xs font-medium text-slate-700">Nombre</label>
                            <input id={`n-nom-${i}-${j}`} value={n.nombre} onChange={(e) => cambiarCriterio(i, (k) => (k.niveles[j].nombre = e.target.value))} className={campo} />
                          </div>
                          <div>
                            <label htmlFor={`n-des-${i}-${j}`} className="block text-xs font-medium text-slate-700">Descriptor</label>
                            <input id={`n-des-${i}-${j}`} value={n.descriptor} onChange={(e) => cambiarCriterio(i, (k) => (k.niveles[j].descriptor = e.target.value))} className={campo} />
                          </div>
                          <div>
                            <label htmlFor={`n-val-${i}-${j}`} className="block text-xs font-medium text-slate-700">Valor</label>
                            <input id={`n-val-${i}-${j}`} type="number" min={0} max={5} step="0.1" value={n.valor} onChange={(e) => cambiarCriterio(i, (k) => (k.niveles[j].valor = e.target.value === '' ? 0 : Number(e.target.value)))} className={campo} />
                          </div>
                          <div className="flex items-end gap-1">
                            <button type="button" className={botonSec} disabled={j === 0} onClick={() => cambiarCriterio(i, (k) => (k.niveles = mover(k.niveles, j, -1)))} aria-label={`Subir nivel ${n.nombre || j + 1}`}>↑</button>
                            <button type="button" className={botonSec} disabled={j === cr.niveles.length - 1} onClick={() => cambiarCriterio(i, (k) => (k.niveles = mover(k.niveles, j, 1)))} aria-label={`Bajar nivel ${n.nombre || j + 1}`}>↓</button>
                            <button type="button" className={botonSec} onClick={() => cambiarCriterio(i, (k) => k.niveles.splice(j, 1))} aria-label={`Quitar nivel ${n.nombre || j + 1}`}>×</button>
                          </div>
                        </li>
                      ))}
                    </ul>
                    <button type="button" className={`${botonSec} mt-2`} onClick={() => cambiarCriterio(i, (k) => k.niveles.push({ nombre: '', descriptor: '', valor: 0 }))}>
                      Agregar nivel
                    </button>
                  </fieldset>

                  <div className="mt-3 flex gap-2 border-t border-slate-200 pt-3">
                    <button type="button" className={botonSec} disabled={i === 0} onClick={() => cambiar((c) => (c.criterios = mover(c.criterios, i, -1)))} aria-label={`Subir criterio ${cr.nombre || cr.id}`}>↑</button>
                    <button type="button" className={botonSec} disabled={i === contenido.criterios.length - 1} onClick={() => cambiar((c) => (c.criterios = mover(c.criterios, i, 1)))} aria-label={`Bajar criterio ${cr.nombre || cr.id}`}>↓</button>
                    <button type="button" className={botonSec} onClick={() => cambiar((c) => c.criterios.splice(i, 1))} aria-label={`Quitar criterio ${cr.nombre || cr.id}`}>Quitar criterio</button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <aside className="space-y-6 lg:sticky lg:top-4 lg:self-start" aria-label="Validación y versiones">
          <section className={tarjeta} aria-labelledby="h-val">
            <h2 id="h-val" className="text-lg font-semibold text-tinta">Validación</h2>
            <p className={`mt-2 rounded px-3 py-2 text-sm font-semibold ${pesosOk ? 'bg-emerald-100 text-emerald-900' : 'bg-red-100 text-red-900'}`} role="status">
              Suma de pesos: {sumaPesos} % {pesosOk ? '✓' : '(debe ser 100 %)'}
            </p>
            <button type="button" className={`${botonSec} mt-3`} onClick={() => setPedirValidar((n) => n + 1)} disabled={validando}>
              {validando ? 'Validando…' : 'Validar'}
            </button>
            {errorValidar && <div className="mt-3"><Aviso tipo="error">{errorValidar}</Aviso></div>}
            {validaServidor !== null && !errorValidar && (
              <div className="mt-3 text-sm" aria-live="polite">
                {validaServidor ? (
                  <Aviso tipo="ok">El servidor no encontró inconsistencias.</Aviso>
                ) : (
                  <div role="alert" className="rounded border border-red-300 bg-red-50 px-3 py-2 text-red-800">
                    <p className="font-semibold">Inconsistencias ({inconsistencias?.length ?? 0})</p>
                    <ul className="mt-1 list-disc space-y-1 pl-5">
                      {inconsistencias?.map((m, k) => <li key={k}>{m}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            )}
            <button type="button" className={`${botonPrim} mt-4 w-full`} onClick={guardar} disabled={guardando}>
              {guardando ? 'Guardando…' : 'Guardar como nueva versión'}
            </button>
            <p className="mt-2 text-xs text-slate-600">
              Se guarda aunque tenga inconsistencias, pero una versión inválida no se podrá usar para entregas.
            </p>
          </section>

          <section className={tarjeta} aria-labelledby="h-hist">
            <h2 id="h-hist" className="text-lg font-semibold text-tinta">Historial de versiones</h2>
            {versiones.length === 0 && <p className="mt-2 text-sm text-slate-600">Sin versiones guardadas.</p>}
            <ul className="mt-2 divide-y divide-slate-100">
              {[...versiones].sort((a, b) => b.numero - a.numero).map((v) => (
                <li key={v.id} className="py-2 text-sm">
                  <p className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">Versión {v.numero}</span>
                    {v.valida ? <Insignia tono="verde">Válida</Insignia> : <Insignia tono="rojo">Inválida</Insignia>}
                  </p>
                  <p className="text-xs text-slate-600">{formatoFecha(v.creado_en)} · {v.creado_por.nombre}</p>
                  <div className="mt-1 flex gap-2">
                    <button type="button" className={botonSec} onClick={() => verVersion(v)} aria-label={`Ver versión ${v.numero}`}>Ver</button>
                    <button
                      type="button"
                      className={botonSec}
                      onClick={async () => {
                        try {
                          usarComoBase(await obtenerVersionRubrica(v.id))
                        } catch (e) {
                          setErrorGuardar(mensajeError(e))
                        }
                      }}
                      aria-label={`Usar versión ${v.numero} como base`}
                    >
                      Usar como base
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>

      {vista?.contenido && (
        <section className={`${tarjeta} mt-6`} aria-labelledby="h-vista">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="h-vista" className="text-lg font-semibold text-tinta">Versión {vista.numero} (solo lectura)</h2>
            <div className="flex gap-2">
              <button type="button" className={botonSec} onClick={() => usarComoBase(vista)}>Usar como base</button>
              <button type="button" className={botonSec} onClick={() => setVista(null)}>Cerrar</button>
            </div>
          </div>
          {vista.inconsistencias.length > 0 && (
            <div className="mt-3"><Aviso tipo="advertencia">Inconsistencias: {vista.inconsistencias.join(' · ')}</Aviso></div>
          )}
          <h3 className="mt-3 font-semibold text-slate-800">Competencias</h3>
          <ul className="mt-1 list-disc pl-5 text-sm">
            {vista.contenido.competencias.map((c) => (
              <li key={c.id}><strong>{c.nombre}</strong> ({c.id}){c.descripcion && ` — ${c.descripcion}`}</li>
            ))}
          </ul>
          <h3 className="mt-3 font-semibold text-slate-800">Criterios</h3>
          <div className="mt-1 space-y-3">
            {vista.contenido.criterios.map((c) => (
              <div key={c.id} className="rounded border border-slate-200 p-3 text-sm">
                <p><strong>{c.nombre}</strong> ({c.id}) · competencia {c.competencia_id} · peso {c.peso} %</p>
                {c.descripcion && <p className="text-slate-700">{c.descripcion}</p>}
                <ul className="mt-1 list-disc pl-5">
                  {c.niveles.map((n, k) => (
                    <li key={k}>{n.nombre} ({n.valor.toFixed(1)}){n.descriptor && `: ${n.descriptor}`}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}
    </section>
  )
}

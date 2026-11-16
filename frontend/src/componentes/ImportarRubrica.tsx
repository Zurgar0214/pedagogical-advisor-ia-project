import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import {
  interpretarRubrica,
  LIMITE_PDF_BYTES,
  TEXTO_MAX,
  TEXTO_MIN,
  type PropuestaRubrica,
} from '../api/iteracion5'
import type { RubricaContenido } from '../api/iteracion2'
import { botonPrim, botonSec, campo, formatoTamano, mensajeError } from './estilos'
import { Aviso, Insignia } from './ui'

interface Props {
  /** Si el editor tiene contenido que se perdería al cargar la propuesta, se pide confirmación. */
  requiereConfirmacion: boolean
  onCerrar: () => void
  onCargar: (rubrica: RubricaContenido) => void
}

type Pestana = 'pdf' | 'texto'

const FOCUSABLES = 'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

export default function ImportarRubrica({ requiereConfirmacion, onCerrar, onCargar }: Props) {
  const [pestana, setPestana] = useState<Pestana>('pdf')
  const [archivo, setArchivo] = useState<File | null>(null)
  const [errorArchivo, setErrorArchivo] = useState<string | null>(null)
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [propuesta, setPropuesta] = useState<PropuestaRubrica | null>(null)
  const [confirmando, setConfirmando] = useState(false)
  const dialogo = useRef<HTMLDivElement>(null)
  const previo = useRef<Element | null>(null)

  // Foco inicial y restauración al cerrar; bloquea el scroll del fondo.
  useEffect(() => {
    previo.current = document.activeElement
    dialogo.current?.querySelector<HTMLElement>(FOCUSABLES)?.focus()
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = overflow
      if (previo.current instanceof HTMLElement) previo.current.focus()
    }
  }, [])

  function alTeclado(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'Escape') {
      if (enviando) return
      e.stopPropagation()
      onCerrar()
      return
    }
    if (e.key !== 'Tab') return
    const items = Array.from(dialogo.current?.querySelectorAll<HTMLElement>(FOCUSABLES) ?? [])
    if (items.length === 0) return
    const primero = items[0]
    const ultimo = items[items.length - 1]
    const activo = document.activeElement
    if (e.shiftKey && (activo === primero || !dialogo.current?.contains(activo))) {
      e.preventDefault()
      ultimo.focus()
    } else if (!e.shiftKey && (activo === ultimo || !dialogo.current?.contains(activo))) {
      e.preventDefault()
      primero.focus()
    }
  }

  function elegirArchivo(f: File | null) {
    setError(null)
    if (!f) {
      setArchivo(null)
      setErrorArchivo(null)
      return
    }
    if (!f.name.toLowerCase().endsWith('.pdf') && f.type !== 'application/pdf') {
      setArchivo(null)
      setErrorArchivo('El archivo debe ser un PDF.')
    } else if (f.size > LIMITE_PDF_BYTES) {
      setArchivo(null)
      setErrorArchivo(`El PDF pesa ${formatoTamano(f.size)} y el máximo es 10 MB.`)
    } else if (f.size === 0) {
      setArchivo(null)
      setErrorArchivo('El archivo está vacío.')
    } else {
      setArchivo(f)
      setErrorArchivo(null)
    }
  }

  const largo = texto.trim().length
  const textoOk = largo >= TEXTO_MIN && texto.length <= TEXTO_MAX
  const puedeEnviar = pestana === 'pdf' ? archivo !== null : textoOk

  async function enviar() {
    if (!puedeEnviar || enviando) return
    setEnviando(true)
    setError(null)
    setPropuesta(null)
    try {
      const r = await interpretarRubrica(pestana === 'pdf' && archivo ? { archivo } : { texto })
      setPropuesta(r)
    } catch (e) {
      setError(mensajeError(e))
    } finally {
      setEnviando(false)
    }
  }

  function cargar() {
    if (!propuesta) return
    if (requiereConfirmacion && !confirmando) {
      setConfirmando(true)
      return
    }
    onCargar(propuesta.rubrica)
  }

  const tabClase = (activa: boolean) =>
    `rounded-t border px-4 py-2 text-sm font-medium focus:outline-2 focus:outline-marca ${
      activa ? 'border-slate-300 border-b-white bg-white text-tinta' : 'border-transparent text-slate-600 hover:text-tinta'
    }`

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/60 p-4" onMouseDown={(e) => e.target === e.currentTarget && !enviando && onCerrar()}>
      <div
        ref={dialogo}
        role="dialog"
        aria-modal="true"
        aria-labelledby="imp-titulo"
        aria-busy={enviando}
        onKeyDown={alTeclado}
        className="my-6 w-full max-w-3xl rounded-lg bg-white p-5 shadow-xl"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="imp-titulo" className="font-serif text-xl font-semibold text-tinta">Importar rúbrica con IA</h2>
            <p className="mt-1 text-sm text-slate-700">
              Sube el PDF de la rúbrica o pega su texto. La IA propone una estructura; tú la revisas antes de guardar.
            </p>
          </div>
          <button type="button" className={botonSec} onClick={onCerrar} disabled={enviando} aria-label="Cerrar diálogo">✕</button>
        </div>

        <div role="tablist" aria-label="Origen de la rúbrica" className="mt-4 flex gap-1 border-b border-slate-300">
          {(['pdf', 'texto'] as const).map((p) => (
            <button
              key={p}
              type="button"
              role="tab"
              id={`tab-${p}`}
              aria-selected={pestana === p}
              aria-controls={`panel-${p}`}
              tabIndex={pestana === p ? 0 : -1}
              disabled={enviando}
              className={tabClase(pestana === p)}
              onClick={() => setPestana(p)}
              onKeyDown={(e) => {
                if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                  e.preventDefault()
                  const otro = p === 'pdf' ? 'texto' : 'pdf'
                  setPestana(otro)
                  document.getElementById(`tab-${otro}`)?.focus()
                }
              }}
            >
              {p === 'pdf' ? 'Subir PDF' : 'Pegar texto'}
            </button>
          ))}
        </div>

        {pestana === 'pdf' ? (
          <div role="tabpanel" id="panel-pdf" aria-labelledby="tab-pdf" className="mt-4">
            <label htmlFor="imp-archivo" className="block text-sm font-medium text-slate-800">Archivo PDF (máximo 10 MB)</label>
            <input
              id="imp-archivo"
              type="file"
              accept=".pdf,application/pdf"
              disabled={enviando}
              onChange={(e) => elegirArchivo(e.target.files?.[0] ?? null)}
              aria-describedby="imp-archivo-ayuda"
              className={campo}
            />
            <p id="imp-archivo-ayuda" className="mt-1 text-xs text-slate-600">El PDF debe tener texto seleccionable (no un escaneo) y no estar protegido con contraseña.</p>
            {archivo && <p className="mt-2 text-sm text-slate-800">Seleccionado: <strong>{archivo.name}</strong> ({formatoTamano(archivo.size)})</p>}
            {errorArchivo && <div className="mt-2"><Aviso tipo="error">{errorArchivo}</Aviso></div>}
          </div>
        ) : (
          <div role="tabpanel" id="panel-texto" aria-labelledby="tab-texto" className="mt-4">
            <label htmlFor="imp-texto" className="block text-sm font-medium text-slate-800">Texto de la rúbrica</label>
            <textarea
              id="imp-texto"
              rows={10}
              value={texto}
              disabled={enviando}
              onChange={(e) => {
                setTexto(e.target.value)
                setError(null)
              }}
              aria-describedby="imp-texto-contador"
              className={campo}
            />
            <p id="imp-texto-contador" className={`mt-1 text-xs ${textoOk || texto.length === 0 ? 'text-slate-600' : 'text-red-800'}`}>
              {texto.length.toLocaleString('es-CO')} / {TEXTO_MAX.toLocaleString('es-CO')} caracteres (mínimo {TEXTO_MIN}).
              {texto.length > TEXTO_MAX && ' Reduce el texto.'}
              {texto.length > 0 && largo < TEXTO_MIN && ' Aún es muy corto.'}
            </p>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button type="button" className={botonPrim} onClick={enviar} disabled={!puedeEnviar || enviando}>
            {enviando ? 'Interpretando…' : propuesta ? 'Interpretar de nuevo' : 'Interpretar con IA'}
          </button>
          <button type="button" className={botonSec} onClick={onCerrar} disabled={enviando}>Cancelar</button>
          {enviando && <p role="status" className="text-sm text-slate-700">La IA está leyendo la rúbrica… esto puede tardar unos segundos.</p>}
        </div>

        <div aria-live="polite" className="mt-4">
          {error && <Aviso tipo="error">{error}</Aviso>}
        </div>

        {propuesta && (
          <div className="mt-4 border-t border-slate-200 pt-4">
            <Aviso tipo="advertencia">
              Revisa la propuesta: la IA puede equivocarse. Nada se guarda hasta que pulses «Guardar como nueva versión».
            </Aviso>
            <Vista propuesta={propuesta} />

            {confirmando ? (
              <div role="alertdialog" aria-labelledby="imp-conf" className="mt-4 rounded border border-amber-400 bg-amber-50 p-3 text-sm text-amber-950">
                <p id="imp-conf" className="font-semibold">Esto reemplazará el contenido actual del editor (cambios sin guardar incluidos). ¿Continuar?</p>
                <div className="mt-2 flex gap-2">
                  <button type="button" className={botonPrim} onClick={() => onCargar(propuesta.rubrica)}>Sí, reemplazar</button>
                  <button type="button" className={botonSec} onClick={() => setConfirmando(false)}>No, volver</button>
                </div>
              </div>
            ) : (
              <div className="mt-4">
                <button type="button" className={botonPrim} onClick={cargar} disabled={enviando}>Cargar en el editor</button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function Vista({ propuesta }: { propuesta: PropuestaRubrica }) {
  const { rubrica, validacion, observaciones, advertencias } = propuesta
  const suma = Math.round(rubrica.criterios.reduce((s, c) => s + (Number.isFinite(c.peso) ? c.peso : 0), 0) * 100) / 100
  return (
    <div className="mt-3 space-y-4 text-sm">
      {advertencias.length > 0 && (
        <div role="alert" className="rounded border-2 border-amber-500 bg-amber-50 px-3 py-2 text-amber-950">
          <p className="font-semibold">Advertencias</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">{advertencias.map((a, i) => <li key={i}>{a}</li>)}</ul>
        </div>
      )}

      <div className={`rounded border px-3 py-2 ${validacion.valida ? 'border-emerald-300 bg-emerald-50 text-emerald-900' : 'border-red-300 bg-red-50 text-red-900'}`}>
        <p className="font-semibold">
          {validacion.valida ? 'Validación: sin inconsistencias' : `Validación: ${validacion.inconsistencias.length} inconsistencia(s)`}
          <span className="ml-2 font-normal">· suma de pesos {suma} %</span>
        </p>
        {!validacion.valida && (
          <ul className="mt-1 list-disc space-y-1 pl-5">{validacion.inconsistencias.map((m, i) => <li key={i}>{m}</li>)}</ul>
        )}
        {!validacion.valida && <p className="mt-1 text-xs">Podrás corregirlo en el editor antes de guardar.</p>}
      </div>

      {observaciones.length > 0 && (
        <div className="rounded border border-sky-300 bg-sky-50 px-3 py-2 text-sky-950">
          <p className="font-semibold">Observaciones de la IA</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">{observaciones.map((o, i) => <li key={i}>{o}</li>)}</ul>
        </div>
      )}

      <section aria-labelledby="imp-comp">
        <h3 id="imp-comp" className="font-semibold text-slate-800">Competencias ({rubrica.competencias.length})</h3>
        <ul className="mt-1 list-disc pl-5">
          {rubrica.competencias.map((c) => (
            <li key={c.id}><strong>{c.nombre}</strong> ({c.id}){c.descripcion && ` — ${c.descripcion}`}</li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="imp-crit">
        <h3 id="imp-crit" className="font-semibold text-slate-800">Criterios ({rubrica.criterios.length})</h3>
        <div className="mt-1 max-h-96 space-y-3 overflow-y-auto pr-1">
          {rubrica.criterios.map((c) => (
            <div key={c.id} className="rounded border border-slate-200 p-3">
              <p className="flex flex-wrap items-center gap-2">
                <strong>{c.nombre}</strong>
                <Insignia tono="azul">{c.peso} %</Insignia>
                <span className="text-xs text-slate-600">{c.id} · competencia {c.competencia_id}</span>
              </p>
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

      <p className="text-xs text-slate-600">
        Generado por {propuesta.proveedor} · {propuesta.modelo} · costo estimado US$ {propuesta.costo_usd_estimado.toFixed(4)}
      </p>
    </div>
  )
}

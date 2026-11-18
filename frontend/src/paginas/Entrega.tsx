import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  agregarRepositorio,
  borrarEvidencia,
  descargarEvidencia,
  obtenerEntrega,
  obtenerLaboratorio,
  subirEvidencia,
  type Entrega as TipoEntrega,
  type Evidencia,
  type Laboratorio,
  type TipoEvidencia,
} from '../api/iteracion2'
import { botonPrim, botonSec, campo, formatoFecha, formatoTamano, mensajeError, tarjeta } from '../componentes/estilos'
import { Aviso, Insignia } from '../componentes/ui'
import PanelEvaluacion from '../componentes/PanelEvaluacion'
import { useAuth } from '../auth/contexto'
import { ETIQUETA_ESTADO, ETIQUETA_FALTANTE, TONO_ESTADO } from './estadoEntrega'

const MB = 1024 * 1024

interface ReglaArchivo {
  tipo: Exclude<TipoEvidencia, 'repo_github'>
  titulo: string
  ayuda: string
  extensiones: string[]
  maxBytes: number
}

const REGLAS: ReglaArchivo[] = [
  { tipo: 'informe_pdf', titulo: 'Informe PDF (obligatorio)', ayuda: 'PDF con texto legible, máx. 20 MB. Solo uno por entrega.', extensiones: ['.pdf'], maxBytes: 20 * MB },
  { tipo: 'codigo_zip', titulo: 'Código en ZIP', ayuda: 'Archivo ZIP, máx. 50 MB. Obligatorio si no indicas un repositorio.', extensiones: ['.zip'], maxBytes: 50 * MB },
  { tipo: 'imagen', titulo: 'Imagen (opcional)', ayuda: 'PNG o JPEG, máx. 10 MB.', extensiones: ['.png', '.jpg', '.jpeg'], maxBytes: 10 * MB },
  { tipo: 'presentacion', titulo: 'Presentación (opcional)', ayuda: 'PDF o PPTX, máx. 50 MB.', extensiones: ['.pdf', '.pptx'], maxBytes: 50 * MB },
  { tipo: 'video', titulo: 'Video (opcional)', ayuda: 'MP4 o WEBM, máx. 50 MB.', extensiones: ['.mp4', '.webm'], maxBytes: 50 * MB },
]

const ETIQUETA_TIPO: Record<TipoEvidencia, string> = {
  informe_pdf: 'Informe PDF',
  codigo_zip: 'Código ZIP',
  repo_github: 'Repositorio GitHub',
  video: 'Video',
  presentacion: 'Presentación',
  imagen: 'Imagen',
}

const RE_REPO = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+?(\.git)?\/?$/

function validarArchivo(regla: ReglaArchivo, f: File): string | null {
  const nombre = f.name.toLowerCase()
  if (!regla.extensiones.some((e) => nombre.endsWith(e))) return `Formato no admitido. Se aceptan: ${regla.extensiones.join(', ')}.`
  if (f.size === 0) return 'El archivo está vacío.'
  if (f.size > regla.maxBytes) return `El archivo pesa ${formatoTamano(f.size)} y el máximo es ${formatoTamano(regla.maxBytes)}.`
  return null
}

function detalleTexto(e: Evidencia): string {
  const d = e.detalle ?? {}
  const partes: string[] = []
  const num = (k: string) => (typeof d[k] === 'number' ? (d[k] as number) : null)
  if (e.tipo === 'informe_pdf') {
    const p = num('paginas')
    const c = num('caracteres_texto')
    if (p !== null) partes.push(`${p} páginas`)
    if (c !== null) partes.push(`${c.toLocaleString('es-CO')} caracteres de texto`)
  } else if (e.tipo === 'codigo_zip') {
    const n = num('archivos') ?? num('num_archivos') ?? num('numero_archivos')
    if (n !== null) partes.push(`${n} archivos`)
    const t = num('tamano_descomprimido') ?? num('tamano_descomprimido_bytes')
    if (t !== null) partes.push(`${formatoTamano(t)} descomprimido`)
    const ext = d['extensiones']
    if (Array.isArray(ext) && ext.length) partes.push(`extensiones: ${ext.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(', ')}`)
  } else if (e.tipo === 'repo_github') {
    if (typeof d['owner'] === 'string' && typeof d['repo'] === 'string') partes.push(`${d['owner']}/${d['repo']}`)
  }
  return partes.join(' · ')
}

function ZonaCarga({ regla, entregaId, deshabilitado, alCargar }: { regla: ReglaArchivo; entregaId: number; deshabilitado: boolean; alCargar: (m: string) => void }) {
  const [archivo, setArchivo] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [progreso, setProgreso] = useState<number | null>(null)
  const [clave, setClave] = useState(0)
  const enviando = progreso !== null
  const idCampo = `archivo-${regla.tipo}`

  async function enviar(e: FormEvent) {
    e.preventDefault()
    if (!archivo) return setError('Selecciona un archivo.')
    const problema = validarArchivo(regla, archivo)
    if (problema) return setError(problema)
    setError(null)
    setProgreso(0)
    try {
      await subirEvidencia(entregaId, regla.tipo, archivo, setProgreso)
      setArchivo(null)
      setClave((n) => n + 1)
      alCargar(`${ETIQUETA_TIPO[regla.tipo]} cargado correctamente.`)
    } catch (err) {
      setError(mensajeError(err))
    } finally {
      setProgreso(null)
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="rounded border border-slate-200 bg-slate-50 p-3">
      <label htmlFor={idCampo} className="block text-sm font-semibold text-slate-800">{regla.titulo}</label>
      <p id={`${idCampo}-ayuda`} className="text-xs text-slate-600">{regla.ayuda}</p>
      <input
        key={clave}
        id={idCampo}
        type="file"
        accept={regla.extensiones.join(',')}
        disabled={deshabilitado || enviando}
        aria-describedby={`${idCampo}-ayuda`}
        onChange={(e) => {
          const f = e.target.files?.[0] ?? null
          setArchivo(f)
          setError(f ? validarArchivo(regla, f) : null)
        }}
        className="mt-2 block w-full text-sm file:mr-3 file:rounded file:border file:border-slate-400 file:bg-white file:px-2.5 file:py-1 focus:outline-2 focus:outline-marca"
      />
      {error && <p role="alert" className="mt-2 text-sm text-red-800">{error}</p>}
      {enviando && (
        <div className="mt-2" role="status">
          <progress value={progreso} max={100} className="w-full" aria-label={`Progreso de carga de ${regla.titulo}`} />
          <span className="text-xs text-slate-700">Enviando… {progreso} %{progreso === 100 ? ' (procesando en el servidor)' : ''}</span>
        </div>
      )}
      <button type="submit" disabled={deshabilitado || enviando || !archivo} className={`${botonPrim} mt-2`}>
        {enviando ? 'Enviando…' : 'Subir'}
      </button>
    </form>
  )
}

function ZonaRepo({ entregaId, deshabilitado, alCargar }: { entregaId: number; deshabilitado: boolean; alCargar: (m: string) => void }) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    const u = url.trim()
    if (!RE_REPO.test(u)) return setError('La URL debe tener el formato https://github.com/<propietario>/<repositorio>.')
    setError(null)
    setEnviando(true)
    try {
      await agregarRepositorio(entregaId, u)
      setUrl('')
      alCargar('Repositorio agregado correctamente.')
    } catch (err) {
      setError(mensajeError(err))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="rounded border border-slate-200 bg-slate-50 p-3">
      <label htmlFor="repo-url" className="block text-sm font-semibold text-slate-800">Repositorio GitHub</label>
      <p id="repo-ayuda" className="text-xs text-slate-600">Alternativa al ZIP de código. Ej.: https://github.com/usuario/proyecto</p>
      <input id="repo-url" type="url" value={url} disabled={deshabilitado || enviando} onChange={(e) => setUrl(e.target.value)} aria-describedby="repo-ayuda" className={campo} />
      {error && <p role="alert" className="mt-2 text-sm text-red-800">{error}</p>}
      <button type="submit" disabled={deshabilitado || enviando || !url.trim()} className={`${botonPrim} mt-2`}>
        {enviando ? 'Enviando…' : 'Agregar repositorio'}
      </button>
    </form>
  )
}

export default function Entrega() {
  const { id } = useParams()
  const { usuario } = useAuth()
  const entregaId = Number(id)
  const [entrega, setEntrega] = useState<TipoEntrega | null>(null)
  const [lab, setLab] = useState<Laboratorio | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const [aviso, setAviso] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null)
  const [ocupado, setOcupado] = useState<number | null>(null)

  const recargar = useCallback(async () => {
    try {
      const e = await obtenerEntrega(entregaId)
      setEntrega(e)
      setError(null)
      obtenerLaboratorio(e.laboratorio.id).then(setLab).catch(() => setLab(null))
    } catch (err) {
      setError(mensajeError(err))
    } finally {
      setCargando(false)
    }
  }, [entregaId])

  useEffect(() => {
    let activo = true
    obtenerEntrega(entregaId)
      .then((e) => {
        if (!activo) return
        setEntrega(e)
        setError(null)
        obtenerLaboratorio(e.laboratorio.id).then(setLab).catch(() => setLab(null))
      })
      .catch((err) => activo && setError(mensajeError(err)))
      .finally(() => activo && setCargando(false))
    return () => {
      activo = false
    }
  }, [entregaId])

  if (!Number.isInteger(entregaId)) return <p className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10 text-red-800">Entrega no válida.</p>
  if (cargando) return <p role="status" className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10 text-slate-600">Cargando entrega…</p>
  if (error || !entrega) {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10">
        <Aviso tipo="error">{error ?? 'No se pudo cargar la entrega.'}</Aviso>
        <Link to="/portafolio" className="mt-4 inline-block text-marca underline">Volver al portafolio</Link>
      </section>
    )
  }

  const editable = entrega.estado === 'borrador' || entrega.estado === 'lista'
  const evidencias = entrega.evidencias ?? []

  async function alCargar(texto: string) {
    setAviso({ tipo: 'ok', texto })
    await recargar()
  }

  async function descargar(ev: Evidencia) {
    setOcupado(ev.id)
    setAviso(null)
    try {
      await descargarEvidencia(ev)
    } catch (e) {
      setAviso({ tipo: 'error', texto: mensajeError(e) })
    } finally {
      setOcupado(null)
    }
  }

  async function borrar(ev: Evidencia) {
    if (!window.confirm(`¿Borrar la evidencia "${ev.nombre_original ?? ev.url ?? ETIQUETA_TIPO[ev.tipo]}"? Esta acción no se puede deshacer.`)) return
    setOcupado(ev.id)
    setAviso(null)
    try {
      await borrarEvidencia(entregaId, ev.id)
      setAviso({ tipo: 'ok', texto: 'Evidencia borrada.' })
      await recargar()
    } catch (e) {
      setAviso({ tipo: 'error', texto: mensajeError(e) })
    } finally {
      setOcupado(null)
    }
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10">
      <Link to="/portafolio" className="text-sm text-marca underline">← Portafolio</Link>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <h1 className="font-serif text-[1.95rem] font-semibold leading-tight text-tinta">
          {entrega.laboratorio.codigo} · {entrega.laboratorio.titulo}
        </h1>
        <Insignia tono={TONO_ESTADO[entrega.estado]}>{ETIQUETA_ESTADO[entrega.estado]}</Insignia>
      </div>
      <p className="mt-1 text-sm text-slate-600">
        Estudiante: {entrega.estudiante.nombre} · Cohorte {entrega.laboratorio.cohorte} · Rúbrica fijada: versión {entrega.rubrica_version.numero}
      </p>

      <div aria-live="polite" className="mt-4">{aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}</div>

      {entrega.faltantes.length > 0 && (
        <div className="mt-4">
          <Aviso tipo="advertencia">Faltan: {entrega.faltantes.map((f) => ETIQUETA_FALTANTE[f] ?? f).join(', ')}.</Aviso>
        </div>
      )}
      {!editable && (
        <div className="mt-4">
          <Aviso tipo="advertencia">La entrega está {ETIQUETA_ESTADO[entrega.estado].toLowerCase()}: ya no se pueden cargar ni borrar evidencias.</Aviso>
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <section className={tarjeta} aria-labelledby="h-lab">
            <h2 id="h-lab" className="text-lg font-semibold text-tinta">Laboratorio</h2>
            {lab ? (
              <>
                <h3 className="mt-2 text-sm font-semibold text-slate-800">Descripción</h3>
                <p className="whitespace-pre-line text-sm text-slate-700">{lab.descripcion || 'Sin descripción.'}</p>
                <h3 className="mt-3 text-sm font-semibold text-slate-800">Objetivos</h3>
                <p className="whitespace-pre-line text-sm text-slate-700">{lab.objetivos || 'Sin objetivos.'}</p>
              </>
            ) : (
              <p className="mt-2 text-sm text-slate-600">No se pudo cargar la descripción del laboratorio.</p>
            )}
          </section>

          <section className={tarjeta} aria-labelledby="h-ev">
            <h2 id="h-ev" className="text-lg font-semibold text-tinta">Evidencias ({evidencias.length})</h2>
            {evidencias.length === 0 && <p className="mt-2 text-sm text-slate-600">Aún no hay evidencias cargadas.</p>}
            <ul className="mt-2 divide-y divide-slate-100">
              {evidencias.map((ev) => (
                <li key={ev.id} className="py-3">
                  <p className="flex flex-wrap items-center gap-2 text-sm">
                    <Insignia tono="azul">{ETIQUETA_TIPO[ev.tipo]}</Insignia>
                    <span className="min-w-0 break-all font-medium text-slate-900">{ev.nombre_original ?? ev.url}</span>
                  </p>
                  <p className="mt-1 text-xs text-slate-600">
                    {ev.tamano_bytes !== null && `${formatoTamano(ev.tamano_bytes)} · `}
                    {formatoFecha(ev.creado_en)}
                    {detalleTexto(ev) && ` · ${detalleTexto(ev)}`}
                  </p>
                  <div className="mt-2 flex gap-2">
                    {ev.tipo === 'repo_github' && ev.url ? (
                      <a href={ev.url} target="_blank" rel="noreferrer noopener" className={botonSec}>Abrir repositorio</a>
                    ) : (
                      <button type="button" className={botonSec} disabled={ocupado === ev.id} onClick={() => descargar(ev)} aria-label={`Descargar ${ev.nombre_original ?? 'evidencia'}`}>
                        Descargar
                      </button>
                    )}
                    <button type="button" className={botonSec} disabled={!editable || ocupado === ev.id} onClick={() => borrar(ev)} aria-label={`Borrar ${ev.nombre_original ?? ev.url ?? 'evidencia'}`}>
                      Borrar
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <section className={`${tarjeta} h-fit space-y-4`} aria-labelledby="h-carga">
          <h2 id="h-carga" className="text-lg font-semibold text-tinta">Cargar evidencias</h2>
          <p className="text-sm text-slate-600">Obligatorios: informe PDF y código (ZIP o repositorio GitHub; basta uno de los dos).</p>
          <ZonaCarga regla={REGLAS[0]} entregaId={entregaId} deshabilitado={!editable} alCargar={alCargar} />
          <ZonaCarga regla={REGLAS[1]} entregaId={entregaId} deshabilitado={!editable} alCargar={alCargar} />
          <ZonaRepo entregaId={entregaId} deshabilitado={!editable} alCargar={alCargar} />
          {REGLAS.slice(2).map((r) => (
            <ZonaCarga key={r.tipo} regla={r} entregaId={entregaId} deshabilitado={!editable} alCargar={alCargar} />
          ))}
        </section>
      </div>

      <PanelEvaluacion
        entregaId={entregaId}
        estadoEntrega={entrega.estado}
        esDocente={usuario?.rol === 'docente' || usuario?.rol === 'admin'}
        alCambiar={() => void recargar()}
      />
    </section>
  )
}

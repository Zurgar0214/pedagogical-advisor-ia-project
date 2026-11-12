// Cliente de la Iteración 2: laboratorios, rúbricas versionadas, portafolio y entregas (docs/API.md).
import { leerToken } from '../auth/token'
import { api, BASE, enviar, ErrorApi, extraerDetalle, manejarSesionExpirada } from './cliente'

export type Cohorte = 1 | 2

export interface RubricaVigente {
  version_id: number
  numero: number
  valida: boolean
}

export interface Laboratorio {
  id: number
  cohorte: Cohorte
  codigo: string
  titulo: string
  descripcion: string
  objetivos: string
  temas: string[]
  rubrica_vigente: RubricaVigente | null
}

export interface NuevoLaboratorio {
  cohorte: Cohorte
  codigo: string
  titulo: string
  descripcion: string
  objetivos: string
  temas: string[]
}

export type CambiosLaboratorio = Partial<NuevoLaboratorio>

export interface NivelRubrica {
  nombre: string
  descriptor: string
  valor: number
}

export interface CompetenciaRubrica {
  id: string
  nombre: string
  descripcion: string
}

export interface CriterioRubrica {
  id: string
  nombre: string
  descripcion: string
  competencia_id: string
  peso: number
  niveles: NivelRubrica[]
}

export interface RubricaContenido {
  version?: number
  competencias: CompetenciaRubrica[]
  criterios: CriterioRubrica[]
}

export interface RubricaVersion {
  id: number
  numero: number
  valida: boolean
  inconsistencias: string[]
  /** Ausente en el listado de versiones del laboratorio. */
  contenido?: RubricaContenido
  creado_por: { id: number; nombre: string }
  creado_en: string
}

export interface RubricasLaboratorio {
  vigente: RubricaVersion | null
  versiones: RubricaVersion[]
}

export interface ResultadoValidacion {
  valida: boolean
  inconsistencias: string[]
}

export type TipoEvidencia = 'informe_pdf' | 'codigo_zip' | 'repo_github' | 'video' | 'presentacion' | 'imagen'

export interface Evidencia {
  id: number
  tipo: TipoEvidencia
  nombre_original: string | null
  url: string | null
  tamano_bytes: number | null
  sha256: string | null
  creado_en: string
  /** Según el tipo: PDF {paginas, caracteres_texto}; ZIP {numero de archivos, ...}; repo {owner, repo}. */
  detalle: Record<string, unknown> | null
}

export type EstadoEntrega = 'borrador' | 'lista' | 'en_evaluacion' | 'evaluada'

export interface Entrega {
  id: number
  estado: EstadoEntrega
  creado_en: string
  estudiante: { id: number; nombre: string }
  laboratorio: { id: number; codigo: string; titulo: string; cohorte: Cohorte }
  rubrica_version: { id: number; numero: number }
  /** Ausente en las entregas resumidas del portafolio. */
  evidencias?: Evidencia[]
  faltantes: string[]
}

export interface EstudianteResumen {
  id: number
  nombre: string
  correo: string
}

export interface EntradaPortafolio {
  laboratorio: Laboratorio
  entrega: Entrega | null
}

export interface Portafolio {
  estudiante: EstudianteResumen
  cohortes: { cohorte: Cohorte; laboratorios: EntradaPortafolio[] }[]
}

export const listarLaboratorios = (cohorte?: Cohorte) =>
  api<Laboratorio[]>(cohorte ? `/laboratorios?cohorte=${cohorte}` : '/laboratorios')

export const obtenerLaboratorio = (id: number) => api<Laboratorio>(`/laboratorios/${id}`)

export const crearLaboratorio = (datos: NuevoLaboratorio) => api<Laboratorio>('/laboratorios', enviar('POST', datos))

export const actualizarLaboratorio = (id: number, cambios: CambiosLaboratorio) =>
  api<Laboratorio>(`/laboratorios/${id}`, enviar('PATCH', cambios))

export const obtenerRubricasLaboratorio = (labId: number) => api<RubricasLaboratorio>(`/laboratorios/${labId}/rubrica`)

export const crearVersionRubrica = (labId: number, contenido: RubricaContenido) =>
  api<RubricaVersion>(`/laboratorios/${labId}/rubrica/versiones`, enviar('POST', contenido))

export const obtenerVersionRubrica = (id: number) => api<RubricaVersion>(`/rubrica-versiones/${id}`)

export const validarRubrica = (contenido: RubricaContenido) =>
  api<ResultadoValidacion>('/rubricas/validar', enviar('POST', contenido))

export const listarEstudiantes = () => api<EstudianteResumen[]>('/estudiantes')

export const obtenerPortafolio = (estudianteId?: number) =>
  api<Portafolio>(estudianteId ? `/portafolio?estudiante_id=${estudianteId}` : '/portafolio')

export const crearEntrega = (laboratorioId: number, estudianteId?: number) =>
  api<Entrega>(
    '/entregas',
    enviar('POST', estudianteId ? { laboratorio_id: laboratorioId, estudiante_id: estudianteId } : { laboratorio_id: laboratorioId }),
  )

export const obtenerEntrega = (id: number) => api<Entrega>(`/entregas/${id}`)

export const borrarEvidencia = (entregaId: number, evidenciaId: number) =>
  api<void>(`/entregas/${entregaId}/evidencias/${evidenciaId}`, { method: 'DELETE' })

/** Agrega un repositorio de GitHub como evidencia (multipart con `tipo` y `url`). */
export function agregarRepositorio(entregaId: number, url: string) {
  const datos = new FormData()
  datos.append('tipo', 'repo_github')
  datos.append('url', url)
  return api<Evidencia>(`/entregas/${entregaId}/evidencias`, { method: 'POST', body: datos })
}

/**
 * Sube un archivo como evidencia con progreso (XMLHttpRequest). No fija Content-Type:
 * el navegador agrega el boundary del multipart.
 */
export function subirEvidencia(
  entregaId: number,
  tipo: TipoEvidencia,
  archivo: File,
  alProgreso?: (porcentaje: number) => void,
): Promise<Evidencia> {
  return new Promise((resolver, rechazar) => {
    const datos = new FormData()
    datos.append('tipo', tipo)
    datos.append('archivo', archivo)
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE}/entregas/${entregaId}/evidencias`)
    xhr.setRequestHeader('Accept', 'application/json')
    const token = leerToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) alProgreso?.(Math.round((ev.loaded / ev.total) * 100))
    }
    xhr.onerror = () => rechazar(new ErrorApi(0, 'No se pudo conectar con el servidor. Intenta de nuevo.'))
    xhr.onload = () => {
      let cuerpo: unknown = null
      try {
        cuerpo = JSON.parse(xhr.responseText)
      } catch {
        /* cuerpo no JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) return resolver(cuerpo as Evidencia)
      if (xhr.status === 401 && token) manejarSesionExpirada()
      rechazar(new ErrorApi(xhr.status, extraerDetalle(cuerpo, `Error ${xhr.status} al subir la evidencia.`)))
    }
    xhr.send(datos)
  })
}

/** Descarga una evidencia enviando el token (fetch → blob → enlace temporal). */
export async function descargarEvidencia(evidencia: Evidencia): Promise<void> {
  const token = leerToken()
  let respuesta: Response
  try {
    respuesta = await fetch(`${BASE}/evidencias/${evidencia.id}/archivo`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
  } catch {
    throw new ErrorApi(0, 'No se pudo conectar con el servidor. Intenta de nuevo.')
  }
  if (!respuesta.ok) {
    let cuerpo: unknown = null
    try {
      cuerpo = await respuesta.json()
    } catch {
      /* cuerpo no JSON */
    }
    if (respuesta.status === 401 && token) manejarSesionExpirada()
    throw new ErrorApi(respuesta.status, extraerDetalle(cuerpo, `Error ${respuesta.status} al descargar el archivo.`))
  }
  const blob = await respuesta.blob()
  const enlaceUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = enlaceUrl
  a.download = evidencia.nombre_original ?? `evidencia-${evidencia.id}`
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(enlaceUrl), 10_000)
}

export const listarEntregas = (filtros: { estudiante_id?: number; laboratorio_id?: number; estado?: EstadoEntrega } = {}) => {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(filtros)) if (v !== undefined) q.set(k, String(v))
  const s = q.toString()
  return api<Entrega[]>(s ? `/entregas?${s}` : '/entregas')
}

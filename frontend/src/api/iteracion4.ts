// Cliente de la Iteración 4: informe integral y mapa mental (docs/API.md, backend/app/informes/contrato.py).
import { api, BASE, ErrorApi, extraerDetalle, manejarSesionExpirada } from './cliente'
import type { UsoModelo, UsuarioRef } from './iteracion3'
import { leerToken } from '../auth/token'

export type NivelDominio = 'inicial' | 'basico' | 'competente' | 'avanzado'
export type EstadoInforme = 'procesando' | 'listo' | 'error'

export interface LaboratorioAgregado {
  laboratorio_id: number
  codigo: string
  titulo: string
  cohorte: number
  evaluacion_id: number
  nota_final: number
  publicado_en: string
  fortalezas: string[]
  debilidades: string[]
  recomendaciones: string[]
}

export interface CompetenciaAgregada {
  nombre: string
  promedio: number
  nivel_dominio: NivelDominio
  laboratorios: string[]
  por_cohorte: Record<string, number>
}

export interface AprendizajeLab {
  laboratorio: string
  que_aprendio: string
  como_aplico: string
  nivel_dominio: NivelDominio
}

export interface TemaAgregado {
  tema: string
  nivel_dominio: NivelDominio | null
  promedio: number | null
  laboratorios: string[]
  laboratorios_sin_evidencia: string[]
  aprendizajes: AprendizajeLab[]
  que_fortalecer: string[]
}

export interface Brecha {
  tipo: 'competencia' | 'tema' | 'criterio' | 'sin_evidencia'
  nombre: string
  detalle: string
}

export interface AgregadoInforme {
  estudiante: string
  laboratorios_totales: number
  laboratorios: LaboratorioAgregado[]
  promedio_general: number
  promedio_cohorte: Record<string, number>
  nivel_general: NivelDominio
  competencias: CompetenciaAgregada[]
  temas: TemaAgregado[]
  tendencia: number | null
  brechas: Brecha[]
}

export interface AccionPlan {
  prioridad: number
  tema: string
  objetivo: string
  actividades: string[]
  recursos: string[]
  indicador_logro: string
  plazo_semanas: number
}

export interface RelacionTemas {
  origen: string
  destino: string
  tipo: 'prerrequisito' | 'complementa' | 'aplica'
  explicacion: string
}

export interface SintesisInforme {
  resumen: string
  evolucion: string
  plan: AccionPlan[]
  clasificacion: { tema: string; categoria: string }[]
  relaciones: RelacionTemas[]
}

export interface Informe {
  id: number
  estado: EstadoInforme
  error: string | null
  estudiante: { id: number; nombre: string; correo: string }
  generado_en: string
  generado_por: UsuarioRef
  evaluaciones_incluidas: number[]
  agregado: AgregadoInforme | null
  sintesis: SintesisInforme | null
  temas_categoria: Record<string, string>
  proveedor: string | null
  modelo: string | null
  version_prompt: string | null
  /** Ausentes para el estudiante. */
  advertencias?: string[]
  uso?: UsoModelo[]
  costo_usd_estimado?: number
}

export interface InformeResumen {
  id: number
  estado: EstadoInforme
  error?: string | null
  generado_en: string
  evaluaciones_incluidas: number[]
  promedio_general: number | null
}

export type TipoNodo = 'raiz' | 'categoria' | 'tema' | 'laboratorio'
export type TipoArista = 'jerarquia' | 'aplicado_en' | 'relacion'

export interface NodoMapa {
  id: string
  tipo: TipoNodo
  etiqueta: string
  nivel_dominio: NivelDominio | null
  datos: {
    promedio?: number | null
    temas?: number
    cohortes?: number[]
    laboratorios?: string[]
    aprendizajes?: AprendizajeLab[]
    que_fortalecer?: string[]
    sin_evidencia?: boolean
    cohorte?: number
    nota_final?: number
    evaluacion_id?: number
    titulo?: string
  }
}

export interface AristaMapa {
  id: string
  origen: string
  destino: string
  tipo: TipoArista
  etiqueta: string
}

export interface Mapa {
  informe_id: number
  estudiante: { id: number; nombre: string }
  nodos: NodoMapa[]
  aristas: AristaMapa[]
}

export const generarInforme = (estudianteId: number) =>
  api<Informe>(`/estudiantes/${estudianteId}/informes`, { method: 'POST' })

export const listarInformes = (estudianteId: number) => api<InformeResumen[]>(`/estudiantes/${estudianteId}/informes`)

export const obtenerInforme = (id: number) => api<Informe>(`/informes/${id}`)

export const obtenerMapa = (informeId: number) => api<Mapa>(`/informes/${informeId}/mapa`)

/** Guarda un Blob (o una URL de datos) en disco mediante un enlace temporal. */
export function guardarArchivo(contenido: Blob | string, nombre: string): void {
  const url = typeof contenido === 'string' ? contenido : URL.createObjectURL(contenido)
  const a = document.createElement('a')
  a.href = url
  a.download = nombre
  document.body.appendChild(a)
  a.click()
  a.remove()
  if (typeof contenido !== 'string') window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const guardarJson = (datos: unknown, nombre: string) =>
  guardarArchivo(new Blob([JSON.stringify(datos, null, 2)], { type: 'application/json' }), nombre)

/** Descarga el PDF con el token (un enlace directo no enviaría Authorization). */
export async function descargarPdfInforme(id: number, nombre: string): Promise<void> {
  const token = leerToken()
  let r: Response
  try {
    r = await fetch(`${BASE}/informes/${id}/pdf`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  } catch {
    throw new ErrorApi(0, 'No se pudo conectar con el servidor. Intenta de nuevo.')
  }
  if (!r.ok) {
    let cuerpo: unknown = null
    try {
      cuerpo = await r.json()
    } catch {
      /* no JSON */
    }
    if (r.status === 401 && token) manejarSesionExpirada()
    throw new ErrorApi(r.status, extraerDetalle(cuerpo, `No se pudo descargar el PDF (error ${r.status}).`))
  }
  guardarArchivo(await r.blob(), nombre)
}

export const nombreArchivoSeguro = (texto: string) =>
  texto
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .toLowerCase() || 'estudiante'

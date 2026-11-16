// Cliente de la Iteración 3: evaluación con IA y revisión docente (docs/API.md, backend/app/evaluacion/contrato.py).
import { api, enviar } from './cliente'
import type { NivelRubrica } from './iteracion2'

export type EstadoEvaluacion = 'procesando' | 'en_revision' | 'aprobada' | 'publicada' | 'error'
export type NivelDominio = 'inicial' | 'basico' | 'competente' | 'avanzado'

export interface UsuarioRef {
  id: number
  nombre: string
}

export interface EvidenciaCitada {
  evidencia_id: number | null
  fuente: string
  ubicacion: string
  fragmento: string
}

export interface AjusteDocente {
  nivel: string
  justificacion: string
  usuario: UsuarioRef
  fecha: string
}

export interface CriterioEvaluado {
  criterio_id: string
  criterio: string
  competencia: string
  peso: number
  niveles_disponibles: NivelRubrica[]
  /** Ausentes para el estudiante: nivel_ia, confianza. */
  nivel_ia?: string
  nivel_final: string
  valor_nivel_final: number
  confianza?: number
  justificacion: string
  evidencias: EvidenciaCitada[]
  fortalezas: string[]
  debilidades: string[]
  recomendaciones: string[]
  modelo?: string
  escalado?: boolean
  ajuste_docente: AjusteDocente | null
}

export interface Aprendizaje {
  tema: string
  que_aprendio: string
  como_aplico: string
  que_fortalecer: string
  nivel_dominio: NivelDominio
  criterios_relacionados: string[]
}

export interface HallazgoCodigo {
  archivo: string
  linea: number | null
  regla: string
  mensaje: string
}

export interface ResultadoPruebas {
  ejecutadas: boolean
  motivo: string
  total: number
  exitosas: number
  fallidas: number
  errores?: number
  omitidas?: number
  tiempo_agotado?: boolean
  salida: string
}

export interface VerificacionTecnica {
  archivos_analizados: number
  archivos_por_lenguaje: Record<string, number>
  errores_sintaxis: HallazgoCodigo[]
  hallazgos_estaticos: HallazgoCodigo[]
  pruebas: ResultadoPruebas
  repositorios_no_analizados: string[]
  notas: string[]
}

export interface UsoModelo {
  proveedor: string
  modelo: string
  proposito: string
  tokens_entrada: number
  tokens_salida: number
  tokens_cache_lectura: number
  tokens_cache_escritura: number
  costo_usd_estimado: number
  duracion_s: number
  intentos: number
}

export interface Evaluacion {
  id: number
  entrega_id: number
  estado: EstadoEvaluacion
  error: string | null
  estudiante: UsuarioRef
  laboratorio: { id: number; codigo: string; titulo: string; cohorte: number }
  rubrica_version: { id: number; numero: number }
  /** Ausentes para el estudiante: proveedor interno, nota_preliminar, advertencias, uso, costo. */
  proveedor?: string
  modelo_principal?: string
  version_prompt?: string
  nota_preliminar?: number | null
  nota_final: number | null
  requiere_revision?: boolean
  advertencias?: string[]
  criterios: CriterioEvaluado[]
  resumen: string
  fortalezas: string[]
  debilidades: string[]
  recomendaciones: string[]
  aprendizajes: Aprendizaje[]
  verificacion: VerificacionTecnica | null
  uso?: UsoModelo[]
  costo_usd_estimado?: number
  creado_en: string
  revisado_por: UsuarioRef | null
  aprobado_en: string | null
  publicado_en: string | null
}

export interface ConfiguracionIA {
  proveedor: string
  modelo_principal: string
  modelo_escalamiento: string
  umbral_confianza: number
  disponible: boolean
  motivo: string
}

export const configuracionIA = () => api<ConfiguracionIA>('/ia/configuracion')

export const evaluarEntrega = (entregaId: number) =>
  api<Evaluacion>(`/entregas/${entregaId}/evaluaciones`, { method: 'POST' })

export const listarEvaluacionesEntrega = (entregaId: number) =>
  api<Evaluacion[]>(`/entregas/${entregaId}/evaluaciones`)

export const colaEvaluaciones = (estado?: EstadoEvaluacion) =>
  api<Evaluacion[]>(estado ? `/evaluaciones?estado=${encodeURIComponent(estado)}` : '/evaluaciones')

export const obtenerEvaluacion = (id: number) => api<Evaluacion>(`/evaluaciones/${id}`)

export const ajustarCriterio = (id: number, criterioId: string, nivel: string, justificacion: string) =>
  api<Evaluacion>(`/evaluaciones/${id}/criterios/${encodeURIComponent(criterioId)}`, enviar('PATCH', { nivel, justificacion }))

export const aprobarEvaluacion = (id: number) => api<Evaluacion>(`/evaluaciones/${id}/aprobar`, { method: 'POST' })

export const publicarEvaluacion = (id: number) => api<Evaluacion>(`/evaluaciones/${id}/publicar`, { method: 'POST' })

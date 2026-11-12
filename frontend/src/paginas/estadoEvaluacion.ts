import type { EstadoEvaluacion, NivelDominio } from '../api/iteracion3'

export const ETIQUETA_EVAL: Record<EstadoEvaluacion, string> = {
  procesando: 'Procesando',
  en_revision: 'En revisión',
  aprobada: 'Aprobada',
  publicada: 'Publicada',
  error: 'Error',
}
export const TONO_EVAL: Record<EstadoEvaluacion, 'gris' | 'ambar' | 'azul' | 'verde' | 'rojo'> = {
  procesando: 'azul',
  en_revision: 'ambar',
  aprobada: 'verde',
  publicada: 'verde',
  error: 'rojo',
}
export const ETIQUETA_DOMINIO: Record<NivelDominio, string> = {
  inicial: 'Inicial',
  basico: 'Básico',
  competente: 'Competente',
  avanzado: 'Avanzado',
}
export const TONO_DOMINIO: Record<NivelDominio, 'gris' | 'ambar' | 'azul' | 'verde'> = {
  inicial: 'ambar',
  basico: 'gris',
  competente: 'azul',
  avanzado: 'verde',
}

export const formatoNota = (n: number | null | undefined) => (typeof n === 'number' ? n.toFixed(1).replace('.', ',') : '—')

import type { EstadoEntrega } from '../api/iteracion2'

export const ETIQUETA_ESTADO: Record<EstadoEntrega, string> = {
  borrador: 'Borrador',
  lista: 'Lista',
  en_evaluacion: 'En evaluación',
  evaluada: 'Evaluada',
}
export const TONO_ESTADO: Record<EstadoEntrega, 'gris' | 'ambar' | 'azul' | 'verde'> = {
  borrador: 'ambar',
  lista: 'azul',
  en_evaluacion: 'azul',
  evaluada: 'verde',
}
export const ETIQUETA_FALTANTE: Record<string, string> = { informe_pdf: 'Informe PDF', codigo: 'Código (ZIP o repositorio)' }

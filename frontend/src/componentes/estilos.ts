import { ErrorApi } from '../api/cliente'

export const campo =
  'mt-1 block w-full rounded border border-slate-400 bg-white px-3 py-2 text-slate-900 focus:outline-2 focus:outline-marca disabled:bg-slate-100'
export const botonPrim =
  'rounded bg-marca px-4 py-2 text-sm font-medium text-white hover:bg-tinta focus:outline-2 focus:outline-offset-2 focus:outline-marca disabled:opacity-60'
export const botonSec =
  'rounded border border-slate-400 bg-white px-2.5 py-1 text-sm text-slate-800 hover:bg-slate-100 focus:outline-2 focus:outline-marca disabled:opacity-50'
export const tarjeta = 'rounded-lg border border-slate-200 bg-white p-4 shadow-sm'

export const mensajeError = (e: unknown) => (e instanceof ErrorApi ? e.message : 'Ocurrió un error inesperado.')

export const formatoFecha = (iso: string) => new Date(iso).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' })

export function formatoTamano(bytes: number | null): string {
  if (bytes === null) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

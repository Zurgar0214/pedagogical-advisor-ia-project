import { ErrorApi } from '../api/cliente'

export const campo =
  'mt-1 block w-full rounded-md border border-slate-400 bg-white px-3 py-2 text-slate-900 transition-colors placeholder:text-slate-500 hover:border-slate-500 focus:border-marca focus:outline-2 focus:outline-offset-0 focus:outline-marca/30 disabled:bg-slate-100'
export const botonPrim =
  'inline-flex items-center justify-center gap-2 rounded-md bg-marca px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-pizarra focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-marca active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60'
export const botonSec =
  'inline-flex items-center justify-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 transition-colors hover:border-slate-400 hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-marca disabled:cursor-not-allowed disabled:opacity-50'
export const tarjeta = 'rounded-lg border border-slate-200 bg-white p-5'

export const mensajeError = (e: unknown) => (e instanceof ErrorApi ? e.message : 'Ocurrió un error inesperado.')

export const formatoFecha = (iso: string) => new Date(iso).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' })

export function formatoTamano(bytes: number | null): string {
  if (bytes === null) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

import { api } from './cliente'
import type { RubricaContenido } from './iteracion2'
import type { UsoModelo } from './iteracion3'

export interface PropuestaRubrica {
  rubrica: RubricaContenido
  validacion: { valida: boolean; inconsistencias: string[] }
  observaciones: string[]
  advertencias: string[]
  proveedor: string
  modelo: string
  uso: UsoModelo[]
  costo_usd_estimado: number
}

export const LIMITE_PDF_BYTES = 10 * 1024 * 1024
export const TEXTO_MIN = 50
export const TEXTO_MAX = 60000

/** POST /rubricas/interpretar (multipart): envía `archivo` (PDF) o `texto`, nunca ambos. No guarda nada. */
export function interpretarRubrica(entrada: { archivo: File } | { texto: string }): Promise<PropuestaRubrica> {
  const fd = new FormData()
  if ('archivo' in entrada) fd.append('archivo', entrada.archivo)
  else fd.append('texto', entrada.texto)
  return api<PropuestaRubrica>('/rubricas/interpretar', { method: 'POST', body: fd })
}

import type { NivelDominio } from '../api/iteracion4'

export type NivelOVacio = NivelDominio | null
export type ClaveDominio = NivelDominio | 'sin'

/** Escala única de dominio, compartida por el informe y el mapa. El glifo y el texto evitan depender solo del color. */
export const DOMINIO: Record<ClaveDominio, { etiqueta: string; glifo: string; fondo: string; borde: string; texto: string; punto: string }> = {
  inicial: { etiqueta: 'Inicial', glifo: '◔', fondo: '#fee2e2', borde: '#b91c1c', texto: '#7f1d1d', punto: '#dc2626' },
  basico: { etiqueta: 'Básico', glifo: '◑', fondo: '#fef3c7', borde: '#b45309', texto: '#78350f', punto: '#d97706' },
  competente: { etiqueta: 'Competente', glifo: '◕', fondo: '#dbeafe', borde: '#1d4ed8', texto: '#1e3a8a', punto: '#2563eb' },
  avanzado: { etiqueta: 'Avanzado', glifo: '●', fondo: '#d1fae5', borde: '#047857', texto: '#064e3b', punto: '#059669' },
  sin: { etiqueta: 'Sin evidencia', glifo: '○', fondo: '#f1f5f9', borde: '#64748b', texto: '#334155', punto: '#94a3b8' },
}

export const claveDominio = (n: NivelOVacio | undefined): ClaveDominio => n ?? 'sin'

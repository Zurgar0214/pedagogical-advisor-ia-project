import type { ReactNode } from 'react'

export function Aviso({ tipo, children }: { tipo: 'ok' | 'error' | 'advertencia'; children: ReactNode }) {
  const estilos = {
    ok: 'border-emerald-300 bg-emerald-50 text-emerald-900',
    error: 'border-red-300 bg-red-50 text-red-800',
    advertencia: 'border-amber-300 bg-amber-50 text-amber-900',
  }[tipo]
  return (
    <div role={tipo === 'error' ? 'alert' : 'status'} className={`rounded border px-3 py-2 text-sm ${estilos}`}>
      {children}
    </div>
  )
}

export function Insignia({ tono, children }: { tono: 'verde' | 'rojo' | 'gris' | 'azul' | 'ambar'; children: ReactNode }) {
  const estilos = {
    verde: 'bg-emerald-100 text-emerald-900',
    rojo: 'bg-red-100 text-red-900',
    gris: 'bg-slate-200 text-slate-800',
    azul: 'bg-blue-100 text-blue-900',
    ambar: 'bg-amber-100 text-amber-900',
  }[tono]
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${estilos}`}>{children}</span>
}


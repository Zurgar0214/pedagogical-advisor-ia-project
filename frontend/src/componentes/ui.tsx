import type { ReactNode } from 'react'

export function Aviso({ tipo, children }: { tipo: 'ok' | 'error' | 'advertencia'; children: ReactNode }) {
  const estilos = {
    ok: 'border-emerald-600 bg-emerald-50 text-emerald-900',
    error: 'border-red-600 bg-red-50 text-red-900',
    advertencia: 'border-amber-500 bg-amber-50 text-amber-950',
  }[tipo]
  return (
    <div role={tipo === 'error' ? 'alert' : 'status'} className={`rounded-md border-l-4 px-3.5 py-2.5 text-sm ${estilos}`}>
      {children}
    </div>
  )
}

export function Insignia({ tono, children }: { tono: 'verde' | 'rojo' | 'gris' | 'azul' | 'ambar'; children: ReactNode }) {
  const estilos = {
    verde: 'bg-emerald-100 text-emerald-900',
    rojo: 'bg-red-100 text-red-900',
    gris: 'bg-slate-200 text-slate-800',
    azul: 'bg-marca-claro text-pizarra',
    ambar: 'bg-amber-100 text-amber-900',
  }[tono]
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${estilos}`}>{children}</span>
}


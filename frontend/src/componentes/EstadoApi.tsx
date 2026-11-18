import { useEffect, useState } from 'react'
import { consultarSalud } from '../api/cliente'

export default function EstadoApi({ enOscuro = false }: { enOscuro?: boolean }) {
  const [conectada, setConectada] = useState<boolean | null>(null)

  useEffect(() => {
    let activo = true
    consultarSalud().then((ok) => {
      if (activo) setConectada(ok)
    })
    return () => {
      activo = false
    }
  }, [])

  const texto = conectada === null ? 'Comprobando API…' : conectada ? 'API conectada' : 'API sin conexión'
  const color = conectada === null ? 'bg-slate-400' : conectada ? 'bg-emerald-400' : 'bg-red-500'

  return (
    <span role="status" className={`inline-flex items-center gap-2 text-sm ${enOscuro ? 'text-white/70' : 'text-slate-600'}`}>
      <span className={`h-2.5 w-2.5 rounded-full ${color}`} aria-hidden="true" />
      {texto}
    </span>
  )
}

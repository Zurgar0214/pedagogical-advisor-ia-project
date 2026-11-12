import type { EstudianteResumen } from '../api/iteracion2'
import { campo } from './estilos'
import { Aviso } from './ui'

interface Props {
  id: string
  estudiantes: EstudianteResumen[]
  valor: number | ''
  alCambiar: (v: number | '') => void
  error: string | null
}

export function SelectorEstudiante({ id, estudiantes, valor, alCambiar, error }: Props) {
  return (
    <div className="max-w-sm">
      <label htmlFor={id} className="block text-sm font-medium text-slate-800">Estudiante</label>
      <select id={id} value={valor} onChange={(e) => alCambiar(e.target.value === '' ? '' : Number(e.target.value))} className={campo}>
        <option value="">Selecciona un estudiante…</option>
        {estudiantes.map((s) => (
          <option key={s.id} value={s.id}>
            {s.nombre} ({s.correo})
          </option>
        ))}
      </select>
      {error && <div className="mt-2"><Aviso tipo="error">{error}</Aviso></div>}
    </div>
  )
}

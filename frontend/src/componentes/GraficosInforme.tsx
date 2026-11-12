import type { CompetenciaAgregada, LaboratorioAgregado } from '../api/iteracion4'
import { DOMINIO } from './dominio'
import { InsigniaDominio } from './InsigniaDominio'
import { formatoNota } from '../paginas/estadoEvaluacion'

const COLOR_COHORTE: Record<number, string> = { 1: '#1d4ed8', 2: '#c2410c' }
const colorCohorte = (c: number) => COLOR_COHORTE[c] ?? '#475569'

function Marca({ cohorte, x, y }: { cohorte: number; x: number; y: number }) {
  const color = colorCohorte(cohorte)
  // Forma distinta por cohorte para no depender solo del color.
  if (cohorte === 1) return <circle cx={x} cy={y} r={6} fill={color} stroke="#fff" strokeWidth={1.5} />
  return <rect x={x - 6} y={y - 6} width={12} height={12} fill={color} stroke="#fff" strokeWidth={1.5} transform={`rotate(45 ${x} ${y})`} />
}

export function GraficoEvolucion({ laboratorios }: { laboratorios: LaboratorioAgregado[] }) {
  const orden = [...laboratorios].sort((a, b) => a.cohorte - b.cohorte || a.publicado_en.localeCompare(b.publicado_en))
  const cohortes = [...new Set(orden.map((l) => l.cohorte))].sort()
  const margen = { izq: 40, der: 20, arr: 16, abajo: 84 }
  const paso = 70
  const ancho = Math.max(480, margen.izq + margen.der + paso * orden.length)
  const alto = 300
  const yDe = (v: number) => margen.arr + (1 - v / 5) * (alto - margen.arr - margen.abajo)
  const xDe = (i: number) => margen.izq + paso * (i + 0.5)

  if (orden.length === 0) return <p className="text-sm text-slate-600">No hay laboratorios evaluados.</p>

  return (
    <div>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${ancho} ${alto}`}
          width={ancho}
          height={alto}
          role="img"
          aria-label={`Evolución de la nota final por laboratorio, escala de 0 a 5. ${orden.map((l) => `${l.codigo}: ${formatoNota(l.nota_final)}`).join('; ')}.`}
          className="max-w-none"
        >
          {[0, 1, 2, 3, 4, 5].map((v) => (
            <g key={v}>
              <line x1={margen.izq} x2={ancho - margen.der} y1={yDe(v)} y2={yDe(v)} stroke="#e2e8f0" />
              <text x={margen.izq - 8} y={yDe(v) + 4} textAnchor="end" fontSize="11" fill="#475569">{v}</text>
            </g>
          ))}
          {cohortes.map((c) => {
            const pts = orden.map((l, i) => ({ l, i })).filter((p) => p.l.cohorte === c)
            return (
              <polyline
                key={c}
                points={pts.map((p) => `${xDe(p.i)},${yDe(p.l.nota_final)}`).join(' ')}
                fill="none"
                stroke={colorCohorte(c)}
                strokeWidth={2}
                strokeDasharray={c === 1 ? undefined : '6 4'}
              />
            )
          })}
          {orden.map((l, i) => (
            <g key={l.evaluacion_id}>
              <Marca cohorte={l.cohorte} x={xDe(i)} y={yDe(l.nota_final)} />
              <title>{`${l.codigo} · ${l.titulo} (cohorte ${l.cohorte}): ${formatoNota(l.nota_final)}`}</title>
              <text x={xDe(i)} y={yDe(l.nota_final) - 12} textAnchor="middle" fontSize="11" fontWeight="600" fill="#14213d">
                {formatoNota(l.nota_final)}
              </text>
              <text
                x={xDe(i)}
                y={alto - margen.abajo + 14}
                textAnchor="end"
                fontSize="11"
                fill="#334155"
                transform={`rotate(-35 ${xDe(i)} ${alto - margen.abajo + 14})`}
              >
                {l.codigo}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <ul className="mt-2 flex flex-wrap gap-4 text-sm text-slate-700" aria-label="Leyenda del gráfico de evolución">
        {cohortes.map((c) => (
          <li key={c} className="flex items-center gap-2">
            <svg width="22" height="14" aria-hidden="true">
              <line x1="0" x2="22" y1="7" y2="7" stroke={colorCohorte(c)} strokeWidth="2" strokeDasharray={c === 1 ? undefined : '5 3'} />
              <Marca cohorte={c} x={11} y={7} />
            </svg>
            Cohorte {c}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function BarrasCompetencias({ competencias }: { competencias: CompetenciaAgregada[] }) {
  const orden = [...competencias].sort((a, b) => b.promedio - a.promedio)
  if (orden.length === 0) return <p className="text-sm text-slate-600">No hay competencias para mostrar.</p>
  return (
    <ul className="space-y-3">
      {orden.map((c) => {
        const d = DOMINIO[c.nivel_dominio]
        return (
          <li key={c.nombre}>
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="font-medium text-slate-900">{c.nombre}</span>
              <span className="flex items-center gap-2">
                <strong className="text-tinta">{formatoNota(c.promedio)}</strong>
                <InsigniaDominio nivel={c.nivel_dominio} />
              </span>
            </div>
            <div
              className="mt-1 h-3 w-full overflow-hidden rounded bg-slate-200"
              role="img"
              aria-label={`${c.nombre}: promedio ${formatoNota(c.promedio)} de 5, nivel ${d.etiqueta}`}
            >
              <div className="h-full rounded" style={{ width: `${Math.max(0, Math.min(100, (c.promedio / 5) * 100))}%`, backgroundColor: d.punto }} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}

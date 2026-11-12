import { claveDominio, DOMINIO, type ClaveDominio } from './dominio'

export function InsigniaDominio({ nivel }: { nivel: Parameters<typeof claveDominio>[0] }) {
  const d = DOMINIO[claveDominio(nivel)]
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium"
      style={{ backgroundColor: d.fondo, borderColor: d.borde, color: d.texto }}
    >
      <span aria-hidden="true">{d.glifo}</span>
      {d.etiqueta}
    </span>
  )
}

export function LeyendaDominio() {
  return (
    <ul className="flex flex-wrap gap-x-3 gap-y-1" aria-label="Leyenda de niveles de dominio">
      {(Object.keys(DOMINIO) as ClaveDominio[]).map((k) => (
        <li key={k}>
          <InsigniaDominio nivel={k === 'sin' ? null : k} />
        </li>
      ))}
    </ul>
  )
}

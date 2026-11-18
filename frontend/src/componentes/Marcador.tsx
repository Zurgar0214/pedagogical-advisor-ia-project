import { Link } from 'react-router-dom'

interface Props {
  titulo: string
  requisito: string
  descripcion: string
}

/** Página de estado (hoy solo se usa para rutas inexistentes). */
export default function Marcador({ titulo, requisito, descripcion }: Props) {
  return (
    <section className="mx-auto max-w-2xl px-4 py-20 lg:px-10">
      <p className="font-display text-6xl font-semibold text-slate-300">{requisito}</p>
      <h1 className="mt-4 font-display text-[1.95rem] font-semibold leading-tight text-tinta">{titulo}</h1>
      <p className="mt-2 text-lg text-slate-600">{descripcion} Revisa la dirección o vuelve al inicio.</p>
      <Link
        to="/"
        className="mt-6 inline-flex rounded-md bg-marca px-5 py-2.5 font-semibold text-white transition-colors hover:bg-pizarra"
      >
        Volver al inicio
      </Link>
    </section>
  )
}

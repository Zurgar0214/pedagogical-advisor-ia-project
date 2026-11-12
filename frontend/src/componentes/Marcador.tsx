interface Props {
  titulo: string
  requisito: string
  descripcion: string
}

export default function Marcador({ titulo, requisito, descripcion }: Props) {
  return (
    <section className="mx-auto max-w-3xl px-4 py-16 text-center">
      <p className="text-sm font-semibold uppercase tracking-widest text-acento">{requisito}</p>
      <h1 className="mt-2 font-serif text-3xl font-semibold text-tinta">{titulo}</h1>
      <div className="mt-8 rounded-lg border border-dashed border-slate-300 bg-white p-10">
        <p className="text-lg font-medium text-slate-700">En construcción — {requisito}</p>
        <p className="mt-2 text-slate-600">{descripcion}</p>
      </div>
    </section>
  )
}

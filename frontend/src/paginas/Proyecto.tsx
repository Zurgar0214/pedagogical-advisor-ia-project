import { useState } from 'react'

const objetivos = [
  'Evaluar los laboratorios de cada estudiante contra su rúbrica, con evidencias citadas por criterio.',
  'Calcular la nota (0,0 a 5,0) de forma determinista en el backend, nunca en el modelo de lenguaje.',
  'Generar un informe integral del aprendizaje y un mapa mental de competencias en IA.',
  'Garantizar que ninguna evaluación llegue al estudiante sin aprobación del docente.',
]

const funcionalidades = [
  ['Portafolio académico', 'Entregas por estudiante, cohorte y laboratorio (PDF, código y rúbrica).'],
  ['Gestión de rúbricas', 'Carga, interpretación asistida por IA, validación de ponderaciones (100 %) y versionado.'],
  ['Evaluación inteligente', 'Nivel de desempeño, evidencias, justificación y recomendaciones por criterio.'],
  ['Revisión docente', 'Ajuste de niveles con justificación, auditoría y publicación controlada.'],
  ['Informe integral', 'Notas, competencias, evolución, brechas y plan de fortalecimiento, descargable en PDF.'],
  ['Mapa mental interactivo', 'Competencias y conceptos con navegación, zoom y descarga en PNG, SVG o JSON.'],
]

const tecnologias = ['FastAPI', 'Pydantic', 'PostgreSQL', 'React', 'TypeScript', 'Tailwind CSS', 'Docker', 'Claude API / modelo local']

const aportes = [
  ['Evaluación explicable', 'Cada nivel asignado se respalda con evidencias concretas y una justificación legible.'],
  ['Trazable', 'Se conserva la versión de la rúbrica, el modelo, los parámetros y los resultados de pruebas.'],
  ['Validada por el docente', 'El docente revisa, ajusta y aprueba antes de que el estudiante vea el resultado.'],
]

function Foto() {
  const [falla, setFalla] = useState(false)
  if (falla) {
    return (
      <div
        role="img"
        aria-label="Iniciales de Juan Diego Varón Valencia"
        className="flex h-28 w-28 shrink-0 items-center justify-center rounded-full bg-marca text-3xl font-semibold text-white"
      >
        JV
      </div>
    )
  }
  return (
    <img
      src="/equipo/juan-diego.jpg"
      alt="Foto de Juan Diego Varón Valencia"
      onError={() => setFalla(true)}
      className="h-28 w-28 shrink-0 rounded-full object-cover ring-2 ring-marca-claro"
    />
  )
}

export default function Proyecto() {
  return (
    <div>
      <section className="bg-marca-claro">
        <div className="mx-auto max-w-6xl px-4 py-14">
          <p className="text-sm font-semibold uppercase tracking-widest text-acento">Proyecto Final · Inteligencia Artificial</p>
          <h1 className="mt-2 max-w-3xl font-serif text-4xl font-semibold leading-tight text-tinta">Asesor Pedagógico Inteligente</h1>
          <p className="mt-4 max-w-3xl text-lg leading-relaxed text-slate-700">
            Plataforma web que recibe los laboratorios de un estudiante, los evalúa con inteligencia artificial contra su rúbrica,
            calcula la nota en el backend y entrega un informe integral y un mapa mental de competencias, siempre bajo revisión y
            aprobación docente.
          </p>
        </div>
      </section>

      <div className="mx-auto max-w-6xl space-y-14 px-4 py-12">
        <section aria-labelledby="objetivos">
          <h2 id="objetivos" className="font-serif text-2xl font-semibold text-tinta">Objetivos</h2>
          <ul className="mt-4 list-disc space-y-2 pl-6 text-slate-700">
            {objetivos.map((o) => (
              <li key={o}>{o}</li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="funcionalidades">
          <h2 id="funcionalidades" className="font-serif text-2xl font-semibold text-tinta">Funcionalidades</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {funcionalidades.map(([t, d]) => (
              <article key={t} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                <h3 className="font-semibold text-marca">{t}</h3>
                <p className="mt-1 text-sm leading-relaxed text-slate-700">{d}</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="tecnologias">
          <h2 id="tecnologias" className="font-serif text-2xl font-semibold text-tinta">Tecnologías</h2>
          <ul className="mt-4 flex flex-wrap gap-2">
            {tecnologias.map((t) => (
              <li key={t} className="rounded-full border border-marca/30 bg-white px-3 py-1 text-sm font-medium text-marca">
                {t}
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="aportes">
          <h2 id="aportes" className="font-serif text-2xl font-semibold text-tinta">Aportes</h2>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            {aportes.map(([t, d]) => (
              <article key={t} className="rounded-lg border-l-4 border-acento bg-white p-5 shadow-sm">
                <h3 className="font-semibold text-tinta">{t}</h3>
                <p className="mt-1 text-sm leading-relaxed text-slate-700">{d}</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="equipo">
          <h2 id="equipo" className="font-serif text-2xl font-semibold text-tinta">Equipo</h2>
          <article className="mt-4 flex max-w-md items-center gap-5 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <Foto />
            <div>
              <h3 className="text-lg font-semibold text-tinta">Juan Diego Varón Valencia</h3>
              <p className="text-slate-700">Ingeniero de software full-stack e IA</p>
            </div>
          </article>
        </section>
      </div>
    </div>
  )
}

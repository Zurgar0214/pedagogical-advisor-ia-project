import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/contexto'

const objetivos = [
  'Evaluar los laboratorios de cada estudiante contra su rúbrica, con evidencias citadas por criterio.',
  'Calcular la nota (0,0 a 5,0) de forma determinista en el backend, nunca en el modelo de lenguaje.',
  'Generar un informe integral del aprendizaje y un mapa mental de competencias en IA.',
  'Garantizar que ninguna evaluación llegue al estudiante sin aprobación del docente.',
]

const funcionalidades = [
  ['Portafolio académico', 'Entregas por estudiante, cohorte y laboratorio: informe en PDF, código y rúbrica.'],
  ['Gestión de rúbricas', 'Editor visual, importación desde PDF con IA, validación de pesos (100 %) y versiones.'],
  ['Evaluación inteligente', 'Nivel de desempeño, evidencias, justificación y recomendaciones por criterio.'],
  ['Verificación del código', 'Sintaxis, análisis estático y pruebas unitarias del estudiante en una sandbox sin red.'],
  ['Revisión docente', 'Ajuste de niveles con justificación, auditoría y publicación controlada.'],
  ['Informe y mapa mental', 'Competencias, evolución entre cohortes y plan de fortalecimiento, con descargas.'],
]

// Es un proceso real y ordenado: por eso va numerado.
const pasos = [
  ['El estudiante entrega', 'Sube el informe en PDF y el código del laboratorio.'],
  ['Se verifica el código', 'Sintaxis, análisis estático y pruebas en un contenedor aislado.'],
  ['La IA propone niveles', 'Por criterio, con evidencias citadas y justificación validadas con Pydantic.'],
  ['El backend calcula la nota', 'Aplica los pesos de la rúbrica; el modelo nunca da la nota.'],
  ['El docente revisa', 'Ajusta lo que considere, justifica el cambio y aprueba.'],
  ['El estudiante ve el resultado', 'Solo cuando está publicado, con su informe y mapa mental.'],
]

const tecnologias = ['FastAPI', 'Pydantic', 'PostgreSQL', 'React', 'TypeScript', 'Tailwind CSS', 'React Flow', 'Docker', 'Caddy', 'Claude API', 'Ollama']

const aportes = [
  ['Evaluación explicable', 'Cada nivel asignado se respalda con evidencias concretas y una justificación legible.'],
  ['Trazable', 'Se conserva la versión de la rúbrica, el modelo, el prompt, el costo y los resultados de pruebas.'],
  ['Validada por el docente', 'El docente revisa, ajusta y aprueba antes de que el estudiante vea el resultado.'],
]

const NIVELES = [
  { nombre: 'Insuficiente', valor: 1 },
  { nombre: 'Básico', valor: 3 },
  { nombre: 'Competente', valor: 4 },
  { nombre: 'Sobresaliente', valor: 5 },
]

const formato = (n: number) => n.toLocaleString('es-CO', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

/** Ejemplo vivo de la regla central: la IA propone niveles y el backend aplica los pesos. */
function EjemploNota() {
  const [criterios, setCriterios] = useState([
    { nombre: 'Implementación del modelo', peso: 60, nivel: 2 },
    { nombre: 'Interpretación de resultados', peso: 40, nivel: 3 },
  ])
  const nota = criterios.reduce((s, c) => s + (c.peso / 100) * NIVELES[c.nivel].valor, 0)
  const operacion = criterios.map((c) => `${formato(c.peso / 100)} × ${formato(NIVELES[c.nivel].valor)}`).join(' + ')

  return (
    <figure className="rounded-lg border border-slate-200 bg-white">
      <figcaption className="border-b border-slate-200 px-5 py-3.5">
        <p className="font-semibold text-tinta">Así se calcula una nota</p>
        <p className="text-sm text-slate-600">Cambia el nivel que propone la IA y mira cómo el backend recalcula.</p>
      </figcaption>
      <div className="divide-y divide-slate-200">
        {criterios.map((c, i) => (
          <div key={c.nombre} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 px-5 py-3.5 sm:grid-cols-[1fr_auto_10.5rem]">
            <p className="text-[0.95rem] font-medium text-slate-800">{c.nombre}</p>
            <p className="text-right text-sm tabular-nums text-slate-600">peso {c.peso} %</p>
            <label className="col-span-2 sm:col-span-1">
              <span className="sr-only">Nivel propuesto para {c.nombre}</span>
              <select
                value={c.nivel}
                onChange={(e) =>
                  setCriterios((prev) => prev.map((x, j) => (j === i ? { ...x, nivel: Number(e.target.value) } : x)))
                }
                className="block w-full rounded-md border border-slate-300 bg-papel px-2.5 py-1.5 text-sm text-slate-900 hover:border-slate-400"
              >
                {NIVELES.map((n, k) => (
                  <option key={n.nombre} value={k}>
                    {n.nombre} ({formato(n.valor)})
                  </option>
                ))}
              </select>
            </label>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-end justify-between gap-4 rounded-b-lg bg-pizarra px-5 py-5 text-white">
        <div>
          <p className="text-sm text-white/70">Nota calculada por el backend</p>
          <p className="mt-1 text-sm tabular-nums text-white/80">{operacion} =</p>
        </div>
        <p aria-live="polite" className="font-display text-5xl font-semibold leading-none tabular-nums">
          <span className="text-resaltador">{formato(nota)}</span>
          <span className="ml-1 text-xl text-white/50">/ 5,0</span>
        </p>
      </div>
    </figure>
  )
}

function Foto() {
  const [falla, setFalla] = useState(false)
  if (falla) {
    return (
      <div
        role="img"
        aria-label="Iniciales de Juan Diego Varón Valencia"
        className="flex h-32 w-32 shrink-0 items-center justify-center rounded-full bg-marca text-3xl font-semibold text-white"
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
      className="h-32 w-32 shrink-0 rounded-full object-cover ring-4 ring-resaltador/70"
    />
  )
}

function Seccion({ id, titulo, children }: { id: string; titulo: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="grid gap-6 border-t border-slate-200 pt-10 lg:grid-cols-[13rem_1fr] lg:gap-10">
      <h2 id={id} className="font-display text-2xl font-semibold leading-tight text-tinta">
        {titulo}
      </h2>
      <div>{children}</div>
    </section>
  )
}

export default function Proyecto() {
  const { usuario } = useAuth()

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 lg:px-10 lg:py-14">
      <section className="grid items-center gap-10 xl:grid-cols-[1fr_27rem] xl:gap-14">
        <div>
          <p className="text-[0.95rem] font-medium text-acento">Proyecto final de Inteligencia Artificial, Universidad de Manizales</p>
          <h1 className="mt-3 font-display text-[2.6rem] font-semibold leading-[1.08] text-tinta sm:text-[3.2rem]">
            Asesor Pedagógico Inteligente
          </h1>
          <p className="mt-5 max-w-[36rem] text-lg leading-relaxed text-slate-700">
            Evalúa los laboratorios de cada estudiante contra su rúbrica. La IA propone el nivel de cada criterio con evidencias, el
            sistema calcula la nota y el docente decide qué se publica. Con eso se construye un informe integral y un mapa mental de
            competencias.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            {usuario ? (
              <Link
                to="/portafolio"
                className="inline-flex items-center rounded-md bg-marca px-5 py-2.5 font-semibold text-white transition-colors hover:bg-pizarra"
              >
                Ir al portafolio
              </Link>
            ) : (
              <Link
                to="/login"
                className="inline-flex items-center rounded-md bg-marca px-5 py-2.5 font-semibold text-white transition-colors hover:bg-pizarra"
              >
                Iniciar sesión
              </Link>
            )}
            <a
              href="#como-funciona"
              className="inline-flex items-center rounded-md border border-slate-300 bg-white px-5 py-2.5 font-semibold text-slate-800 transition-colors hover:border-slate-400"
            >
              Ver cómo funciona
            </a>
          </div>
        </div>
        <EjemploNota />
      </section>

      <div className="mt-16 space-y-12">
        <Seccion id="objetivos" titulo="Objetivos">
          <ul className="max-w-3xl space-y-3">
            {objetivos.map((o) => (
              <li key={o} className="flex gap-3 text-slate-700">
                <svg viewBox="0 0 20 20" className="mt-1 h-4 w-4 shrink-0 text-marca" aria-hidden="true">
                  <path d="M4 10.5l4 4 8-9" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                {o}
              </li>
            ))}
          </ul>
        </Seccion>

        <Seccion id="como-funciona" titulo="Cómo funciona">
          <ol className="grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
            {pasos.map(([t, d], i) => (
              <li key={t} className="relative pl-11">
                <span
                  aria-hidden="true"
                  className={`absolute left-0 top-0 flex h-8 w-8 items-center justify-center rounded-full font-display text-sm font-semibold ${
                    i === 3 ? 'bg-resaltador text-pizarra' : 'bg-marca-claro text-pizarra'
                  }`}
                >
                  {i + 1}
                </span>
                <p className="font-semibold text-tinta">{t}</p>
                <p className="mt-0.5 text-sm leading-relaxed text-slate-600">{d}</p>
              </li>
            ))}
          </ol>
        </Seccion>

        <Seccion id="funcionalidades" titulo="Funcionalidades">
          <dl className="grid gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 sm:grid-cols-2">
            {funcionalidades.map(([t, d]) => (
              <div key={t} className="bg-white px-5 py-4">
                <dt className="font-semibold text-pizarra">{t}</dt>
                <dd className="mt-1 text-sm leading-relaxed text-slate-600">{d}</dd>
              </div>
            ))}
          </dl>
        </Seccion>

        <Seccion id="tecnologias" titulo="Tecnologías">
          <ul className="flex flex-wrap gap-2">
            {tecnologias.map((t) => (
              <li key={t} className="rounded-md border border-slate-300 bg-white px-3 py-1 text-sm font-medium text-slate-700">
                {t}
              </li>
            ))}
          </ul>
        </Seccion>

        <Seccion id="aportes" titulo="Aportes">
          <div className="grid gap-6 md:grid-cols-3">
            {aportes.map(([t, d]) => (
              <article key={t} className="border-l-2 border-resaltador pl-4">
                <h3 className="font-semibold text-tinta">{t}</h3>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">{d}</p>
              </article>
            ))}
          </div>
        </Seccion>

        <Seccion id="equipo" titulo="Equipo">
          <article className="flex flex-col items-start gap-5 sm:flex-row sm:items-center">
            <Foto />
            <div>
              <h3 className="font-display text-xl font-semibold text-tinta">Juan Diego Varón Valencia</h3>
              <p className="text-slate-700">Ingeniero de software full-stack e IA</p>
              <p className="mt-2 max-w-md text-sm text-slate-600">
                Diseñó, dirigió y verificó el desarrollo con agentes de IA: requisitos, arquitectura, código, pruebas y despliegue.
              </p>
            </div>
          </article>
        </Seccion>
      </div>
    </div>
  )
}

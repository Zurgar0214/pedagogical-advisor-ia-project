import { useEffect, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  actualizarLaboratorio,
  crearLaboratorio,
  listarLaboratorios,
  type Cohorte,
  type Laboratorio,
  type NuevoLaboratorio,
} from '../api/iteracion2'
import { botonPrim, botonSec, campo, mensajeError, tarjeta } from '../componentes/estilos'
import { Aviso, Insignia } from '../componentes/ui'

const VACIO: NuevoLaboratorio = { cohorte: 1, codigo: '', titulo: '', descripcion: '', objetivos: '', temas: [] }

function EstadoRubrica({ lab }: { lab: Laboratorio }) {
  const r = lab.rubrica_vigente
  if (!r) return <Insignia tono="gris">Sin rúbrica</Insignia>
  return r.valida ? (
    <Insignia tono="verde">Válida (v{r.numero})</Insignia>
  ) : (
    <Insignia tono="rojo">Con inconsistencias (v{r.numero})</Insignia>
  )
}

export default function Laboratorios() {
  const [labs, setLabs] = useState<Laboratorio[]>([])
  const [cargando, setCargando] = useState(true)
  const [errorLista, setErrorLista] = useState<string | null>(null)
  const [recarga, setRecarga] = useState(0)
  const [aviso, setAviso] = useState<string | null>(null)

  // formulario (editando === null → creación)
  const [editando, setEditando] = useState<Laboratorio | null>(null)
  const [form, setForm] = useState<NuevoLaboratorio>(VACIO)
  const [tema, setTema] = useState('')
  const [errorForm, setErrorForm] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)

  useEffect(() => {
    let activo = true
    listarLaboratorios()
      .then((l) => {
        if (!activo) return
        setLabs(l)
        setErrorLista(null)
      })
      .catch((e) => activo && setErrorLista(mensajeError(e)))
      .finally(() => activo && setCargando(false))
    return () => {
      activo = false
    }
  }, [recarga])

  function empezarEdicion(l: Laboratorio) {
    setEditando(l)
    setForm({ cohorte: l.cohorte, codigo: l.codigo, titulo: l.titulo, descripcion: l.descripcion, objetivos: l.objetivos, temas: l.temas })
    setErrorForm(null)
    setAviso(null)
    document.getElementById('lab-codigo')?.focus()
  }

  function limpiar() {
    setEditando(null)
    setForm(VACIO)
    setTema('')
    setErrorForm(null)
  }

  function agregarTema() {
    const t = tema.trim()
    if (t && !form.temas.some((x) => x.toLowerCase() === t.toLowerCase())) setForm({ ...form, temas: [...form.temas, t] })
    setTema('')
  }

  function alTeclearTema(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      agregarTema()
    }
  }

  async function guardar(e: FormEvent) {
    e.preventDefault()
    if (!form.codigo.trim() || !form.titulo.trim()) return setErrorForm('Completa el código y el título.')
    const temas = tema.trim() ? [...form.temas, tema.trim()] : form.temas
    const datos = { ...form, codigo: form.codigo.trim(), titulo: form.titulo.trim(), temas }
    setErrorForm(null)
    setGuardando(true)
    try {
      if (editando) await actualizarLaboratorio(editando.id, datos)
      else await crearLaboratorio(datos)
      setAviso(editando ? 'Laboratorio actualizado.' : 'Laboratorio creado.')
      limpiar()
      setRecarga((n) => n + 1)
    } catch (err) {
      setErrorForm(mensajeError(err))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="font-serif text-2xl font-semibold text-tinta">Laboratorios</h1>
      <p className="mt-1 text-sm text-slate-600">Gestiona los laboratorios de cada cohorte y sus rúbricas versionadas.</p>

      <div aria-live="polite" className="mt-4">
        {aviso && <Aviso tipo="ok">{aviso}</Aviso>}
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-[1fr_22rem]">
        <div className="min-w-0 space-y-6">
          {errorLista && <Aviso tipo="error">{errorLista}</Aviso>}
          {cargando && (
            <p role="status" className="text-slate-600">
              Cargando laboratorios…
            </p>
          )}
          {([1, 2] as Cohorte[]).map((c) => {
            const lista = labs.filter((l) => l.cohorte === c)
            return (
              <section key={c} className={tarjeta} aria-labelledby={`cohorte-${c}`}>
                <h2 id={`cohorte-${c}`} className="text-lg font-semibold text-tinta">
                  Cohorte {c}
                </h2>
                {!cargando && lista.length === 0 && <p className="mt-3 text-sm text-slate-600">No hay laboratorios en esta cohorte.</p>}
                <ul className="mt-3 divide-y divide-slate-100">
                  {lista.map((l) => (
                    <li key={l.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <p className="font-medium text-slate-900">
                          <span className="text-slate-600">{l.codigo}</span> · {l.titulo}
                        </p>
                        <p className="mt-1 flex flex-wrap items-center gap-1.5">
                          <EstadoRubrica lab={l} />
                          {l.temas.map((t) => (
                            <Insignia key={t} tono="azul">
                              {t}
                            </Insignia>
                          ))}
                        </p>
                      </div>
                      <div className="flex shrink-0 gap-2">
                        <button type="button" className={botonSec} onClick={() => empezarEdicion(l)} aria-label={`Editar laboratorio ${l.codigo}`}>
                          Editar
                        </button>
                        <Link to={`/laboratorios/${l.id}/rubrica`} className={botonSec} aria-label={`Rúbrica de ${l.codigo}`}>
                          Rúbrica
                        </Link>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )
          })}
        </div>

        <form onSubmit={guardar} noValidate className={`${tarjeta} h-fit space-y-4`} aria-labelledby="titulo-lab">
          <h2 id="titulo-lab" className="text-lg font-semibold text-tinta">
            {editando ? `Editar ${editando.codigo}` : 'Crear laboratorio'}
          </h2>
          {errorForm && <Aviso tipo="error">{errorForm}</Aviso>}
          <div>
            <label htmlFor="lab-cohorte" className="block text-sm font-medium text-slate-800">Cohorte</label>
            <select id="lab-cohorte" value={form.cohorte} onChange={(e) => setForm({ ...form, cohorte: Number(e.target.value) as Cohorte })} className={campo}>
              <option value={1}>Cohorte 1</option>
              <option value={2}>Cohorte 2</option>
            </select>
          </div>
          <div>
            <label htmlFor="lab-codigo" className="block text-sm font-medium text-slate-800">Código</label>
            <input id="lab-codigo" type="text" required value={form.codigo} onChange={(e) => setForm({ ...form, codigo: e.target.value })} className={campo} placeholder="C1-LAB01" />
          </div>
          <div>
            <label htmlFor="lab-titulo" className="block text-sm font-medium text-slate-800">Título</label>
            <input id="lab-titulo" type="text" required value={form.titulo} onChange={(e) => setForm({ ...form, titulo: e.target.value })} className={campo} />
          </div>
          <div>
            <label htmlFor="lab-desc" className="block text-sm font-medium text-slate-800">Descripción</label>
            <textarea id="lab-desc" rows={3} value={form.descripcion} onChange={(e) => setForm({ ...form, descripcion: e.target.value })} className={campo} />
          </div>
          <div>
            <label htmlFor="lab-obj" className="block text-sm font-medium text-slate-800">Objetivos</label>
            <textarea id="lab-obj" rows={3} value={form.objetivos} onChange={(e) => setForm({ ...form, objetivos: e.target.value })} className={campo} />
          </div>
          <div>
            <label htmlFor="lab-tema" className="block text-sm font-medium text-slate-800">Temas (Enter para agregar)</label>
            <div className="flex gap-2">
              <input id="lab-tema" type="text" value={tema} onChange={(e) => setTema(e.target.value)} onKeyDown={alTeclearTema} className={campo} />
              <button type="button" className={`${botonSec} mt-1`} onClick={agregarTema}>
                Agregar
              </button>
            </div>
            <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Temas del laboratorio">
              {form.temas.map((t) => (
                <li key={t} className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-900">
                  {t}
                  <button type="button" aria-label={`Quitar tema ${t}`} className="rounded px-1 hover:bg-blue-200 focus:outline-2 focus:outline-marca" onClick={() => setForm({ ...form, temas: form.temas.filter((x) => x !== t) })}>
                    ×
                  </button>
                </li>
              ))}
            </ul>
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={guardando} className={`${botonPrim} flex-1`}>
              {guardando ? 'Guardando…' : editando ? 'Guardar cambios' : 'Crear laboratorio'}
            </button>
            {editando && (
              <button type="button" className={botonSec} onClick={limpiar}>
                Cancelar
              </button>
            )}
          </div>
        </form>
      </div>
    </section>
  )
}

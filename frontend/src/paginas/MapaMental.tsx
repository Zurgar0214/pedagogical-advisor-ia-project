import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Background,
  Controls,
  getNodesBounds,
  getViewportForBounds,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useNodesInitialized,
  useReactFlow,
  type Edge,
  type Node,
  type NodeChange,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { toPng, toSvg } from 'html-to-image'
import { guardarArchivo, guardarJson, nombreArchivoSeguro, obtenerMapa, type Mapa, type NodoMapa } from '../api/iteracion4'
import { botonSec, campo, formatoFecha, mensajeError, tarjeta } from '../componentes/estilos'
import { DOMINIO, claveDominio } from '../componentes/dominio'
import { InsigniaDominio, LeyendaDominio } from '../componentes/InsigniaDominio'
import { SelectorEstudiante } from '../componentes/SelectorEstudiante'
import { useEstudianteActivo } from '../componentes/useEstudianteActivo'
import { Aviso } from '../componentes/ui'
import { useInformes } from '../componentes/useInformes'
import { formatoNota } from './estadoEvaluacion'
import { ANCHO_NODO, calcularMapa, hijosDe, type Cohorte } from './mapaLayout'

type DatosRF = { nodo: NodoMapa; plegada?: boolean; alternar?: () => void }
type NodoRF = Node<DatosRF, 'mapa'>

const ETIQUETA_TIPO: Record<NodoMapa['tipo'], string> = { raiz: 'Raíz', categoria: 'Categoría', tema: 'Tema', laboratorio: 'Laboratorio' }
const ocultar = { opacity: 0, pointerEvents: 'none' as const }

function NodoMapaVista({ data, selected }: NodeProps<NodoRF>) {
  const { nodo } = data
  const esLab = nodo.tipo === 'laboratorio'
  const d = DOMINIO[claveDominio(nodo.nivel_dominio)]
  const sinNivel = !esLab && nodo.nivel_dominio === null
  const promedio = nodo.datos.promedio
  return (
    <div
      className="rounded-lg px-3 py-2 text-left shadow-sm"
      style={{
        width: ANCHO_NODO[nodo.tipo],
        backgroundColor: esLab ? '#ffffff' : d.fondo,
        color: esLab ? '#0f172a' : d.texto,
        border: `${nodo.tipo === 'raiz' ? 3 : 2}px ${sinNivel ? 'dashed' : 'solid'} ${esLab ? '#64748b' : d.borde}`,
        outline: selected ? '3px solid #14213d' : undefined,
        outlineOffset: 2,
      }}
    >
      <Handle type="target" position={Position.Left} id="in" style={ocultar} />
      <Handle type="source" position={Position.Right} id="out" style={ocultar} />
      <Handle type="source" position={Position.Right} id="rs" style={{ ...ocultar, top: '25%' }} />
      <Handle type="target" position={Position.Right} id="rt" style={{ ...ocultar, top: '75%' }} />
      <p className="text-[10px] font-semibold uppercase tracking-wide opacity-80">{ETIQUETA_TIPO[nodo.tipo]}</p>
      <p className={`leading-tight ${nodo.tipo === 'raiz' ? 'text-base font-bold' : 'text-sm font-semibold'}`} style={{ overflowWrap: 'anywhere' }}>
        {nodo.etiqueta}
      </p>
      <p className="mt-0.5 text-xs">
        {esLab ? (
          <>Cohorte {nodo.datos.cohorte ?? '—'} · Nota {formatoNota(nodo.datos.nota_final)}</>
        ) : (
          <>
            <span aria-hidden="true">{d.glifo} </span>
            {d.etiqueta}
            {typeof promedio === 'number' && <> · {formatoNota(promedio)}</>}
          </>
        )}
      </p>
      {nodo.tipo === 'categoria' && data.alternar && (
        <button
          type="button"
          className="nodrag nopan mt-1 rounded border px-1.5 py-0.5 text-xs font-medium"
          style={{ borderColor: d.borde, backgroundColor: '#ffffffb0' }}
          aria-expanded={!data.plegada}
          aria-label={`${data.plegada ? 'Desplegar' : 'Plegar'} la categoría ${nodo.etiqueta}`}
          onClick={(e) => {
            e.stopPropagation()
            data.alternar?.()
          }}
        >
          {data.plegada ? '+ Desplegar' : '− Plegar'}
        </button>
      )}
    </div>
  )
}

const tiposNodo = { mapa: NodoMapaVista }

function Dato({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="font-semibold text-slate-800">{etiqueta}:</span>
      {children}
    </div>
  )
}

function ListaSimple({ titulo, items }: { titulo: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div className="mt-3">
      <h4 className="text-sm font-semibold text-slate-800">{titulo}</h4>
      <ul className="list-disc pl-5 text-sm text-slate-700">
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </div>
  )
}

function PanelNodo({ mapa, nodo, ir }: { mapa: Mapa; nodo: NodoMapa | null; ir: (id: string) => void }) {
  const porId = useMemo(() => new Map(mapa.nodos.map((n) => [n.id, n])), [mapa])
  if (!nodo) {
    return <p className="text-sm text-slate-600">Selecciona un nodo del mapa (clic, o Tab y Enter) para ver su detalle.</p>
  }
  const botonNodo = (id: string, texto: string) => (
    <button type="button" className="text-left text-marca underline" onClick={() => ir(id)}>{texto}</button>
  )
  const hijos = hijosDe(mapa, 'jerarquia').get(nodo.id) ?? []
  const labs = (hijosDe(mapa, 'aplicado_en').get(nodo.id) ?? []).map((id) => porId.get(id)).filter((n): n is NodoMapa => !!n)
  const d = nodo.datos

  let cuerpo: React.ReactNode = null
  if (nodo.tipo === 'tema') {
    const relaciones = mapa.aristas.filter((a) => a.tipo === 'relacion' && (a.origen === nodo.id || a.destino === nodo.id))
    cuerpo = (
      <>
        <Dato etiqueta="Dominio"><InsigniaDominio nivel={nodo.nivel_dominio} /></Dato>
        {typeof d.promedio === 'number' && <Dato etiqueta="Promedio"><strong>{formatoNota(d.promedio)}</strong> / 5,0</Dato>}
        {d.sin_evidencia && <p className="mt-2 text-sm text-slate-700">Este tema aún no tiene evaluaciones publicadas que lo respalden.</p>}
        <div className="mt-3">
          <h4 className="text-sm font-semibold text-slate-800">Laboratorios donde se aplicó</h4>
          {labs.length === 0 && (d.laboratorios?.length ?? 0) === 0 && <p className="text-sm text-slate-600">Ninguno.</p>}
          <ul className="list-disc pl-5 text-sm">
            {labs.map((l) => (
              <li key={l.id}>
                {l.etiqueta} · nota {formatoNota(l.datos.nota_final)}{' '}
                {l.datos.evaluacion_id !== undefined && <Link to={`/evaluaciones/${l.datos.evaluacion_id}`} className="text-marca underline">Ver evaluación</Link>}
              </li>
            ))}
            {labs.length === 0 && (d.laboratorios ?? []).map((c) => <li key={c}>{c}</li>)}
          </ul>
        </div>
        {(d.aprendizajes?.length ?? 0) > 0 && (
          <div className="mt-3">
            <h4 className="text-sm font-semibold text-slate-800">Aprendizajes evidenciados</h4>
            <ul className="space-y-2 text-sm text-slate-700">
              {d.aprendizajes?.map((a, i) => (
                <li key={i}>
                  <span className="font-medium">{a.laboratorio}</span> <InsigniaDominio nivel={a.nivel_dominio} />
                  <p>{a.que_aprendio}</p>
                  {a.como_aplico && <p className="text-slate-600">Cómo lo aplicó: {a.como_aplico}</p>}
                </li>
              ))}
            </ul>
          </div>
        )}
        <ListaSimple titulo="Aspectos a profundizar" items={d.que_fortalecer ?? []} />
        {relaciones.length > 0 && (
          <div className="mt-3">
            <h4 className="text-sm font-semibold text-slate-800">Relaciones con otros temas</h4>
            <ul className="space-y-1 text-sm text-slate-700">
              {relaciones.map((r) => {
                const otro = r.origen === nodo.id ? r.destino : r.origen
                const o = porId.get(otro)
                return (
                  <li key={r.id}>
                    {r.origen === nodo.id ? 'Hacia' : 'Desde'} {o ? botonNodo(otro, o.etiqueta) : otro}
                    {r.etiqueta && <span className="block text-slate-600">{r.etiqueta}</span>}
                  </li>
                )
              })}
            </ul>
          </div>
        )}
      </>
    )
  } else if (nodo.tipo === 'laboratorio') {
    const temas = mapa.aristas.filter((a) => a.tipo === 'aplicado_en' && a.destino === nodo.id).map((a) => porId.get(a.origen)).filter((n): n is NodoMapa => !!n)
    cuerpo = (
      <>
        {d.titulo && <p className="text-sm text-slate-800">{d.titulo}</p>}
        <Dato etiqueta="Cohorte">{d.cohorte ?? '—'}</Dato>
        <Dato etiqueta="Nota final"><strong>{formatoNota(d.nota_final)}</strong> / 5,0</Dato>
        {d.evaluacion_id !== undefined && (
          <p className="mt-2"><Link to={`/evaluaciones/${d.evaluacion_id}`} className="text-sm text-marca underline">Ver evaluación</Link></p>
        )}
        {temas.length > 0 && (
          <div className="mt-3">
            <h4 className="text-sm font-semibold text-slate-800">Temas aplicados</h4>
            <ul className="list-disc pl-5 text-sm">{temas.map((t) => <li key={t.id}>{botonNodo(t.id, t.etiqueta)}</li>)}</ul>
          </div>
        )}
      </>
    )
  } else {
    cuerpo = (
      <>
        <Dato etiqueta="Dominio"><InsigniaDominio nivel={nodo.nivel_dominio} /></Dato>
        {typeof d.promedio === 'number' && <Dato etiqueta="Promedio"><strong>{formatoNota(d.promedio)}</strong> / 5,0</Dato>}
        <div className="mt-3">
          <h4 className="text-sm font-semibold text-slate-800">{nodo.tipo === 'raiz' ? 'Categorías' : `Temas (${hijos.length})`}</h4>
          <ul className="list-disc pl-5 text-sm">
            {hijos.map((id) => {
              const h = porId.get(id)
              return h ? <li key={id}>{botonNodo(id, h.etiqueta)}{h.nivel_dominio ? ` · ${DOMINIO[h.nivel_dominio].etiqueta}` : ' · Sin evidencia'}</li> : null
            })}
          </ul>
        </div>
      </>
    )
  }

  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">{ETIQUETA_TIPO[nodo.tipo]}</p>
      <h3 className="font-serif text-lg font-semibold text-tinta">{nodo.etiqueta}</h3>
      <div className="mt-2">{cuerpo}</div>
    </div>
  )
}

function Lienzo({ mapa, informeFecha }: { mapa: Mapa; informeFecha: string }) {
  const { fitView, setCenter, getNodes } = useReactFlow<NodoRF>()
  const contenedor = useRef<HTMLDivElement>(null)
  const [plegadas, setPlegadas] = useState<Set<string>>(new Set())
  const [mostrarLabs, setMostrarLabs] = useState(true)
  const [mostrarRel, setMostrarRel] = useState(true)
  const [cohorte, setCohorte] = useState<Cohorte>('todas')
  const [seleccionId, setSeleccionId] = useState<string | null>(null)
  const [hoverArista, setHoverArista] = useState<string | null>(null)
  const [busqueda, setBusqueda] = useState('')
  const [pendiente, setPendiente] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [exportando, setExportando] = useState(false)

  const porId = useMemo(() => new Map(mapa.nodos.map((n) => [n.id, n])), [mapa])
  const categorias = useMemo(() => mapa.nodos.filter((n) => n.tipo === 'categoria'), [mapa])
  const padreDe = useMemo(() => {
    const m = new Map<string, string>()
    for (const a of mapa.aristas) if (a.tipo === 'jerarquia' || a.tipo === 'aplicado_en') if (!m.has(a.destino)) m.set(a.destino, a.origen)
    return m
  }, [mapa])
  const cohortesDisponibles = useMemo(
    () => [...new Set(mapa.nodos.filter((n) => n.tipo === 'laboratorio').map((n) => n.datos.cohorte).filter((c): c is number => c === 1 || c === 2))].sort(),
    [mapa],
  )

  const visible = useMemo(() => calcularMapa(mapa, { plegadas, mostrarLabs, cohorte }), [mapa, plegadas, mostrarLabs, cohorte])

  const alternar = useCallback((id: string) => {
    setPlegadas((p) => {
      const n = new Set(p)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })
  }, [])

  const nodos = useMemo<NodoRF[]>(
    () =>
      visible.nodos.map((n) => ({
        id: n.id,
        type: 'mapa',
        position: { x: n.x, y: n.y },
        selected: n.id === seleccionId,
        draggable: false,
        connectable: false,
        ariaLabel: `${ETIQUETA_TIPO[n.tipo]}: ${n.etiqueta}. ${n.tipo === 'laboratorio' ? `Nota ${formatoNota(n.datos.nota_final)}` : DOMINIO[claveDominio(n.nivel_dominio)].etiqueta}`,
        data: { nodo: n, plegada: plegadas.has(n.id), alternar: n.tipo === 'categoria' ? () => alternar(n.id) : undefined },
      })),
    [visible, seleccionId, plegadas, alternar],
  )

  const aristas = useMemo<Edge[]>(() => {
    const base: Edge[] = visible.aristas.map((a) => ({
      id: a.id,
      source: a.origen,
      target: a.destino,
      sourceHandle: 'out',
      targetHandle: 'in',
      focusable: false,
      style: a.tipo === 'jerarquia' ? { stroke: '#475569', strokeWidth: 1.8 } : { stroke: '#94a3b8', strokeWidth: 1.2 },
    }))
    if (mostrarRel) {
      for (const a of visible.relaciones) {
        const texto = a.etiqueta || 'Relación'
        base.push({
          id: a.id,
          source: a.origen,
          target: a.destino,
          sourceHandle: 'rs',
          targetHandle: 'rt',
          ariaLabel: `Relación entre temas: ${texto}`,
          label: hoverArista === a.id ? texto : undefined,
          labelStyle: { fontSize: 12, fill: '#4c1d95', fontWeight: 600 },
          labelBgStyle: { fill: '#f5f3ff', stroke: '#7c3aed' },
          labelBgPadding: [6, 4],
          labelBgBorderRadius: 4,
          interactionWidth: 24,
          markerEnd: { type: MarkerType.ArrowClosed, color: '#7c3aed' },
          style: { stroke: '#7c3aed', strokeWidth: 2, strokeDasharray: '7 5' },
        })
      }
    }
    return base
  }, [visible, mostrarRel, hoverArista])

  const alCambiarNodos = useCallback((cambios: NodeChange<NodoRF>[]) => {
    for (const c of cambios) if (c.type === 'select' && c.selected) setSeleccionId(c.id)
  }, [])

  // Refit al cambiar la estructura visible (plegar, filtrar, ocultar), salvo que se esté buscando un nodo.
  const firma = useMemo(() => visible.nodos.map((n) => n.id).join('|'), [visible])
  // Espera a que React Flow mida los nodos; antes de eso fitView no tiene límites y no ajusta.
  const medidos = useNodesInitialized()
  useEffect(() => {
    if (pendiente || !medidos) return
    const t = window.setTimeout(() => void fitView({ duration: 300, padding: 0.12 }), 60)
    return () => window.clearTimeout(t)
  }, [firma, pendiente, medidos, fitView])

  useEffect(() => {
    if (!pendiente) return
    const n = visible.nodos.find((x) => x.id === pendiente)
    if (!n) return
    const t = window.setTimeout(() => {
      void setCenter(n.x + ANCHO_NODO[n.tipo] / 2, n.y + 32, { zoom: 1.1, duration: 500 })
      setSeleccionId(n.id)
      setPendiente(null)
    }, 80)
    return () => window.clearTimeout(t)
  }, [pendiente, visible, setCenter])

  /** Lleva el foco a un nodo, haciéndolo visible si estaba plegado, filtrado u oculto. */
  const ir = useCallback(
    (id: string) => {
      const n = porId.get(id)
      if (!n) return
      setCohorte('todas')
      if (n.tipo === 'laboratorio') {
        setMostrarLabs(true)
        const tema = padreDe.get(id)
        const cat = tema ? padreDe.get(tema) : undefined
        if (cat) setPlegadas((p) => new Set([...p].filter((c) => c !== cat)))
      } else if (n.tipo === 'tema') {
        const cat = padreDe.get(id)
        if (cat) setPlegadas((p) => new Set([...p].filter((c) => c !== cat)))
      }
      setPendiente(id)
    },
    [porId, padreDe],
  )

  const resultados = useMemo(() => {
    const q = busqueda.trim().toLowerCase()
    if (!q) return []
    return mapa.nodos.filter((n) => n.tipo === 'tema' && n.etiqueta.toLowerCase().includes(q)).slice(0, 8)
  }, [busqueda, mapa])

  async function exportar(formato: 'png' | 'svg') {
    const el = contenedor.current?.querySelector<HTMLElement>('.react-flow__viewport')
    const actuales = getNodes()
    if (!el || actuales.length === 0) return
    setExportando(true)
    setError(null)
    try {
      const b = getNodesBounds(actuales)
      const ancho = Math.ceil(b.width + 120)
      const alto = Math.ceil(b.height + 120)
      const vp = getViewportForBounds(b, ancho, alto, 0.1, 1, 0.06)
      const opciones = {
        backgroundColor: '#ffffff',
        width: ancho,
        height: alto,
        pixelRatio: 2,
        skipFonts: true,
        style: { width: `${ancho}px`, height: `${alto}px`, transform: `translate(${vp.x}px, ${vp.y}px) scale(${vp.zoom})` },
      }
      const base = `mapa-mental-${nombreArchivoSeguro(mapa.estudiante.nombre)}`
      if (formato === 'png') guardarArchivo(await toPng(el, opciones), `${base}.png`)
      else guardarArchivo(await toSvg(el, opciones), `${base}.svg`)
    } catch {
      setError('No se pudo exportar la imagen del mapa. Intenta de nuevo.')
    } finally {
      setExportando(false)
    }
  }

  const seleccionado = seleccionId ? (porId.get(seleccionId) ?? null) : null
  const todasPlegadas = categorias.length > 0 && categorias.every((c) => plegadas.has(c.id))

  return (
    <div className="mt-4">
      <div className={`${tarjeta} space-y-3`}>
        <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
          <div className="min-w-[14rem] flex-1">
            <label htmlFor="mm-buscar" className="block text-sm font-medium text-slate-800">Buscar tema</label>
            <input
              id="mm-buscar"
              type="search"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Ej.: regresión"
              className={campo}
              autoComplete="off"
              aria-controls="mm-resultados"
            />
            <ul id="mm-resultados" className="mt-1 flex flex-wrap gap-1" aria-live="polite">
              {busqueda.trim() !== '' && resultados.length === 0 && <li className="text-xs text-slate-600">Sin coincidencias.</li>}
              {resultados.map((r) => (
                <li key={r.id}>
                  <button type="button" className={botonSec} onClick={() => { ir(r.id); setBusqueda('') }}>{r.etiqueta}</button>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <label htmlFor="mm-cohorte" className="block text-sm font-medium text-slate-800">Cohorte</label>
            <select id="mm-cohorte" value={cohorte} onChange={(e) => setCohorte(e.target.value === 'todas' ? 'todas' : (Number(e.target.value) as Cohorte))} className={campo}>
              <option value="todas">Todas</option>
              {cohortesDisponibles.map((c) => (
                <option key={c} value={c}>Cohorte {c}</option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-800">
            <input type="checkbox" checked={mostrarLabs} onChange={(e) => setMostrarLabs(e.target.checked)} /> Laboratorios
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-800">
            <input type="checkbox" checked={mostrarRel} onChange={(e) => setMostrarRel(e.target.checked)} /> Relaciones entre temas
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className={botonSec} onClick={() => void fitView({ duration: 300, padding: 0.12 })}>Ajustar a la vista</button>
          <button type="button" className={botonSec} onClick={() => setPlegadas(todasPlegadas ? new Set() : new Set(categorias.map((c) => c.id)))}>
            {todasPlegadas ? 'Desplegar categorías' : 'Plegar categorías'}
          </button>
          <span className="mx-1 hidden h-5 w-px bg-slate-300 sm:inline-block" aria-hidden="true" />
          <button type="button" className={botonSec} disabled={exportando} onClick={() => void exportar('png')}>Descargar PNG</button>
          <button type="button" className={botonSec} disabled={exportando} onClick={() => void exportar('svg')}>Descargar SVG</button>
          <button type="button" className={botonSec} onClick={() => guardarJson(mapa, `mapa-mental-${nombreArchivoSeguro(mapa.estudiante.nombre)}.json`)}>Descargar JSON</button>
        </div>
        <LeyendaDominio />
        <p className="text-xs text-slate-600">
          Aristas: línea continua = jerarquía; línea fina gris = aplicado en laboratorio; línea punteada violeta = relación entre temas
          (pasa el cursor para ver su explicación). Informe del {informeFecha}.
        </p>
        {error && <Aviso tipo="error">{error}</Aviso>}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div
          ref={contenedor}
          className="h-[70vh] min-h-[26rem] rounded-lg border border-slate-300 bg-white"
          role="region"
          aria-label={`Lienzo del mapa mental de ${mapa.estudiante.nombre}. Usa Tab para recorrer los nodos y Enter para ver su detalle.`}
        >
          <ReactFlow
            nodes={nodos}
            edges={aristas}
            nodeTypes={tiposNodo}
            onNodesChange={alCambiarNodos}
            onPaneClick={() => setSeleccionId(null)}
            onEdgeMouseEnter={(_, e) => setHoverArista(e.id)}
            onEdgeMouseLeave={() => setHoverArista(null)}
            nodesDraggable={false}
            nodesConnectable={false}
            fitView
            fitViewOptions={{ padding: 0.12 }}
            minZoom={0.1}
            maxZoom={2}
            proOptions={{ hideAttribution: true }}
          >
            <Background />
            <Controls showInteractive={false} aria-label="Controles de zoom" />
            <MiniMap
              pannable
              zoomable
              ariaLabel="Minimapa"
              nodeColor={(n) => {
                const nodo = (n.data as DatosRF | undefined)?.nodo
                return nodo?.tipo === 'laboratorio' ? '#cbd5e1' : DOMINIO[claveDominio(nodo?.nivel_dominio)].punto
              }}
            />
          </ReactFlow>
        </div>
        <aside className={`${tarjeta} max-h-none overflow-auto lg:max-h-[70vh]`} aria-label="Detalle del nodo seleccionado" aria-live="polite">
          <PanelNodo mapa={mapa} nodo={seleccionado} ir={ir} />
        </aside>
      </div>
    </div>
  )
}

function ContenidoMapa({ estudianteId }: { estudianteId: number }) {
  const { lista, error } = useInformes(estudianteId)
  const [elegido, setElegido] = useState<number | null>(null)
  const [mapa, setMapa] = useState<Mapa | null>(null)
  const [errorMapa, setErrorMapa] = useState<string | null>(null)

  const listos = (lista ?? []).filter((i) => i.estado === 'listo')
  const verId = elegido !== null && listos.some((i) => i.id === elegido) ? elegido : (listos[0]?.id ?? null)
  const fecha = listos.find((i) => i.id === verId)?.generado_en

  useEffect(() => {
    if (verId === null) return
    let activo = true
    obtenerMapa(verId)
      .then((m) => {
        if (!activo) return
        setMapa(m)
        setErrorMapa(null)
      })
      .catch((e) => activo && setErrorMapa(mensajeError(e)))
    return () => {
      activo = false
    }
  }, [verId])

  if (error) return <div className="mt-4"><Aviso tipo="error">{error}</Aviso></div>
  if (lista === null) return <p role="status" className="mt-6 text-slate-600">Cargando…</p>
  if (listos.length === 0) {
    const procesando = lista.some((i) => i.estado === 'procesando')
    return (
      <div className="mt-6 max-w-2xl">
        <Aviso tipo="advertencia">
          {procesando ? 'El informe se está generando; el mapa estará disponible cuando termine.' : 'Todavía no hay un informe listo para construir el mapa mental.'}{' '}
          <Link to="/informe" className="font-medium underline">Ir a la página Informe</Link>
          {procesando ? ' para seguir el avance.' : ' para generar uno (solo usa evaluaciones publicadas).'}
        </Aviso>
      </div>
    )
  }

  return (
    <>
      {listos.length > 1 && (
        <div className="mt-4 max-w-sm">
          <label htmlFor="mm-informe" className="block text-sm font-medium text-slate-800">Informe</label>
          <select id="mm-informe" value={verId ?? ''} onChange={(e) => setElegido(Number(e.target.value))} className={campo}>
            {listos.map((i) => (
              <option key={i.id} value={i.id}>
                {formatoFecha(i.generado_en)}{i.promedio_general !== null ? ` · promedio ${formatoNota(i.promedio_general)}` : ''}
              </option>
            ))}
          </select>
        </div>
      )}
      {errorMapa && <div className="mt-4"><Aviso tipo="error">{errorMapa}</Aviso></div>}
      {mapa && mapa.informe_id === verId && (
        <ReactFlowProvider key={mapa.informe_id}>
          <Lienzo mapa={mapa} informeFecha={fecha ? formatoFecha(fecha) : '—'} />
        </ReactFlowProvider>
      )}
    </>
  )
}

export default function MapaMental() {
  const { esEstudiante, estudiantes, seleccion, setSeleccion, estudianteId, error } = useEstudianteActivo()
  return (
    <section className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="font-serif text-2xl font-semibold text-tinta">Mapa mental de competencias</h1>
      <p className="mt-1 text-sm text-slate-600">Temas, categorías y laboratorios con el nivel de dominio de cada uno, construido desde el informe.</p>
      {!esEstudiante && (
        <div className="mt-4">
          <SelectorEstudiante id="mm-est" estudiantes={estudiantes} valor={seleccion} alCambiar={setSeleccion} error={error} />
        </div>
      )}
      {!esEstudiante && estudianteId === null && !error && <p className="mt-6 text-slate-600">Elige un estudiante para ver su mapa.</p>}
      {estudianteId !== null && <ContenidoMapa key={estudianteId} estudianteId={estudianteId} />}
    </section>
  )
}

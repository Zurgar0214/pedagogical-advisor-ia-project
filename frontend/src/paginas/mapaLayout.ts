import type { AristaMapa, Mapa, NodoMapa } from '../api/iteracion4'

export const ANCHO_NODO: Record<NodoMapa['tipo'], number> = { raiz: 190, categoria: 210, tema: 230, laboratorio: 240 }
const X_COLUMNA: Record<NodoMapa['tipo'], number> = { raiz: 0, categoria: 270, tema: 560, laboratorio: 960 }
const ALTO_FILA = 88
const SEPARACION_GRUPO = 24

export type Cohorte = 'todas' | 1 | 2

export interface OpcionesMapa {
  plegadas: ReadonlySet<string>
  mostrarLabs: boolean
  cohorte: Cohorte
}

export interface MapaVisible {
  nodos: (NodoMapa & { x: number; y: number })[]
  /** Aristas jerárquicas y de aplicación visibles. */
  aristas: AristaMapa[]
  /** Aristas de relación entre temas, ambas puntas visibles. */
  relaciones: AristaMapa[]
}

const media = (v: number[]) => (v.length ? v.reduce((a, b) => a + b, 0) / v.length : 0)

/** Hijos por tipo de arista (origen → destinos). */
export function hijosDe(mapa: Mapa, tipo: AristaMapa['tipo']): Map<string, string[]> {
  const m = new Map<string, string[]>()
  for (const a of mapa.aristas) {
    if (a.tipo !== tipo) continue
    m.set(a.origen, [...(m.get(a.origen) ?? []), a.destino])
  }
  return m
}

/**
 * Árbol por columnas (raíz → categorías → temas → laboratorios). Las filas se reparten sin solaparse y cada
 * nodo se centra respecto de sus hijos/padres, así ~30 nodos quedan legibles.
 */
export function calcularMapa(mapa: Mapa, op: OpcionesMapa): MapaVisible {
  const porId = new Map(mapa.nodos.map((n) => [n.id, n]))
  const catsHijos = hijosDe(mapa, 'jerarquia')
  const labsDeTema = hijosDe(mapa, 'aplicado_en')

  const raiz = mapa.nodos.find((n) => n.tipo === 'raiz')
  const categorias = mapa.nodos.filter((n) => n.tipo === 'categoria')

  const pasaCohorte = (n: NodoMapa) => {
    if (op.cohorte === 'todas') return true
    if (n.tipo === 'laboratorio') return n.datos.cohorte === op.cohorte
    if (n.tipo === 'tema') {
      const c = n.datos.cohortes ?? []
      return n.datos.sin_evidencia === true || c.length === 0 || c.includes(op.cohorte)
    }
    return true
  }

  const y = new Map<string, number>()
  let fila = 0
  const temasVisibles = new Set<string>()
  const categoriasVisibles: NodoMapa[] = []

  for (const cat of categorias) {
    const temas = (catsHijos.get(cat.id) ?? []).map((id) => porId.get(id)).filter((n): n is NodoMapa => !!n && n.tipo === 'tema' && pasaCohorte(n))
    if (temas.length === 0) continue
    categoriasVisibles.push(cat)
    if (op.plegadas.has(cat.id)) {
      y.set(cat.id, fila * ALTO_FILA)
      fila += 1
    } else {
      const ys: number[] = []
      for (const t of temas) {
        y.set(t.id, fila * ALTO_FILA)
        temasVisibles.add(t.id)
        ys.push(fila * ALTO_FILA)
        fila += 1
      }
      y.set(cat.id, media(ys))
    }
    fila += SEPARACION_GRUPO / ALTO_FILA
  }

  // Laboratorios: se centran junto a sus temas y se separan hacia abajo.
  const labsVisibles: NodoMapa[] = []
  if (op.mostrarLabs) {
    const padres = new Map<string, string[]>()
    for (const [t, labs] of labsDeTema) for (const l of labs) padres.set(l, [...(padres.get(l) ?? []), t])
    const candidatos = mapa.nodos
      .filter((n) => n.tipo === 'laboratorio' && pasaCohorte(n))
      .map((n) => {
        const ps = padres.get(n.id) ?? []
        const visibles = ps.filter((p) => temasVisibles.has(p))
        return { n, deseado: visibles.length ? media(visibles.map((p) => y.get(p) ?? 0)) : null, huerfano: ps.length === 0 }
      })
      .filter((c) => c.deseado !== null || c.huerfano)
    candidatos.sort((a, b) => (a.deseado ?? Infinity) - (b.deseado ?? Infinity) || a.n.id.localeCompare(b.n.id))
    const minimo = 76
    let previo = -Infinity
    for (const c of candidatos) {
      const base = c.deseado ?? (previo === -Infinity ? 0 : previo + minimo)
      const pos = Math.max(base, previo + minimo)
      y.set(c.n.id, pos)
      previo = pos
      labsVisibles.push(c.n)
    }
  }

  const ysCats = categoriasVisibles.map((c) => y.get(c.id) ?? 0)
  if (raiz) y.set(raiz.id, media(ysCats))

  const nodos: NodoMapa[] = [
    ...(raiz ? [raiz] : []),
    ...categoriasVisibles,
    ...mapa.nodos.filter((n) => temasVisibles.has(n.id)),
    ...labsVisibles,
  ]
  const ids = new Set(nodos.map((n) => n.id))
  const aristas = mapa.aristas.filter((a) => a.tipo !== 'relacion' && ids.has(a.origen) && ids.has(a.destino))
  const relaciones = mapa.aristas.filter((a) => a.tipo === 'relacion' && temasVisibles.has(a.origen) && temasVisibles.has(a.destino))

  return {
    nodos: nodos.map((n) => ({ ...n, x: X_COLUMNA[n.tipo], y: y.get(n.id) ?? 0 })),
    aristas,
    relaciones,
  }
}

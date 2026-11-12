import { Background, Controls, ReactFlow, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

const nodos: Node[] = [{ id: '1', position: { x: 0, y: 0 }, data: { label: 'Competencias en IA' } }]
const aristas: Edge[] = []

export default function MapaMental() {
  return (
    <section className="mx-auto max-w-5xl px-4 py-12">
      <p className="text-center text-sm font-semibold uppercase tracking-widest text-acento">RF-10</p>
      <h1 className="mt-2 text-center font-serif text-3xl font-semibold text-tinta">Mapa mental</h1>
      <p className="mt-2 text-center text-slate-700">En construcción — RF-10. Vista previa mínima del lienzo.</p>
      <div className="mt-6 h-64 rounded-lg border border-slate-300 bg-white" aria-label="Lienzo del mapa mental">
        <ReactFlow nodes={nodos} edges={aristas} fitView>
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </section>
  )
}

import { useCallback, useEffect, useState } from 'react'
import { listarInformes, type InformeResumen } from '../api/iteracion4'
import { mensajeError } from './estilos'

const INTERVALO_MS = 3000

/** Lista los informes de un estudiante y sondea cada 3 s mientras alguno esté `procesando`. */
export function useInformes(estudianteId: number | null) {
  const [lista, setLista] = useState<InformeResumen[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const recargar = useCallback(async () => {
    if (estudianteId === null) return
    try {
      setLista(await listarInformes(estudianteId))
      setError(null)
    } catch (e) {
      setError(mensajeError(e))
    }
  }, [estudianteId])

  useEffect(() => {
    if (estudianteId === null) return
    let activo = true
    listarInformes(estudianteId)
      .then((l) => {
        if (!activo) return
        setLista(l)
        setError(null)
      })
      .catch((e) => activo && setError(mensajeError(e)))
    return () => {
      activo = false
    }
  }, [estudianteId])

  const procesando = lista?.some((i) => i.estado === 'procesando') ?? false
  useEffect(() => {
    if (!procesando) return
    const t = window.setInterval(() => void recargar(), INTERVALO_MS)
    return () => window.clearInterval(t)
  }, [procesando, recargar])

  return { lista, error, procesando, recargar }
}

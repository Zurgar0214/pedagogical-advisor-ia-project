import { useEffect, useState } from 'react'
import { listarEstudiantes, type EstudianteResumen } from '../api/iteracion2'
import { useAuth } from '../auth/contexto'
import { mensajeError } from './estilos'

/** Devuelve el id del estudiante activo (el propio si es estudiante) y los datos del selector para docente/admin. */
export function useEstudianteActivo() {
  const { usuario } = useAuth()
  const esEstudiante = usuario?.rol === 'estudiante'
  const [estudiantes, setEstudiantes] = useState<EstudianteResumen[]>([])
  const [seleccion, setSeleccion] = useState<number | ''>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (esEstudiante) return
    let activo = true
    listarEstudiantes()
      .then((l) => activo && setEstudiantes(l))
      .catch((e) => activo && setError(mensajeError(e)))
    return () => {
      activo = false
    }
  }, [esEstudiante])

  const estudianteId = esEstudiante ? (usuario?.id ?? null) : seleccion === '' ? null : seleccion
  return { esEstudiante, estudiantes, seleccion, setSeleccion, estudianteId, error }
}


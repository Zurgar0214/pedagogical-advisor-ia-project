const BASE: string = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

export class ErrorApi extends Error {
  estado: number
  constructor(estado: number, mensaje: string) {
    super(mensaje)
    this.estado = estado
  }
}

export async function api<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const respuesta = await fetch(`${BASE}${ruta}`, {
    ...opciones,
    headers: { Accept: 'application/json', ...(opciones.headers ?? {}) },
  })
  if (!respuesta.ok) {
    throw new ErrorApi(respuesta.status, `Error ${respuesta.status} en ${ruta}`)
  }
  return (await respuesta.json()) as T
}

/** Consulta GET /salud. Nunca lanza: devuelve false si la API no responde. */
export async function consultarSalud(): Promise<boolean> {
  try {
    await api<unknown>('/salud')
    return true
  } catch {
    return false
  }
}

import { borrarToken, leerToken } from '../auth/token'

export const BASE: string = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

export type Rol = 'admin' | 'docente' | 'estudiante'

export interface Usuario {
  id: number
  nombre: string
  correo: string
  rol: Rol
  activo: boolean
  creado_en: string
}

export interface RespuestaLogin {
  access_token: string
  token_type: 'bearer'
  usuario: Usuario
}

export interface NuevoUsuario {
  nombre: string
  correo: string
  contrasena: string
  rol: Rol
}

export type CambiosUsuario = Partial<{ nombre: string; rol: Rol; activo: boolean; contrasena: string }>

/** Error de la API; `message` es el `detail` en español devuelto por el backend. */
export class ErrorApi extends Error {
  estado: number
  constructor(estado: number, mensaje: string) {
    super(mensaje)
    this.name = 'ErrorApi'
    this.estado = estado
  }
}

let alSesionExpirada: (() => void) | null = null

/** El contexto de autenticación registra aquí qué hacer ante un 401 autenticado. */
export function registrarSesionExpirada(fn: (() => void) | null): void {
  alSesionExpirada = fn
}

export function extraerDetalle(cuerpo: unknown, respaldo: string): string {
  if (cuerpo && typeof cuerpo === 'object' && 'detail' in cuerpo) {
    const d = (cuerpo as { detail: unknown }).detail
    if (typeof d === 'string') return d
    if (Array.isArray(d)) {
      const msgs = d
        .map((e) => (e && typeof e === 'object' && 'msg' in e ? String((e as { msg: unknown }).msg) : ''))
        .filter(Boolean)
      if (msgs.length) return msgs.join('. ')
    }
  }
  return respaldo
}

export async function api<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const token = leerToken()
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (opciones.body !== undefined && !(opciones.body instanceof FormData)) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`

  let respuesta: Response
  try {
    respuesta = await fetch(`${BASE}${ruta}`, {
      ...opciones,
      headers: { ...headers, ...(opciones.headers as Record<string, string> | undefined) },
    })
  } catch {
    throw new ErrorApi(0, 'No se pudo conectar con el servidor. Intenta de nuevo.')
  }

  if (!respuesta.ok) {
    let cuerpo: unknown = null
    try {
      cuerpo = await respuesta.json()
    } catch {
      /* cuerpo no JSON */
    }
    if (respuesta.status === 401 && token) {
      borrarToken()
      alSesionExpirada?.()
    }
    throw new ErrorApi(respuesta.status, extraerDetalle(cuerpo, `Error ${respuesta.status} en ${ruta}`))
  }
  if (respuesta.status === 204) return undefined as T
  return (await respuesta.json()) as T
}

export const enviar = (metodo: string, cuerpo: unknown): RequestInit => ({ method: metodo, body: JSON.stringify(cuerpo) })

export const login = (correo: string, contrasena: string) =>
  api<RespuestaLogin>('/auth/login', enviar('POST', { correo, contrasena }))

export const obtenerYo = () => api<Usuario>('/auth/yo')

export const listarUsuarios = (rol?: Rol) =>
  api<Usuario[]>(rol ? `/usuarios?rol=${encodeURIComponent(rol)}` : '/usuarios')

export const crearUsuario = (datos: NuevoUsuario) => api<Usuario>('/usuarios', enviar('POST', datos))

export const actualizarUsuario = (id: number, cambios: CambiosUsuario) =>
  api<Usuario>(`/usuarios/${id}`, enviar('PATCH', cambios))

/** Consulta GET /salud. Nunca lanza: devuelve false si la API no responde. */
export async function consultarSalud(): Promise<boolean> {
  try {
    await api<unknown>('/salud')
    return true
  } catch {
    return false
  }
}

/** Para clientes auxiliares (subida con XHR, descargas): trata un 401 autenticado como sesión expirada. */
export function manejarSesionExpirada(): void {
  borrarToken()
  alSesionExpirada?.()
}

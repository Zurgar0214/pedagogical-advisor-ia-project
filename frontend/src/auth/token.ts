const CLAVE = 'api_token'

export function leerToken(): string | null {
  try {
    return sessionStorage.getItem(CLAVE)
  } catch {
    return null
  }
}

export function guardarToken(token: string): void {
  try {
    sessionStorage.setItem(CLAVE, token)
  } catch {
    /* sin almacenamiento: la sesión vive solo en memoria de la pestaña */
  }
}

export function borrarToken(): void {
  try {
    sessionStorage.removeItem(CLAVE)
  } catch {
    /* ignorar */
  }
}

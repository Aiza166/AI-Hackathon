// Small fetch wrapper around the backend's response envelope.
// Token lives in sessionStorage (cleared when the tab closes: phones are shared).

export type Envelope<T> = {
  success: boolean
  data: T
  error: { code: string; message: string } | null
  meta: Record<string, unknown>
}

const BASE: string = import.meta.env.VITE_API_BASE ?? ''
const TOKEN_KEY = 'sahara.token'

export class ApiError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

export function setToken(token: string | null): void {
  if (token) sessionStorage.setItem(TOKEN_KEY, token)
  else sessionStorage.removeItem(TOKEN_KEY)
}

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<Envelope<T>> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, 'OFFLINE', 'No connection. Your progress is saved on this phone.')
  }
  const body = (await response.json().catch(() => null)) as Envelope<T> | null
  if (!response.ok || !body?.success) {
    throw new ApiError(response.status, body?.error?.code ?? 'ERROR', body?.error?.message ?? 'Something went wrong')
  }
  return body
}

export function post<T>(path: string, data: unknown): Promise<Envelope<T>> {
  return api<T>(path, { method: 'POST', body: JSON.stringify(data) })
}

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}

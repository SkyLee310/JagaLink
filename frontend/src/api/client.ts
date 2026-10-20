import { useSession } from '../lib/session'
import type { ApiErrorBody } from './types'

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

/** A failed API call, carrying the server's {code, message, details} body (D-40). */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown

  constructor(status: number, code: string, message: string, details: unknown = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

/** Calls `/api/v1{path}` with the session's bearer token (D-41). A 401 ends the session. */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = useSession.getState().session?.token
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body !== undefined) headers.set('Content-Type', 'application/json')

  let response: Response
  try {
    response = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, 'network_error', 'Cannot reach the JagaLink server')
  }
  if (response.ok) return (await response.json()) as T
  if (response.status === 401) useSession.getState().signOut()
  throw await readError(response)
}

async function readError(response: Response): Promise<ApiError> {
  const body = (await response.json().catch(() => null)) as Partial<ApiErrorBody> | null
  if (typeof body?.code === 'string' && typeof body.message === 'string') {
    return new ApiError(response.status, body.code, body.message, body.details)
  }
  return new ApiError(response.status, 'http_error', `The server answered ${response.status}`)
}

/**
 * The lines worth showing for a failed call: each layout or scenario problem, or each malformed
 * field.
 */
export function errorLines(error: unknown): string[] {
  if (!(error instanceof ApiError)) return []
  const details = error.details as
    | { problems?: { message: string }[] }
    | (ValidationItem | string)[]
    | null
  if (Array.isArray(details)) {
    return details.map((item) => {
      if (typeof item === 'string') return item
      const where = (item.loc ?? []).filter((part) => part !== 'body').join('.')
      const text = String(item.msg).replace(/^Value error, /, '')
      return where ? `${where}: ${text}` : text
    })
  }
  return details?.problems?.map((problem) => problem.message) ?? []
}

interface ValidationItem {
  loc?: (string | number)[]
  msg: string
}

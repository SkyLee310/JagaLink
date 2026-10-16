import { describe, expect, it, vi } from 'vitest'
import { useSession } from '../lib/session'
import { jsonResponse } from '../test/http'
import { API_URL, ApiError, apiFetch } from './client'
import type { Session } from './types'

const SESSION: Session = {
  token: 'signed-token',
  expires_at: '2026-10-17T13:14:00.000Z',
  user: { id: 'u2', code: 'u-guard-02', name: 'Guard B', role: 'guard', on_duty: true },
  community_id: 'c1',
}

describe('apiFetch', () => {
  it('sends the bearer token and returns the JSON body', async () => {
    useSession.getState().signIn(SESSION)
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse({ status: 'ok' }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiFetch('/health')).resolves.toEqual({ status: 'ok' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`${API_URL}/api/v1/health`)
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer signed-token')
  })

  it('turns the error body into an ApiError', async () => {
    const body = { code: 'user_not_found', message: 'No seeded user has that ID', details: null }
    vi.stubGlobal('fetch', vi.fn<typeof fetch>(async () => jsonResponse(body, 404)))

    const error = await apiFetch('/session', { method: 'POST', body: '{}' }).catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 404, ...body })
  })

  it('clears the session on a 401', async () => {
    useSession.getState().signIn(SESSION)
    const body = { code: 'token_expired', message: 'The session has expired', details: null }
    vi.stubGlobal('fetch', vi.fn<typeof fetch>(async () => jsonResponse(body, 401)))

    await expect(apiFetch('/communities/c1/layout')).rejects.toMatchObject({ status: 401 })
    expect(useSession.getState().session).toBeNull()
  })

  it('reports a server it cannot reach', async () => {
    const offline = vi.fn<typeof fetch>(async () => {
      throw new TypeError('Failed to fetch')
    })
    vi.stubGlobal('fetch', offline)

    await expect(apiFetch('/session/users')).rejects.toMatchObject({
      status: 0,
      code: 'network_error',
    })
  })
})

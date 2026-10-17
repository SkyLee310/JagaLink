import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { SessionUser } from '../../api/types'
import { useSession } from '../../lib/session'
import { jsonResponse } from '../../test/http'
import { RolePickerPage } from './RolePickerPage'

const USERS: SessionUser[] = [
  { id: 'u1', code: 'u-guard-01', name: 'Guard A', role: 'guard', on_duty: true },
  { id: 'u3', code: 'u-guard-03', name: 'Guard C', role: 'guard', on_duty: false },
  { id: 'u0', code: 'u-sup-01', name: 'Supervisor', role: 'supervisor', on_duty: true },
]

function renderPicker() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<RolePickerPage />} />
          <Route path="/console" element={<p>Console page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RolePickerPage', () => {
  it('lists the seeded staff by role', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>(async () => jsonResponse(USERS)),
    )
    renderPicker()

    const guards = await screen.findByRole('region', { name: 'Guards' })
    const supervisors = screen.getByRole('region', { name: 'Supervisor' })
    expect(within(guards).getAllByRole('button')).toHaveLength(2)
    expect(within(guards).getByRole('button', { name: /Guard C/ }).textContent).toContain(
      'Off duty',
    )
    expect(within(supervisors).getAllByRole('button')).toHaveLength(1)
  })

  it('starts a session for the picked user and opens the console', async () => {
    const session = {
      token: 'signed-token',
      expires_at: '2026-10-17T13:14:00.000Z',
      user: USERS[0],
      community_id: 'c1',
    }
    const fetchMock = vi.fn<typeof fetch>(async (input) =>
      jsonResponse(String(input).endsWith('/session/users') ? USERS : session),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderPicker()

    fireEvent.click(await screen.findByRole('button', { name: /Guard A/ }))

    expect(await screen.findByText('Console page')).toBeTruthy()
    expect(useSession.getState().session).toEqual(session)
    const [url, init] = fetchMock.mock.calls[1]
    expect(String(url)).toMatch(/\/api\/v1\/session$/)
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({ user_id: 'u1' })
  })

  it('shows an error with Retry when the API cannot be reached', async () => {
    const fetchMock = vi
      .fn<typeof fetch>(async () => jsonResponse(USERS))
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
    vi.stubGlobal('fetch', fetchMock)
    renderPicker()

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Cannot reach the JagaLink server')
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }))

    expect(await screen.findByRole('button', { name: /Guard A/ })).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Run, Session } from '../../api/types'
import type { MapAlert } from '../../components/map/mapShapes'
import { playCue } from '../../lib/cue'
import { useSession } from '../../lib/session'
import { alertFrame, GUARD_C, handled, SUPERVISOR_REF, testAlert } from '../../test/alerts'
import { jsonResponse } from '../../test/http'
import { testLayout } from '../layout-editor/testLayout'
import { ConsolePage } from './ConsolePage'

vi.mock('../../lib/cue', () => ({ playCue: vi.fn() }))

// Konva needs a real canvas, so the map becomes a list of the alert marks it would draw.
vi.mock('../../components/map/CommunityMap', async () => {
  const { createElement } = await import('react')
  const map = ({ alerts }: { alerts?: MapAlert[] }) =>
    createElement(
      'ul',
      { 'aria-label': 'Alert marks' },
      (alerts ?? []).map((alert) =>
        createElement(
          'li',
          { key: alert.id },
          `${alert.severity} ${alert.nodeId}>${alert.nextNodeId ?? 'none'}`,
        ),
      ),
    )
  return { CommunityMap: map }
})

const GUARD: Session = {
  token: 'signed-token',
  expires_at: '2026-10-21T13:14:00.000Z',
  user: { ...GUARD_C, on_duty: true },
  community_id: 'c1',
}

const RUN: Run = {
  id: 'r1',
  scenario_id: 's2',
  scenario_code: 's2-night-fence',
  scenario_name: 'S2 · Person crossing from the back fence at night',
  mode: 'live',
  speed: 10,
  state: 'playing',
  started_at: '2026-10-20T10:00:00.000Z',
  window_start: '2026-10-21T18:08:00.000Z',
  window_end: '2026-10-21T18:18:00.000Z',
  clock: '2026-10-21T18:10:00.000Z',
  events_emitted: 3,
  events_total: 15,
}

/** An SSE response that stays open until the request is aborted; `push` sends more down it. */
function openStream(signal?: AbortSignal | null) {
  let controller: ReadableStreamDefaultController<Uint8Array> | undefined
  const body = new ReadableStream<Uint8Array>({
    start(opened) {
      controller = opened
      signal?.addEventListener('abort', () => opened.error(new Error('aborted')))
    },
  })
  return {
    response: new Response(body, { headers: { 'Content-Type': 'text/event-stream' } }),
    push: (text: string) => controller?.enqueue(new TextEncoder().encode(text)),
  }
}

type Handler = (url: string, init?: RequestInit) => Response | undefined

/** Serves the console's API; the run's stream starts with `frames`, and `stream.push` adds more. */
function serve(run: Run | null, frames: string, handler: Handler = () => undefined) {
  const stream = { push: (text: string): unknown => text }
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input)
    const answer = handler(url, init)
    if (answer) return answer
    if (url.endsWith('/communities/c1/layout')) return jsonResponse(testLayout())
    if (url.endsWith('/scenario-runs/current')) return jsonResponse(run)
    if (url.includes('/stream?run_id=r1')) {
      const opened = openStream(init?.signal)
      stream.push = opened.push
      opened.push(frames)
      return opened.response
    }
    throw new Error(`unexpected request ${init?.method ?? 'GET'} ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return { fetchMock, stream }
}

function renderConsole(session: Session = GUARD) {
  useSession.getState().signIn(session)
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/console']}>
        <Routes>
          <Route path="/console" element={<ConsolePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const cards = () =>
  within(screen.getByRole('region', { name: 'Alerts' })).queryAllByRole('article')

const findCard = (name: string) => screen.findByRole('article', { name })

describe('ConsolePage', () => {
  beforeEach(() => {
    vi.mocked(playCue).mockClear()
  })

  it('shows each alert as a card, open and most severe first, and rings it on the map', async () => {
    serve(
      RUN,
      alertFrame('alert', testAlert('a1')) +
        alertFrame(
          'alert',
          testAlert('a2', {
            severity: 'high',
            rule: 'off_route',
            rule_name: 'Off-route movement',
            node_id: 'b',
            next_node: null,
            created_ts: '2026-10-21T18:10:19.500Z',
          }),
        ) +
        alertFrame(
          'alert_update',
          handled(testAlert('a3', { node_id: 'c' }), 'dismiss', SUPERVISOR_REF, 'A resident'),
        ),
    )
    renderConsole()

    await waitFor(() => expect(cards()).toHaveLength(3))
    expect(cards().map((card) => card.getAttribute('aria-label'))).toEqual([
      'high alert: Off-route movement at c-b',
      'medium alert: After-hours entry at c-a',
      'medium alert: After-hours entry at c-c',
    ])
    const [offRoute, afterHours, dismissed] = cards().map((card) => within(card))
    expect(offRoute.getByText('No camera links onward')).toBeTruthy()
    expect(afterHours.getByText('New')).toBeTruthy()
    expect(afterHours.getByText('02:10:00')).toBeTruthy()
    expect(afterHours.getByText(/^Next/).textContent).toBe('Next c-b · 30 m · 16 s · 40 % of routes')
    expect(afterHours.getByText(/Guard C/).textContent).toBe('→ Guard C (you) · 116 s away')
    expect(dismissed.getByText(/Dismissed by/).textContent).toBe(
      'Dismissed by Supervisor at 02:18:00 — “A resident”',
    )
    expect(dismissed.queryByRole('button', { name: 'Confirm' })).toBeNull()
    expect(screen.getByText('2 open')).toBeTruthy()

    const marks = within(screen.getByRole('list', { name: 'Alert marks' })).getAllByRole('listitem')
    expect(marks.map((mark) => mark.textContent)).toEqual(['high b>none', 'medium a>b'])
    await waitFor(() => expect(playCue).toHaveBeenCalledTimes(1))
  })

  it('confirms with a one-line reason in one click and says who did it', async () => {
    const alert = testAlert('a1')
    const { fetchMock } = serve(RUN, alertFrame('alert', alert), (url, init) =>
      init?.method === 'POST' && url.endsWith('/alerts/a1/actions')
        ? jsonResponse(handled(alert, 'confirm', GUARD_C, 'Resident walking a dog'))
        : undefined,
    )
    renderConsole()

    const card = await findCard('medium alert: After-hours entry at c-a')
    fireEvent.change(within(card).getByLabelText('Reason'), {
      target: { value: '  Resident walking a dog ' },
    })
    fireEvent.click(within(card).getByRole('button', { name: 'Confirm' }))

    await waitFor(() =>
      expect(within(card).getByText(/Confirmed by/).textContent).toBe(
        'Confirmed by Guard C (you) at 02:18:00 — “Resident walking a dog”',
      ),
    )
    const posts = fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')
    expect(posts).toHaveLength(1)
    expect(JSON.parse(String(posts[0][1]?.body))).toEqual({
      action: 'confirm',
      reason: 'Resident walking a dog',
    })
    expect(within(card).queryByRole('button', { name: 'Confirm' })).toBeNull()
    expect(screen.getByText('0 open')).toBeTruthy()
  })

  it('follows actions taken on another screen and chimes only for new open alerts', async () => {
    const alert = testAlert('a1')
    const { stream } = serve(RUN, alertFrame('alert', alert))
    renderConsole()

    const card = await findCard('medium alert: After-hours entry at c-a')
    await waitFor(() => expect(playCue).toHaveBeenCalledTimes(1))

    stream.push(alertFrame('alert_update', handled(alert, 'dismiss', SUPERVISOR_REF)))
    await waitFor(() =>
      expect(within(card).getByText(/Dismissed by/).textContent).toBe(
        'Dismissed by Supervisor at 02:18:00',
      ),
    )
    // A late copy of the original message changes nothing.
    stream.push(alertFrame('alert', alert))

    stream.push(
      alertFrame('alert', testAlert('a2', { severity: 'high', node_id: 'b' })) +
        alertFrame('alert', testAlert('a3', { severity: 'low', node_id: 'c' })),
    )
    await waitFor(() => expect(cards()).toHaveLength(3))
    await waitFor(() => expect(playCue).toHaveBeenCalledTimes(2))
    await new Promise((resolve) => setTimeout(resolve, 300))
    expect(playCue).toHaveBeenCalledTimes(2)
    expect(within(card).getByText('Dismissed')).toBeTruthy()
  })

  it('says so when someone else handled the alert first', async () => {
    serve(RUN, alertFrame('alert', testAlert('a1')), (url, init) =>
      init?.method === 'POST' && url.endsWith('/alerts/a1/actions')
        ? jsonResponse(
            {
              code: 'alert_already_handled',
              message: 'The alert was dismissed already',
              details: 'dismissed',
            },
            409,
          )
        : undefined,
    )
    renderConsole()

    const card = await findCard('medium alert: After-hours entry at c-a')
    fireEvent.click(within(card).getByRole('button', { name: 'Dismiss' }))
    expect((await within(card).findByRole('alert')).textContent).toBe(
      'Someone has already handled this alert.',
    )
  })

  it('waits for a scenario when none is running', async () => {
    serve(null, '')
    renderConsole()

    expect(await screen.findByText('No scenario is running.')).toBeTruthy()
    expect(screen.getByText('No scenario is running. Alerts show here once one plays.')).toBeTruthy()
    expect(cards()).toHaveLength(0)
  })
})

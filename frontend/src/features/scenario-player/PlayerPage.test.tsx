import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { RunEvent, Run, Scenario, Session, Track } from '../../api/types'
import type { MapHighlights } from '../../components/map/CommunityMap'
import type { MapPath } from '../../components/map/mapShapes'
import { useSession } from '../../lib/session'
import { jsonResponse } from '../../test/http'
import { testLayout } from '../layout-editor/testLayout'
import { PlayerPage } from './PlayerPage'

// Konva needs a real canvas, so the map becomes lists of the cameras it would light up and the
// paths it would draw.
vi.mock('../../components/map/CommunityMap', async () => {
  const { createElement, Fragment } = await import('react')
  const map = ({ highlights, paths }: { highlights?: MapHighlights; paths?: MapPath[] }) =>
    createElement(
      Fragment,
      null,
      createElement(
        'ul',
        { 'aria-label': 'Cameras in view' },
        [...(highlights?.occupied ?? [])].map((id) => createElement('li', { key: id }, id)),
      ),
      createElement(
        'ul',
        { 'aria-label': 'Paths' },
        (paths ?? []).map((path) =>
          createElement(
            'li',
            { key: path.id },
            `${path.label} ${path.nodeIds.join('>')}${path.active ? '' : ' (closed)'}`,
          ),
        ),
      ),
    )
  return { CommunityMap: map }
})

const SUPERVISOR: Session = {
  token: 'signed-token',
  expires_at: '2026-10-21T13:14:00.000Z',
  user: { id: 'u0', code: 'u-sup-01', name: 'Supervisor', role: 'supervisor', on_duty: true },
  community_id: 'c1',
}

const SCENARIOS: Scenario[] = [
  {
    id: 's1',
    code: 's1-evening-vehicle',
    name: 'S1 · Vehicle circling the south lanes',
    description: 'An unfamiliar vehicle loops the south lanes.',
    duration_s: 840,
    default_speed: 10,
    window_start: '2026-10-21T11:18:00.000Z',
    window_end: '2026-10-21T11:32:00.000Z',
  },
  {
    id: 's2',
    code: 's2-night-fence',
    name: 'S2 · Person crossing from the back fence at night',
    description: 'A person comes over the back fence.',
    duration_s: 600,
    default_speed: 10,
    window_start: '2026-10-21T18:08:00.000Z',
    window_end: '2026-10-21T18:18:00.000Z',
  },
]

function playing(scenario: Scenario): Run {
  return {
    id: 'r1',
    scenario_id: scenario.id,
    scenario_code: scenario.code,
    scenario_name: scenario.name,
    mode: 'live',
    speed: 10,
    state: 'playing',
    started_at: '2026-10-20T10:00:00.000Z',
    window_start: scenario.window_start,
    window_end: scenario.window_end,
    clock: scenario.window_start,
    events_emitted: 0,
    events_total: 15,
  }
}

function frame(seq: number, nodeId: string, type: RunEvent['type'], localTrackId: string) {
  const event: RunEvent = {
    id: `e${seq}`,
    run_id: 'r1',
    seq,
    ts: `2026-10-21T18:10:0${seq}.000Z`,
    node_id: nodeId,
    type,
    object_class: 'person',
    local_track_id: localTrackId,
    attrs: {},
    source: 'sim',
  }
  return `id: ${seq}\nevent: event\ndata: ${JSON.stringify(event)}\n\n`
}

function trackFrame(seq: number, id: string, nodeIds: string[], status: Track['status']) {
  const track: Track = {
    id,
    run_id: 'r1',
    anon_id: `obj-${id}`,
    object_class: 'person',
    status,
    first_ts: '2026-10-21T18:10:00.000Z',
    last_ts: '2026-10-21T18:12:00.000Z',
    expires_at: '2026-10-22T18:12:00.000Z',
    segments: nodeIds.map((nodeId) => ({
      node_id: nodeId,
      enter_ts: '2026-10-21T18:10:00.000Z',
      exit_ts: null,
      event_ids: [],
    })),
  }
  return `id: ${seq}
event: track_update
data: ${JSON.stringify(track)}

`
}

/** An SSE response that sends `text` and stays open until the request is aborted. */
function sseResponse(text: string, signal?: AbortSignal | null): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text))
      signal?.addEventListener('abort', () => controller.error(new Error('aborted')))
    },
  })
  return new Response(body, { headers: { 'Content-Type': 'text/event-stream' } })
}

type Handler = (url: string, init?: RequestInit) => Response | undefined

function serve(run: Run | null, handler: Handler = () => undefined) {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input)
    const answer = handler(url, init)
    if (answer) return answer
    if (url.endsWith('/communities/c1/layout')) return jsonResponse(testLayout())
    if (url.endsWith('/scenarios')) return jsonResponse(SCENARIOS)
    if (url.endsWith('/scenario-runs/current')) return jsonResponse(run)
    throw new Error(`unexpected request ${init?.method ?? 'GET'} ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderPlayer(session: Session = SUPERVISOR) {
  useSession.getState().signIn(session)
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/player']}>
        <Routes>
          <Route path="/player" element={<PlayerPage />} />
          <Route path="/console" element={<p>Console page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function calls(fetchMock: ReturnType<typeof serve>, method: string, path: string) {
  return fetchMock.mock.calls.filter(
    ([input, init]) => (init?.method ?? 'GET') === method && String(input).endsWith(path),
  )
}

describe('PlayerPage', () => {
  it('plays the picked scenario at the picked speed', async () => {
    const fetchMock = serve(null, (url, init) =>
      init?.method === 'POST' && url.endsWith('/scenario-runs')
        ? jsonResponse(playing(SCENARIOS[1]), 201)
        : undefined,
    )
    renderPlayer()

    fireEvent.change(await screen.findByLabelText('Scenario'), { target: { value: 's2' } })
    fireEvent.change(screen.getByLabelText('Speed'), { target: { value: '30' } })
    fireEvent.click(screen.getByRole('button', { name: 'Play' }))

    await waitFor(() => expect(calls(fetchMock, 'POST', '/scenario-runs')).toHaveLength(1))
    const [, init] = calls(fetchMock, 'POST', '/scenario-runs')[0]
    expect(JSON.parse(String(init?.body))).toEqual({ scenario_id: 's2', speed: 30 })
    expect(await screen.findByText('Playing')).toBeTruthy()
  })

  it('shows streamed events in the feed and lights the cameras with an object in view', async () => {
    const fetchMock = serve(playing(SCENARIOS[1]), (url, init) => {
      if (url.includes('/stream?run_id=r1')) {
        return sseResponse(
          frame(1, 'a', 'appear', 'c-a#1') +
            frame(2, 'b', 'appear', 'c-b#1') +
            ': ping\n\n' +
            frame(3, 'b', 'disappear', 'c-b#1'),
          init?.signal,
        )
      }
      if (url.endsWith('/scenario-runs/r1/pause')) {
        return jsonResponse({ ...playing(SCENARIOS[1]), state: 'paused' })
      }
      return undefined
    })
    renderPlayer()

    expect(await screen.findByText('c-a#1')).toBeTruthy()
    await waitFor(() => expect(screen.getAllByText('c-b#1')).toHaveLength(2))
    const inView = screen.getByRole('list', { name: 'Cameras in view' })
    expect(inView.textContent).toBe('a')
    expect(screen.getByText('Live')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Pause' }))
    await waitFor(() => expect(calls(fetchMock, 'POST', '/scenario-runs/r1/pause')).toHaveLength(1))
    expect(await screen.findByText('Paused')).toBeTruthy()
  })

  it('draws each anonymous path as it grows and drops it once it expires', async () => {
    serve(playing(SCENARIOS[1]), (url, init) =>
      url.includes('/stream?run_id=r1')
        ? sseResponse(
            trackFrame(1, 'f1a2b3', ['a'], 'active') +
              trackFrame(2, 'c4d5e6', ['c'], 'closed') +
              trackFrame(3, 'f1a2b3', ['a', 'b'], 'active') +
              trackFrame(4, 'a0b0c0', ['d'], 'active') +
              trackFrame(5, 'a0b0c0', ['d'], 'expired'),
            init?.signal,
          )
        : undefined,
    )
    renderPlayer()

    const paths = await screen.findByRole('list', { name: 'Paths' })
    await waitFor(() =>
      expect(within(paths).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
        'obj-f1a2b3 a>b',
        'obj-c4d5e6 c (closed)',
      ]),
    )
  })

  it('lists each reason a scenario cannot play', async () => {
    serve(null, (url, init) =>
      init?.method === 'POST' && url.endsWith('/scenario-runs')
        ? jsonResponse(
            {
              code: 'scenario_does_not_fit',
              message: "The scenario no longer fits the community's layout or staff",
              details: ['t1 visit 2: no link c-back-02 -> c-lane-2n'],
            },
            409,
          )
        : undefined,
    )
    renderPlayer()

    fireEvent.click(await screen.findByRole('button', { name: 'Play' }))

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('no longer fits')
    expect(alert.textContent).toContain('t1 visit 2: no link c-back-02 -> c-lane-2n')
  })

  it('sends a guard to the console', () => {
    serve(null)
    renderPlayer({ ...SUPERVISOR, user: { ...SUPERVISOR.user, role: 'guard' } })
    expect(screen.getByText('Console page')).toBeTruthy()
  })
})

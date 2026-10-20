import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import type { Dispatch } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { Layout, LayoutInput, Session } from '../../api/types'
import { useSession } from '../../lib/session'
import { jsonResponse } from '../../test/http'
import { EditorPage } from './EditorPage'
import type { EditorAction } from './editorState'
import { testLayout } from './testLayout'

// Konva needs a real canvas, so the canvas becomes buttons that send the actions a click would.
vi.mock('./EditorCanvas', async () => {
  const { createElement } = await import('react')
  const canvas = (props: { dispatch: Dispatch<EditorAction>; newId: () => string }) => {
    const button = (label: string, actions: EditorAction[]) =>
      createElement(
        'button',
        { type: 'button', onClick: () => actions.forEach(props.dispatch) },
        label,
      )
    return createElement(
      'div',
      null,
      button('Place a camera', [
        { type: 'addNode', id: '7c3e1f52-0000-4000-8000-000000000001', kind: 'camera', x: 600, y: 200 },
      ]),
      button('Link a to itself', [
        { type: 'setTool', tool: 'link' },
        { type: 'pickLinkEnd', nodeId: 'a', linkId: 'l1' },
        { type: 'pickLinkEnd', nodeId: 'a', linkId: 'l1' },
      ]),
    )
  }
  return { EditorCanvas: canvas }
})

const SUPERVISOR: Session = {
  token: 'signed-token',
  expires_at: '2026-10-21T13:14:00.000Z',
  user: { id: 'u0', code: 'u-sup-01', name: 'Supervisor', role: 'supervisor', on_duty: true },
  community_id: 'c1',
}

type Handler = (url: string, init?: RequestInit) => Response | Promise<Response>

function serve(handler: Handler) {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => handler(String(input), init))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderEditor(session: Session = SUPERVISOR) {
  useSession.getState().signIn(session)
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/editor']}>
        <Routes>
          <Route path="/editor" element={<EditorPage />} />
          <Route path="/console" element={<p>Console page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

/** The layout the API would answer after saving this body. */
function stored(body: LayoutInput): Layout {
  const { community, zones } = testLayout()
  return {
    community,
    zones,
    nodes: body.nodes.map((node) => ({ ...node, zone_id: node.zone_id ?? null })),
    links: body.links.map((link) => ({
      ...link,
      id: link.id ?? 'new',
      distance_m: link.distance_m ?? null,
    })),
  }
}

describe('EditorPage', () => {
  it('sends a guard back to the console', async () => {
    serve(() => jsonResponse(testLayout()))
    renderEditor({ ...SUPERVISOR, user: { ...SUPERVISOR.user, role: 'guard' } })
    expect(await screen.findByText('Console page')).toBeTruthy()
  })

  it('saves a new camera and shows the layout as saved', async () => {
    const fetchMock = serve((_, init) =>
      init?.method === 'PUT'
        ? jsonResponse(stored(JSON.parse(String(init.body))))
        : jsonResponse(testLayout()),
    )
    renderEditor()

    fireEvent.click(await screen.findByRole('button', { name: 'Place a camera' }))
    expect(screen.getByRole('status').textContent).toBe('Unsaved changes')
    const panel = screen.getByRole('complementary', { name: 'Properties' })
    fireEvent.change(within(panel).getByLabelText('Name'), { target: { value: 'Clubhouse gate' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('All changes saved')).toBeTruthy()
    const [url, init] = fetchMock.mock.calls.find(([, call]) => call?.method === 'PUT')!
    expect(String(url)).toMatch(/\/api\/v1\/communities\/c1\/layout$/)
    const body = JSON.parse(String(init?.body)) as LayoutInput
    expect(body.nodes).toHaveLength(4)
    expect(body.nodes[3]).toMatchObject({
      code: 'c-new-01',
      name: 'Clubhouse gate',
      x: 600,
      y: 200,
      zone_id: 'z-street',
    })
    expect(body.links).toHaveLength(2)
  })

  it("shows the server's refusal and keeps the edits", async () => {
    const refusal = {
      code: 'duplicate_link',
      message: 'link c-b -> c-a duplicates another link (and 1 more)',
      details: {
        problems: [
          { code: 'duplicate_link', message: 'link c-b -> c-a duplicates another link' },
          { code: 'duplicate_link', message: 'link c-c -> c-b duplicates another link' },
        ],
      },
    }
    serve((_, init) =>
      init?.method === 'PUT' ? jsonResponse(refusal, 409) : jsonResponse(testLayout()),
    )
    renderEditor()

    fireEvent.click(await screen.findByRole('button', { name: 'Place a camera' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('The layout was not saved')
    expect(alert.textContent).toContain(refusal.message)
    expect(within(alert).getAllByRole('listitem').map((item) => item.textContent)).toEqual(
      refusal.details.problems.map((problem) => problem.message),
    )
    expect(screen.getByRole('status').textContent).toBe('Unsaved changes')
  })

  it('refuses a self-link on screen', async () => {
    serve(() => jsonResponse(testLayout()))
    renderEditor()

    fireEvent.click(await screen.findByRole('button', { name: 'Link a to itself' }))

    expect(screen.getByRole('alert').textContent).toContain(
      'Refused: a link cannot join c-a to itself.',
    )
    expect(screen.getByRole('status').textContent).toBe('All changes saved')
  })

  it('exports the saved layout as a file named after the community', async () => {
    const file = { community: { slug: 'taman-ujian' }, zones: [], nodes: [], links: [] }
    serve((url) => jsonResponse(url.endsWith('/export') ? file : testLayout()))
    const createObjectURL = vi.fn((_blob: Blob) => 'blob:layout')
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }))
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    renderEditor()

    fireEvent.click(await screen.findByRole('button', { name: 'Export' }))

    await vi.waitFor(() => expect(click).toHaveBeenCalledOnce())
    const anchor = click.mock.contexts[0] as HTMLAnchorElement
    expect(anchor.download).toBe('taman-ujian.json')
    const blob = createObjectURL.mock.calls[0][0]
    expect(JSON.parse(await blob.text())).toEqual(file)
    click.mockRestore()
  })

  it('imports a layout file and refuses one that is not JSON', async () => {
    const imported = { ...testLayout(), nodes: testLayout().nodes.slice(0, 1), links: [] }
    const fetchMock = serve((url) =>
      jsonResponse(url.endsWith('/import') ? imported : testLayout()),
    )
    renderEditor()
    const input = await screen.findByLabelText('Layout file to import')

    const broken = new File(['{ not json'], 'broken.json', { type: 'application/json' })
    fireEvent.change(input, { target: { files: [broken] } })
    expect((await screen.findByRole('alert')).textContent).toContain(
      'broken.json is not a JSON layout file.',
    )

    const layoutFile = { community: { slug: 'taman-ujian' }, nodes: [], links: [] }
    const good = new File([JSON.stringify(layoutFile)], 'layout.json')
    fireEvent.change(input, { target: { files: [good] } })

    expect(await screen.findByText('1 nodes · 0 links')).toBeTruthy()
    const [, init] = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/import'))!
    expect(JSON.parse(String(init?.body))).toEqual(layoutFile)
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

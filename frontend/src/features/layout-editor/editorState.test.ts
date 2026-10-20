import { describe, expect, it } from 'vitest'
import {
  type EditorAction,
  editorReducer,
  type EditorState,
  headingTowards,
  initEditor,
  isDirty,
  toLayoutInput,
  walkingTimes,
  zoneAt,
} from './editorState'
import { testLayout } from './testLayout'

function run(...actions: EditorAction[]): EditorState {
  return actions.reduce(editorReducer, initEditor(testLayout()))
}

const link = (from: string, to: string, linkId = `${from}${to}`): EditorAction[] => [
  { type: 'setTool', tool: 'link' },
  { type: 'pickLinkEnd', nodeId: from, linkId },
  { type: 'pickLinkEnd', nodeId: to, linkId },
]

const node = (state: EditorState, id: string) => state.draft.nodes.find((item) => item.id === id)!

describe('editorReducer', () => {
  it('starts from the loaded layout with nothing to save', () => {
    const state = run()
    expect(state.draft).toEqual({ nodes: testLayout().nodes, links: testLayout().links })
    expect(isDirty(state)).toBe(false)
  })

  it('places a camera with the next free code and the zone under it', () => {
    const state = run({ type: 'addNode', id: 'n1', kind: 'camera', x: 600.4, y: 199.6 })
    expect(node(state, 'n1')).toEqual({
      id: 'n1',
      code: 'c-new-01',
      kind: 'camera',
      name: 'New camera 1',
      x: 600,
      y: 200,
      heading_deg: 0,
      status: 'online',
      zone_id: 'z-street',
    })
    expect(state.selection).toEqual({ kind: 'node', id: 'n1' })
    expect(isDirty(state)).toBe(true)
  })

  it('numbers new cameras and sensors separately and keeps them on the map', () => {
    const state = run(
      { type: 'addNode', id: 'n1', kind: 'camera', x: 10, y: 10 },
      { type: 'addNode', id: 'n2', kind: 'camera', x: 2000, y: -50 },
      { type: 'addNode', id: 'n3', kind: 'sensor', x: 900, y: 700 },
    )
    expect(node(state, 'n2')).toMatchObject({ code: 'c-new-02', x: 1200, y: 0 })
    expect(node(state, 'n3')).toMatchObject({ code: 's-new-01', name: 'New sensor 1', zone_id: null })
  })

  it('moves a node and gives it the zone it is dropped in', () => {
    const dragging = run({ type: 'moveNode', id: 'a', x: 450, y: 120 })
    expect(node(dragging, 'a')).toMatchObject({ x: 450, y: 120, zone_id: 'z-lane' })
    const dropped = run({ type: 'moveNode', id: 'a', x: 450, y: 120, dropped: true })
    expect(node(dropped, 'a').zone_id).toBe('z-street')
    const outside = run({ type: 'moveNode', id: 'a', x: 900, y: 700, dropped: true })
    expect(node(outside, 'a').zone_id).toBe('z-lane')
  })

  it('is clean again once a node is moved back', () => {
    const state = run(
      { type: 'moveNode', id: 'a', x: 300, y: 300, dropped: true },
      { type: 'moveNode', id: 'a', x: 100, y: 100, dropped: true },
    )
    expect(isDirty(state)).toBe(false)
  })

  it('keeps headings in whole degrees from 0 to 359', () => {
    const turned = (heading: number) =>
      node(run({ type: 'updateNode', id: 'a', changes: { heading_deg: heading } }), 'a').heading_deg
    expect([turned(370), turned(-90), turned(359.6)]).toEqual([10, 270, 0])
  })

  it('links two nodes with walking times from their distance (D-69)', () => {
    const state = run(...link('a', 'c'))
    // 400 px at 0.25 m/px is 100 m: 71 s at 1.4 m/s, 84 s at 1.2 m/s.
    expect(state.draft.links.at(-1)).toEqual({
      id: 'ac',
      from_node_id: 'a',
      to_node_id: 'c',
      travel_min_s: 71,
      travel_max_s: 84,
      bidirectional: true,
      distance_m: 100,
    })
    expect(state.selection).toEqual({ kind: 'link', id: 'ac' })
    expect(state.notice).toBeNull()
  })

  it('refuses a self-link on screen', () => {
    const state = run(...link('a', 'a'))
    expect(state.draft.links).toHaveLength(2)
    expect(state.notice).toEqual({
      tone: 'error',
      text: 'Refused: a link cannot join c-a to itself.',
    })
  })

  it.each([
    ['the reverse of a two-way link', 'b', 'a'],
    ['the same direction as a one-way link', 'c', 'b'],
  ])('refuses %s as a duplicate (D-65)', (_, from, to) => {
    const state = run(...link(from, to))
    expect(state.draft.links).toHaveLength(2)
    expect(state.notice?.text).toBe(`Refused: c-${from} and c-${to} are already linked.`)
  })

  it('adds the opposite of a one-way link as one-way', () => {
    const state = run(...link('b', 'c'))
    expect(state.draft.links.at(-1)).toMatchObject({ from_node_id: 'b', bidirectional: false })
    expect(state.notice).toEqual({
      tone: 'info',
      text: 'Added as one-way c-b → c-c: c-c → c-b is one-way.',
    })
  })

  it('refuses to make a link two-way when that duplicates another', () => {
    const state = run(...link('b', 'c', 'bc'), {
      type: 'updateLink',
      id: 'bc',
      changes: { bidirectional: true },
    })
    expect(state.draft.links.find((item) => item.id === 'bc')?.bidirectional).toBe(false)
    expect(state.notice?.text).toBe('Refused: a two-way link would duplicate c-c → c-b.')
  })

  it('changes walking times and distance', () => {
    const state = run({
      type: 'updateLink',
      id: 'ab',
      changes: { travel_min_s: 30, travel_max_s: 40, distance_m: null },
    })
    expect(state.draft.links[0]).toMatchObject({ travel_min_s: 30, travel_max_s: 40, distance_m: null })
  })

  it('deletes a node together with its links', () => {
    const state = run({ type: 'select', selection: { kind: 'node', id: 'b' } }, { type: 'deleteSelection' })
    expect(state.draft.nodes.map((item) => item.id)).toEqual(['a', 'c'])
    expect(state.draft.links).toEqual([])
    expect(state.selection).toBeNull()
  })

  it('cancels a half-picked link first, then the selection', () => {
    const picked = run(
      { type: 'setTool', tool: 'link' },
      { type: 'pickLinkEnd', nodeId: 'a', linkId: 'x' },
    )
    expect(picked.linkStart).toBe('a')
    const cancelled = editorReducer(picked, { type: 'cancel' })
    expect(cancelled.linkStart).toBeNull()
    const selected = editorReducer(cancelled, {
      type: 'select',
      selection: { kind: 'node', id: 'b' },
    })
    expect(editorReducer(selected, { type: 'cancel' }).selection).toBeNull()
  })

  it('clears the draft and loads a saved layout', () => {
    const cleared = run({ type: 'clear' })
    expect(cleared.draft).toEqual({ nodes: [], links: [] })
    expect(isDirty(cleared)).toBe(true)

    const saved = { ...testLayout(), nodes: [], links: [] }
    const loaded = editorReducer(cleared, { type: 'loaded', layout: saved })
    expect(isDirty(loaded)).toBe(false)
  })

  it('keeps the selection across a save when the item still exists', () => {
    const state = run({ type: 'select', selection: { kind: 'node', id: 'a' } })
    expect(editorReducer(state, { type: 'loaded', layout: testLayout() }).selection).toEqual({
      kind: 'node',
      id: 'a',
    })
  })
})

describe('toLayoutInput', () => {
  it('sends only the fields the API accepts', () => {
    const state = run()
    const extra = { ...state.draft.nodes[0], label: 'not an API field' }
    const body = toLayoutInput({ nodes: [extra], links: state.draft.links })
    expect(Object.keys(body.nodes[0]).sort()).toEqual(
      ['code', 'heading_deg', 'id', 'kind', 'name', 'status', 'x', 'y', 'zone_id'],
    )
    expect(body.links[0]).toEqual(testLayout().links[0])
  })
})

describe('walkingTimes', () => {
  it.each([
    [60, 42, 50],
    [62.5, 44, 53],
    [30, 21, 25],
    [0, 1, 1],
  ])('turns %d m into %d–%d s, like the seeded layout', (meters, min, max) => {
    expect(walkingTimes(meters)).toEqual({ travel_min_s: min, travel_max_s: max })
  })
})

describe('headingTowards', () => {
  it.each([
    [0, -10, 0],
    [10, 0, 90],
    [0, 10, 180],
    [-10, 0, 270],
  ])('points at (%d, %d) as %d°', (x, y, heading) => {
    expect(headingTowards({ x: 0, y: 0 }, { x, y })).toBe(heading)
  })
})

describe('zoneAt', () => {
  it('finds the zone whose outline holds the point', () => {
    const { zones } = testLayout()
    expect(zoneAt(zones, 10, 10)).toBe('z-lane')
    expect(zoneAt(zones, 790, 390)).toBe('z-street')
    expect(zoneAt(zones, 900, 900)).toBeNull()
  })
})

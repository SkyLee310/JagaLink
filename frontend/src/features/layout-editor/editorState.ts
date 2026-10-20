import type {
  Layout,
  LayoutInput,
  LayoutLink,
  LayoutNode,
  LayoutZone,
} from '../../api/types'
import { MAP_SIZE } from '../../components/map/mapShapes'

/** The F1 layout editor's state as a pure reducer: every edit stays in the draft until Save. */

export type Tool = 'select' | 'camera' | 'sensor' | 'link'
export type NodeKind = LayoutNode['kind']
export type NodeChanges = Partial<Omit<LayoutNode, 'id'>>
export type LinkChanges = Partial<
  Pick<LayoutLink, 'travel_min_s' | 'travel_max_s' | 'bidirectional' | 'distance_m'>
>

export interface Draft {
  nodes: LayoutNode[]
  links: LayoutLink[]
}

export type Selection = { kind: 'node' | 'link'; id: string } | null

export interface Notice {
  tone: 'error' | 'info'
  text: string
}

export interface EditorState {
  community: Layout['community']
  /** Zones are seeded and read-only (D-64); nodes take theirs from the outline they sit in. */
  zones: LayoutZone[]
  /** The layout as the server last returned it. */
  saved: Draft
  draft: Draft
  tool: Tool
  selection: Selection
  /** The first node picked with the link tool. */
  linkStart: string | null
  notice: Notice | null
}

export type EditorAction =
  | { type: 'loaded'; layout: Layout }
  | { type: 'setTool'; tool: Tool }
  | { type: 'select'; selection: Selection }
  | { type: 'addNode'; id: string; kind: NodeKind; x: number; y: number }
  | { type: 'moveNode'; id: string; x: number; y: number; dropped?: boolean }
  | { type: 'updateNode'; id: string; changes: NodeChanges }
  | { type: 'pickLinkEnd'; nodeId: string; linkId: string }
  | { type: 'updateLink'; id: string; changes: LinkChanges }
  | { type: 'deleteSelection' }
  | { type: 'clear' }
  | { type: 'cancel' }
  | { type: 'dismissNotice' }

/** The editor's tools, each with its keyboard shortcut. */
export const TOOLS: { tool: Tool; label: string; key: string }[] = [
  { tool: 'select', label: 'Select', key: 'v' },
  { tool: 'camera', label: 'Camera', key: 'c' },
  { tool: 'sensor', label: 'Sensor', key: 's' },
  { tool: 'link', label: 'Link', key: 'l' },
]

/** Walking speeds that bound a new link's walking time, in m/s (D-69). */
export const WALK_SPEED = { slow: 1.2, fast: 1.4 }

const NEW_NODE: Record<NodeKind, { code: string; name: string }> = {
  camera: { code: 'c-new', name: 'New camera' },
  sensor: { code: 's-new', name: 'New sensor' },
}

export function initEditor(layout: Layout): EditorState {
  const draft = copyDraft(layout)
  return {
    community: layout.community,
    zones: layout.zones,
    saved: draft,
    draft,
    tool: 'select',
    selection: null,
    linkStart: null,
    notice: null,
  }
}

export function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case 'loaded': {
      const draft = copyDraft(action.layout)
      return {
        ...state,
        community: action.layout.community,
        zones: action.layout.zones,
        saved: draft,
        draft,
        selection: selectable(draft, state.selection),
        linkStart: null,
        notice: null,
      }
    }
    case 'setTool':
      return { ...state, tool: action.tool, linkStart: null, notice: null }
    case 'select':
      return { ...state, selection: action.selection, linkStart: null }
    case 'addNode': {
      const { x, y } = clampToMap(action.x, action.y)
      const number = nextNumber(action.kind, state.draft.nodes)
      const node: LayoutNode = {
        id: action.id,
        code: `${NEW_NODE[action.kind].code}-${String(number).padStart(2, '0')}`,
        kind: action.kind,
        name: `${NEW_NODE[action.kind].name} ${number}`,
        x,
        y,
        heading_deg: 0,
        status: 'online',
        zone_id: zoneAt(state.zones, x, y),
      }
      return {
        ...state,
        draft: { ...state.draft, nodes: [...state.draft.nodes, node] },
        selection: { kind: 'node', id: node.id },
        notice: null,
      }
    }
    case 'moveNode': {
      const { x, y } = clampToMap(action.x, action.y)
      // A dropped node takes the zone it now sits in; outside every zone it keeps its own.
      return withNode(state, action.id, (node) => ({
        ...node,
        x,
        y,
        zone_id: action.dropped ? (zoneAt(state.zones, x, y) ?? node.zone_id) : node.zone_id,
      }))
    }
    case 'updateNode': {
      const { heading_deg: heading, ...changes } = action.changes
      return withNode(state, action.id, (node) => ({
        ...node,
        ...changes,
        ...(heading === undefined ? {} : { heading_deg: normalizeHeading(heading) }),
      }))
    }
    case 'pickLinkEnd':
      return pickLinkEnd(state, action.nodeId, action.linkId)
    case 'updateLink': {
      const link = state.draft.links.find((item) => item.id === action.id)
      if (!link) return state
      const next = { ...link, ...action.changes }
      const clash = state.draft.links.find((other) => other.id !== link.id && sameLink(other, next))
      if (clash) {
        const text = `Refused: a two-way link would duplicate ${arrow(state, clash)}.`
        return { ...state, notice: { tone: 'error', text } }
      }
      return {
        ...state,
        draft: {
          ...state.draft,
          links: state.draft.links.map((item) => (item.id === link.id ? next : item)),
        },
        notice: null,
      }
    }
    case 'deleteSelection': {
      const { selection } = state
      if (!selection) return state
      const { nodes, links } = state.draft
      const draft =
        selection.kind === 'node'
          ? {
              nodes: nodes.filter((node) => node.id !== selection.id),
              links: links.filter((link) => !touches(link, selection.id)),
            }
          : { nodes, links: links.filter((link) => link.id !== selection.id) }
      return { ...state, draft, selection: null, linkStart: null, notice: null }
    }
    case 'clear':
      return {
        ...state,
        draft: { nodes: [], links: [] },
        selection: null,
        linkStart: null,
        notice: null,
      }
    case 'cancel':
      return state.linkStart
        ? { ...state, linkStart: null, notice: null }
        : { ...state, selection: null, notice: null }
    case 'dismissNotice':
      return { ...state, notice: null }
  }
}

/** The link tool: the first pick marks node A, the second adds the link A → B (F1). */
function pickLinkEnd(state: EditorState, nodeId: string, linkId: string): EditorState {
  const start = state.linkStart
  if (start === null || !findNode(state, start)) {
    return { ...state, linkStart: nodeId, selection: null, notice: null }
  }
  const from = findNode(state, start)!
  const to = findNode(state, nodeId)
  if (!to) return state
  if (from.id === to.id) {
    const text = `Refused: a link cannot join ${from.code} to itself.`
    return { ...state, linkStart: null, notice: { tone: 'error', text } }
  }

  const distance = distanceM(from, to, state.community.scale_m_per_px)
  const candidate: LayoutLink = {
    id: linkId,
    from_node_id: from.id,
    to_node_id: to.id,
    ...walkingTimes(distance ?? 0),
    bidirectional: true,
    distance_m: distance,
  }
  // D-65: a two-way link duplicates any link between the same nodes. Only when the other way is
  // one-way, and this way is still free, can a one-way link be added.
  const links = state.draft.links
  const twoWayClash = links.find((link) => sameLink(link, candidate))
  const oneWayClash = links.find((link) => sameLink(link, { ...candidate, bidirectional: false }))
  if (oneWayClash) {
    const text = `Refused: ${from.code} and ${to.code} are already linked.`
    return { ...state, linkStart: null, notice: { tone: 'error', text } }
  }
  const link = twoWayClash ? { ...candidate, bidirectional: false } : candidate
  const reverse = twoWayClash && arrow(state, twoWayClash)
  const notice: Notice | null = reverse
    ? { tone: 'info', text: `Added as one-way ${from.code} → ${to.code}: ${reverse} is one-way.` }
    : null
  return {
    ...state,
    draft: { ...state.draft, links: [...links, link] },
    selection: { kind: 'link', id: link.id },
    linkStart: null,
    notice,
  }
}

/** D-65: (A, B) and (B, A) are one link when either is two-way; the same direction always is. */
export function sameLink(a: LayoutLink, b: LayoutLink): boolean {
  if (a.from_node_id === b.from_node_id && a.to_node_id === b.to_node_id) return true
  const reverse = a.from_node_id === b.to_node_id && a.to_node_id === b.from_node_id
  return reverse && (a.bidirectional || b.bidirectional)
}

/** Walking-time window for a distance, at 1.4 m/s (fastest) to 1.2 m/s (slowest), D-69. */
export function walkingTimes(meters: number): { travel_min_s: number; travel_max_s: number } {
  // The small offsets keep float noise, such as 60 / 1.2 = 50.000…01, from moving a bound.
  const min = Math.max(1, Math.floor(meters / WALK_SPEED.fast + 1e-9))
  const max = Math.max(min, Math.ceil(meters / WALK_SPEED.slow - 1e-9))
  return { travel_min_s: min, travel_max_s: max }
}

/** Straight-line distance between two nodes in metres, to the nearest 0.5 m; null when 0. */
export function distanceM(a: LayoutNode, b: LayoutNode, metersPerPx: number): number | null {
  const meters = Math.round(Math.hypot(b.x - a.x, b.y - a.y) * metersPerPx * 2) / 2
  return meters > 0 ? meters : null
}

/** The zone whose outline holds the point, or null. */
export function zoneAt(zones: LayoutZone[], x: number, y: number): string | null {
  return zones.find((zone) => insidePolygon(zone.polygon, x, y))?.id ?? null
}

function insidePolygon(polygon: LayoutZone['polygon'], x: number, y: number): boolean {
  let inside = false
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i]
    const [xj, yj] = polygon[j]
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

/** Headings are whole degrees, 0 = up, clockwise, in [0, 360). */
export function normalizeHeading(degrees: number): number {
  return ((Math.round(degrees) % 360) + 360) % 360
}

/** Heading from one point towards another. */
export function headingTowards(from: { x: number; y: number }, to: { x: number; y: number }) {
  return normalizeHeading((Math.atan2(to.x - from.x, from.y - to.y) * 180) / Math.PI)
}

export function clampToMap(x: number, y: number): { x: number; y: number } {
  const clamp = (value: number, max: number) => Math.min(max, Math.max(0, Math.round(value)))
  return { x: clamp(x, MAP_SIZE.width), y: clamp(y, MAP_SIZE.height) }
}

export function isDirty(state: EditorState): boolean {
  return canonical(state.draft) !== canonical(state.saved)
}

/** The PUT body for the draft, with only the fields the API accepts. */
export function toLayoutInput({ nodes, links }: Draft): LayoutInput {
  return {
    nodes: nodes.map(({ id, code, kind, name, x, y, heading_deg, status, zone_id }) => ({
      id,
      code,
      kind,
      name,
      x,
      y,
      heading_deg,
      status,
      zone_id,
    })),
    links: links.map((link) => ({
      id: link.id,
      from_node_id: link.from_node_id,
      to_node_id: link.to_node_id,
      travel_min_s: link.travel_min_s,
      travel_max_s: link.travel_max_s,
      bidirectional: link.bidirectional,
      distance_m: link.distance_m,
    })),
  }
}

export function findNode(state: EditorState, id: string): LayoutNode | undefined {
  return state.draft.nodes.find((node) => node.id === id)
}

/** "c-a → c-b" for a one-way link, "c-a ↔ c-b" for a two-way one. */
export function arrow(state: EditorState, link: LayoutLink): string {
  const code = (id: string) => findNode(state, id)?.code ?? '?'
  return `${code(link.from_node_id)} ${link.bidirectional ? '↔' : '→'} ${code(link.to_node_id)}`
}

function copyDraft(layout: Layout): Draft {
  return {
    nodes: layout.nodes.map((node) => ({ ...node })),
    links: layout.links.map((link) => ({ ...link })),
  }
}

function canonical({ nodes, links }: Draft): string {
  return JSON.stringify({
    nodes: [...nodes]
      .sort((a, b) => a.id.localeCompare(b.id))
      .map((n) => [n.id, n.code, n.kind, n.name, n.x, n.y, n.heading_deg, n.status, n.zone_id]),
    links: links
      .map((l) =>
        JSON.stringify([
          l.from_node_id,
          l.to_node_id,
          l.travel_min_s,
          l.travel_max_s,
          l.bidirectional,
          l.distance_m,
        ]),
      )
      .sort(),
  })
}

function nextNumber(kind: NodeKind, nodes: LayoutNode[]): number {
  const codes = new Set(nodes.map((node) => node.code))
  let number = 1
  while (codes.has(`${NEW_NODE[kind].code}-${String(number).padStart(2, '0')}`)) number += 1
  return number
}

function withNode(
  state: EditorState,
  id: string,
  change: (node: LayoutNode) => LayoutNode,
): EditorState {
  if (!findNode(state, id)) return state
  const nodes = state.draft.nodes.map((node) => (node.id === id ? change(node) : node))
  return { ...state, draft: { ...state.draft, nodes } }
}

function touches(link: LayoutLink, nodeId: string): boolean {
  return link.from_node_id === nodeId || link.to_node_id === nodeId
}

function selectable(draft: Draft, selection: Selection): Selection {
  if (!selection) return null
  const items = selection.kind === 'node' ? draft.nodes : draft.links
  return items.some((item) => item.id === selection.id) ? selection : null
}

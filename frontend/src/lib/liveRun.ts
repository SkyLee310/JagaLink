import type { SseMessage } from '../api/sse'
import type { RunEvent, Track } from '../api/types'

/** How long a camera stays lit after its latest event, in wall milliseconds. */
export const FLASH_MS = 1500
/** The feed keeps this many events; older ones stay in the database (GET /events). */
export const MAX_EVENTS = 300

/** What the stream (D-36) has told the page about one run so far. */
export interface LiveRun {
  events: RunEvent[]
  /** Local track IDs each node has in view right now, by node ID. */
  inView: Record<string, string[]>
  /** When each node's latest event arrived (Date.now()), for the flash on the map. */
  lastSeen: Record<string, number>
  seenIds: ReadonlySet<string>
  /** Each anonymous path's latest state (F3), by track ID, in the order the paths began. */
  tracks: Record<string, Track>
}

export type LiveAction =
  | { type: 'reset' }
  | { type: 'message'; message: SseMessage; receivedAt: number }

export const emptyLiveRun: LiveRun = {
  events: [],
  inView: {},
  lastSeen: {},
  seenIds: new Set(),
  tracks: {},
}

/** Applies one stream message. Messages may repeat after a reconnect; repeats change nothing. */
export function liveRunReducer(state: LiveRun, action: LiveAction): LiveRun {
  if (action.type === 'reset') return emptyLiveRun
  const { message, receivedAt } = action
  if (message.event === 'track_update') return updateTrack(state, JSON.parse(message.data) as Track)
  if (message.event !== 'event') return state
  const event = JSON.parse(message.data) as RunEvent
  if (state.seenIds.has(event.id)) return state

  const here = state.inView[event.node_id] ?? []
  const others = here.filter((id) => id !== event.local_track_id)
  const inView = {
    ...state.inView,
    [event.node_id]: event.type === 'disappear' ? others : [...others, event.local_track_id],
  }
  return {
    ...state,
    events: [...state.events, event].slice(-MAX_EVENTS),
    inView,
    lastSeen: { ...state.lastSeen, [event.node_id]: receivedAt },
    seenIds: new Set(state.seenIds).add(event.id),
  }
}

/** A `track_update` carries the whole track: keep the latest, and drop it once it expires (D-11). */
function updateTrack(state: LiveRun, track: Track): LiveRun {
  const tracks =
    track.status === 'expired'
      ? Object.fromEntries(Object.entries(state.tracks).filter(([id]) => id !== track.id))
      : { ...state.tracks, [track.id]: track }
  return { ...state, tracks }
}

/** Nodes with an object in view, and nodes whose latest event is recent enough to flash. */
export function mapHighlights(state: LiveRun, now: number) {
  const occupied = new Set(
    Object.entries(state.inView)
      .filter(([, ids]) => ids.length > 0)
      .map(([nodeId]) => nodeId),
  )
  const flashing = new Set(
    Object.entries(state.lastSeen)
      .filter(([, at]) => now - at < FLASH_MS)
      .map(([nodeId]) => nodeId),
  )
  return { occupied, flashing }
}

/** Each anonymous path as a line on the map, through its nodes in order, labelled with its ID. */
export function mapPaths(state: LiveRun) {
  return Object.values(state.tracks).map((track) => ({
    id: track.id,
    label: track.anon_id,
    nodeIds: track.segments.map((segment) => segment.node_id),
    active: track.status === 'active',
  }))
}

import { describe, expect, it } from 'vitest'
import type { SseMessage } from '../api/sse'
import type { RunEvent, Track } from '../api/types'
import {
  emptyLiveRun,
  FLASH_MS,
  type LiveRun,
  liveRunReducer,
  mapHighlights,
  mapPaths,
} from './liveRun'

let seq = 0

function event(nodeId: string, type: RunEvent['type'], localTrackId: string): SseMessage {
  seq += 1
  const data: RunEvent = {
    id: `e${seq}`,
    run_id: 'r1',
    seq,
    ts: `2026-10-21T18:10:${String(seq).padStart(2, '0')}.000Z`,
    node_id: nodeId,
    type,
    object_class: 'person',
    local_track_id: localTrackId,
    attrs: {},
    source: 'sim',
  }
  return { id: String(seq), event: 'event', data: JSON.stringify(data) }
}

function track(id: string, nodeIds: string[], status: Track['status'] = 'active'): SseMessage {
  seq += 1
  const data: Track = {
    id,
    run_id: 'r1',
    anon_id: `obj-${id}`,
    object_class: 'person',
    status,
    first_ts: '2026-10-21T18:10:00.000Z',
    last_ts: '2026-10-21T18:12:00.000Z',
    expires_at: '2026-10-22T18:12:00.000Z',
    segments: nodeIds.map((nodeId, index) => ({
      node_id: nodeId,
      enter_ts: `2026-10-21T18:1${index}:00.000Z`,
      exit_ts: null,
      event_ids: [],
    })),
  }
  return { id: String(seq), event: 'track_update', data: JSON.stringify(data) }
}

function play(messages: SseMessage[], receivedAt = 1000): LiveRun {
  return messages.reduce(
    (state, message) => liveRunReducer(state, { type: 'message', message, receivedAt }),
    emptyLiveRun,
  )
}

describe('liveRunReducer', () => {
  it('keeps the feed in order and tracks what each camera has in view', () => {
    const state = play([
      event('fence', 'appear', 'fence#1'),
      event('back', 'appear', 'back#1'),
      event('fence', 'disappear', 'fence#1'),
      event('back', 'dwell', 'back#1'),
    ])
    expect(state.events.map((item) => item.seq)).toEqual([1, 2, 3, 4].map((n) => n + seq - 4))
    expect(state.inView).toEqual({ fence: [], back: ['back#1'] })
  })

  it('ignores a message it has already applied, as a reconnect may resend it', () => {
    const message = event('fence', 'appear', 'fence#2')
    const once = play([message])
    expect(liveRunReducer(once, { type: 'message', message, receivedAt: 2000 })).toBe(once)
  })

  it('ignores message types it does not know yet and clears on reset', () => {
    const state = play([event('fence', 'appear', 'fence#3')])
    const other: SseMessage = { id: '9', event: 'alert', data: '{}' }
    expect(liveRunReducer(state, { type: 'message', message: other, receivedAt: 0 })).toBe(state)
    expect(liveRunReducer(state, { type: 'reset' })).toBe(emptyLiveRun)
  })

  it('keeps the latest state of each path and drops a path once it expires', () => {
    const state = play([
      track('a1', ['fence']),
      event('fence', 'appear', 'fence#4'),
      track('b2', ['gate']),
      track('a1', ['fence', 'back']),
    ])
    expect(Object.keys(state.tracks)).toEqual(['a1', 'b2'])
    expect(state.tracks.a1.segments.map((segment) => segment.node_id)).toEqual(['fence', 'back'])
    expect(state.events).toHaveLength(1)

    const message = track('a1', ['fence', 'back'], 'expired')
    const expired = liveRunReducer(state, { type: 'message', message, receivedAt: 2000 })
    expect(Object.keys(expired.tracks)).toEqual(['b2'])
    expect(expired.events).toBe(state.events)
  })
})

describe('mapHighlights', () => {
  it('lights occupied cameras and flashes recent ones', () => {
    const state = play([event('fence', 'appear', 'f#1'), event('back', 'appear', 'b#1')], 1000)
    const left = liveRunReducer(state, {
      type: 'message',
      message: event('back', 'disappear', 'b#1'),
      receivedAt: 1000,
    })
    const soon = mapHighlights(left, 1000 + FLASH_MS - 1)
    expect([...soon.occupied]).toEqual(['fence'])
    expect([...soon.flashing].sort()).toEqual(['back', 'fence'])
    expect(mapHighlights(left, 1000 + FLASH_MS).flashing.size).toBe(0)
  })
})

describe('mapPaths', () => {
  it('draws each path through its nodes in order, labelled with its anonymous ID', () => {
    const state = play([track('a1', ['fence', 'back']), track('b2', ['gate'], 'closed')])
    expect(mapPaths(state)).toEqual([
      { id: 'a1', label: 'obj-a1', nodeIds: ['fence', 'back'], active: true },
      { id: 'b2', label: 'obj-b2', nodeIds: ['gate'], active: false },
    ])
  })
})

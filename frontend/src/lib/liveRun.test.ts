import { describe, expect, it } from 'vitest'
import type { SseMessage } from '../api/sse'
import type { RunEvent } from '../api/types'
import { emptyLiveRun, FLASH_MS, type LiveRun, liveRunReducer, mapHighlights } from './liveRun'

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

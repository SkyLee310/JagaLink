import { describe, expect, it } from 'vitest'
import { parseSse } from './sse'

describe('parseSse', () => {
  it('reads whole messages and keeps the unfinished tail', () => {
    const { messages, rest } = parseSse(
      'id: 1\nevent: event\ndata: {"seq":1}\n\nid: 2\nevent: alert\ndata: {"id"',
    )
    expect(messages).toEqual([{ id: '1', event: 'event', data: '{"seq":1}' }])
    expect(rest).toBe('id: 2\nevent: alert\ndata: {"id"')

    const next = parseSse(`${rest}:"a1"}\n\n`)
    expect(next.messages).toEqual([{ id: '2', event: 'alert', data: '{"id":"a1"}' }])
    expect(next.rest).toBe('')
  })

  it('skips keep-alive comments and joins multi-line data', () => {
    const { messages } = parseSse(': ping\n\ndata: first\ndata: second\n\n')
    expect(messages).toEqual([{ id: null, event: 'message', data: 'first\nsecond' }])
  })

  it('accepts CRLF line breaks', () => {
    const { messages } = parseSse('event: event\r\ndata: x\r\n\r\n')
    expect(messages).toEqual([{ id: null, event: 'event', data: 'x' }])
  })
})

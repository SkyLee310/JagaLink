import { useEffect, useEffectEvent, useState } from 'react'
import { useSession } from '../lib/session'
import { API_URL } from './client'

/** One Server-Sent Events message: `event` is its type, `data` its (JSON) text. */
export interface SseMessage {
  id: string | null
  event: string
  data: string
}

/**
 * Splits SSE text into whole messages, returning the unfinished tail to prepend to the next
 * chunk. Comment lines (`: ping`) are skipped.
 */
export function parseSse(text: string): { messages: SseMessage[]; rest: string } {
  const blocks = text.replace(/\r\n?/g, '\n').split('\n\n')
  const rest = blocks.pop() ?? ''
  const messages: SseMessage[] = []
  for (const block of blocks) {
    let id: string | null = null
    let event = 'message'
    const data: string[] = []
    for (const line of block.split('\n')) {
      if (!line || line.startsWith(':')) continue
      const colon = line.indexOf(':')
      const field = colon === -1 ? line : line.slice(0, colon)
      const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '')
      if (field === 'data') data.push(value)
      else if (field === 'event') event = value
      else if (field === 'id') id = value
    }
    if (data.length > 0) messages.push({ id, event, data: data.join('\n') })
  }
  return { messages, rest }
}

class StreamClosed extends Error {
  readonly status: number

  constructor(status: number) {
    super(`The stream answered ${status}`)
    this.status = status
  }
}

/** Reads one connection until the server ends it; throws when it cannot connect. */
async function readStream(
  url: string,
  token: string,
  signal: AbortSignal,
  onOpen: () => void,
  onMessage: (message: SseMessage) => void,
): Promise<void> {
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' },
    cache: 'no-store',
    signal,
  })
  if (!response.ok || !response.body) throw new StreamClosed(response.status)
  onOpen()
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    const parsed = parseSse(buffer + value)
    buffer = parsed.rest
    parsed.messages.forEach(onMessage)
  }
}

export type StreamStatus = 'idle' | 'connecting' | 'open' | 'retrying'

const FIRST_RETRY_MS = 500
const LAST_RETRY_MS = 10_000

/**
 * Follows `GET /stream?run_id=` (D-36) with the session's bearer token, which EventSource cannot
 * send. Every (re)connection replays the run from the start, so `onOpen` must clear what the
 * page built from earlier messages. Reconnects with backoff; a 401 ends the session.
 */
export function useRunStream(
  runId: string | null,
  onOpen: () => void,
  onMessage: (message: SseMessage) => void,
): StreamStatus {
  const token = useSession((state) => state.session?.token)
  const [status, setStatus] = useState<StreamStatus>('idle')
  const opened = useEffectEvent(onOpen)
  const received = useEffectEvent(onMessage)

  useEffect(() => {
    if (!runId || !token) return
    const controller = new AbortController()
    const url = `${API_URL}/api/v1/stream?run_id=${encodeURIComponent(runId)}`
    let delay = FIRST_RETRY_MS

    const loop = async () => {
      while (!controller.signal.aborted) {
        setStatus('connecting')
        try {
          await readStream(
            url,
            token,
            controller.signal,
            () => {
              delay = FIRST_RETRY_MS
              setStatus('open')
              opened()
            },
            received,
          )
        } catch (error) {
          if (controller.signal.aborted) return
          if (error instanceof StreamClosed && error.status === 401) {
            useSession.getState().signOut()
            return
          }
        }
        if (controller.signal.aborted) return
        setStatus('retrying')
        await new Promise((resolve) => setTimeout(resolve, delay))
        delay = Math.min(delay * 2, LAST_RETRY_MS)
      }
    }
    void loop()
    return () => {
      controller.abort()
      setStatus('idle')
    }
  }, [runId, token])

  return runId && token ? status : 'idle'
}

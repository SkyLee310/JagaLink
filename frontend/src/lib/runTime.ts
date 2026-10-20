import { useEffect, useState } from 'react'
import type { Run } from '../../api/types'

/** Date.now(), refreshed every `intervalMs` while `active`. */
export function useNow(intervalMs: number, active = true): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const timer = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs, active])
  return now
}

/**
 * The run's simulated time now: the server's clock when it was fetched, moved on at the run's
 * speed while it plays, so the display ticks between polls.
 */
export function runClock(run: Run, fetchedAt: number, now: number): number {
  const at = Date.parse(run.clock)
  if (run.state !== 'playing') return at
  return Math.min(at + Math.max(now - fetchedAt, 0) * run.speed, Date.parse(run.window_end))
}

/** Share of the live window played, from 0 to 1. */
export function runProgress(run: Run, clock: number): number {
  const start = Date.parse(run.window_start)
  const span = Date.parse(run.window_end) - start
  return span > 0 ? Math.min(Math.max((clock - start) / span, 0), 1) : 0
}

const formatters = new Map<string, Intl.DateTimeFormat>()

/** A moment as the community's local clock time, e.g. 19:23:41 (D-54). */
export function localTime(moment: number | string, timeZone: string): string {
  let formatter = formatters.get(timeZone)
  if (!formatter) {
    formatter = new Intl.DateTimeFormat('en-GB', {
      timeZone,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
    })
    formatters.set(timeZone, formatter)
  }
  return formatter.format(typeof moment === 'string' ? Date.parse(moment) : moment)
}

import { useEffect, useRef } from 'react'
import type { Alert } from '../../api/types'
import { playCue } from '../../lib/cue'
import { isOpen } from '../../lib/liveRun'

/** Alerts arriving this close together (a burst, or the replay on connect) share one chime. */
export const CUE_SETTLE_MS = 150

/**
 * Chimes when an open alert the page has not chimed for arrives (F6). A reconnect replays the
 * run's alerts; those were chimed for already and stay quiet.
 */
export function useAlertCue(alerts: Record<string, Alert>): void {
  const chimed = useRef(new Set<string>())
  const pending = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const fresh = Object.values(alerts).filter(
      (alert) => isOpen(alert) && !chimed.current.has(alert.id),
    )
    if (fresh.length === 0) return
    fresh.forEach((alert) => chimed.current.add(alert.id))
    pending.current ??= setTimeout(() => {
      pending.current = null
      playCue()
    }, CUE_SETTLE_MS)
  }, [alerts])

  useEffect(
    () => () => {
      if (pending.current !== null) clearTimeout(pending.current)
    },
    [],
  )
}

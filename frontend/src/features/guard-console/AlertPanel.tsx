import type { StreamStatus } from '../../api/sse'
import type { Alert, LayoutNode } from '../../api/types'
import { StreamBadge } from '../../components/StreamBadge'
import { isOpen } from '../../lib/liveRun'
import { AlertCard } from './AlertCard'

/** How long a new alert's card stands out, in wall milliseconds. */
export const FRESH_MS = 6000

interface AlertPanelProps {
  /** In display order: open and most severe first. */
  alerts: Alert[]
  alertSeen: Record<string, number>
  now: number
  nodes: ReadonlyMap<string, LayoutNode>
  timeZone: string
  viewerId: string
  status: StreamStatus
  running: boolean
  onChange: (alert: Alert) => void
}

/** The run's alerts as cards; five fit without scrolling on a 1366×768 screen (D-67). */
export function AlertPanel({
  alerts,
  alertSeen,
  now,
  nodes,
  timeZone,
  viewerId,
  status,
  running,
  onChange,
}: AlertPanelProps) {
  const open = alerts.filter(isOpen).length
  return (
    <section
      aria-label="Alerts"
      className="flex min-h-48 flex-col rounded-lg border border-slate-800 lg:min-h-0 lg:flex-1"
    >
      <header className="flex items-center gap-2 border-b border-slate-800 px-3 py-2">
        <h2 className="text-sm font-medium">Alerts</h2>
        <span className="mr-auto text-xs text-slate-400">{open} open</span>
        <StreamBadge status={status} />
      </header>
      {alerts.length === 0 ? (
        <p className="m-auto p-6 text-center text-sm text-slate-500">
          {running
            ? 'No alerts yet. A new alert shows here with a chime.'
            : 'No scenario is running. Alerts show here once one plays.'}
        </p>
      ) : (
        <ol className="flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto p-1.5">
          {alerts.map((alert) => (
            <li key={alert.id}>
              <AlertCard
                alert={alert}
                nodes={nodes}
                timeZone={timeZone}
                viewerId={viewerId}
                fresh={isOpen(alert) && now - (alertSeen[alert.id] ?? 0) < FRESH_MS}
                onChange={onChange}
              />
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

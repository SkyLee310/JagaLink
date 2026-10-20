import { memo, useMemo } from 'react'
import type { StreamStatus } from '../../api/sse'
import type { LayoutNode, RunEvent } from '../../api/types'
import { StreamBadge } from '../../components/StreamBadge'
import { localTime } from '../../lib/runTime'

const TYPE_STYLES: Record<RunEvent['type'], string> = {
  appear: 'bg-emerald-500/15 text-emerald-300',
  dwell: 'bg-amber-500/15 text-amber-300',
  disappear: 'bg-slate-500/20 text-slate-300',
}

interface EventFeedProps {
  events: RunEvent[]
  nodes: Map<string, LayoutNode>
  timeZone: string
  status: StreamStatus
}

/** The live event feed, newest first: time, camera, event type, object class, per-camera ID. */
export const EventFeed = memo(function EventFeed({
  events,
  nodes,
  timeZone,
  status,
}: EventFeedProps) {
  const newestFirst = useMemo(() => [...events].reverse(), [events])
  return (
    <section
      aria-label="Live events"
      className="flex min-h-0 flex-1 flex-col rounded-lg border border-slate-800"
    >
      <header className="flex items-center gap-2 border-b border-slate-800 px-3 py-2">
        <h2 className="text-sm font-medium">Live events</h2>
        <span className="mr-auto text-xs text-slate-500">{events.length}</span>
        <StreamBadge status={status} />
      </header>
      {newestFirst.length === 0 ? (
        <p className="m-auto p-4 text-center text-sm text-slate-500">
          Events appear here as the scenario plays.
        </p>
      ) : (
        <ol className="min-h-0 flex-1 divide-y divide-slate-800/70 overflow-y-auto text-sm">
          {newestFirst.map((event) => {
            const node = nodes.get(event.node_id)
            return (
              <li key={event.id} className="flex items-center gap-2 px-3 py-1.5">
                <time dateTime={event.ts} className="font-mono text-xs text-slate-400 tabular-nums">
                  {localTime(event.ts, timeZone)}
                </time>
                <span className="w-20 truncate font-mono text-xs" title={node?.name}>
                  {node?.code ?? 'unknown'}
                </span>
                <span className={`rounded px-1.5 py-0.5 text-xs ${TYPE_STYLES[event.type]}`}>
                  {event.type}
                </span>
                <span className="text-xs text-slate-400">{event.object_class}</span>
                <span
                  className="ml-auto truncate font-mono text-xs text-slate-500"
                  title={event.local_track_id}
                >
                  {event.local_track_id}
                </span>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
})

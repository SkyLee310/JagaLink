import type { StreamStatus } from '../api/sse'

const STATUS_TEXT: Record<StreamStatus, string> = {
  idle: 'No run',
  connecting: 'Connecting…',
  open: 'Live',
  retrying: 'Reconnecting…',
}

/** Whether the page is following the run's stream right now (D-36). */
export function StreamBadge({ status }: { status: StreamStatus }) {
  const live = status === 'open'
  return (
    <span
      className={`flex shrink-0 items-center gap-1.5 text-xs ${live ? 'text-emerald-300' : 'text-slate-400'}`}
    >
      <span className={`size-2 rounded-full ${live ? 'bg-emerald-400' : 'bg-slate-500'}`} />
      {STATUS_TEXT[status]}
    </span>
  )
}

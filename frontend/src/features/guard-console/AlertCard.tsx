import { memo, useState } from 'react'
import { ApiError } from '../../api/client'
import { useAlertAction } from '../../api/queries'
import type { Alert, AlertActionInput, LayoutNode } from '../../api/types'
import { isOpen } from '../../lib/liveRun'
import { localTime } from '../../lib/runTime'

const SEVERITY_STYLES: Record<Alert['severity'], { badge: string; edge: string }> = {
  high: { badge: 'border-red-400/70 bg-red-500/20 text-red-100', edge: 'border-l-red-500' },
  medium: {
    badge: 'border-orange-400/70 bg-orange-500/20 text-orange-100',
    edge: 'border-l-orange-500',
  },
  low: { badge: 'border-yellow-400/60 bg-yellow-500/15 text-yellow-100', edge: 'border-l-yellow-500' },
}

const STATUS: Record<Alert['status'], { text: string; style: string }> = {
  new: { text: 'New', style: 'bg-sky-500/20 text-sky-200' },
  escalated: { text: 'Escalated', style: 'bg-fuchsia-500/20 text-fuchsia-200' },
  acked: { text: 'Confirmed', style: 'bg-emerald-500/20 text-emerald-200' },
  dismissed: { text: 'Dismissed', style: 'bg-slate-500/25 text-slate-300' },
}

const DONE_TEXT: Record<AlertActionInput['action'], string> = {
  confirm: 'Confirmed',
  dismiss: 'Dismissed',
}

interface AlertCardProps {
  alert: Alert
  nodes: ReadonlyMap<string, LayoutNode>
  timeZone: string
  /** The signed-in user, so the card can say "you". */
  viewerId: string
  /** Arrived moments ago: the card stands out. */
  fresh: boolean
  /** The alert as stored after an action on this screen. */
  onChange: (alert: Alert) => void
}

/**
 * One alert (F6): severity, rule and place, why it was raised, the camera to check next with its
 * basis (F5) and who it went to; an open alert takes one click to confirm or dismiss.
 */
export const AlertCard = memo(function AlertCard({
  alert,
  nodes,
  timeZone,
  viewerId,
  fresh,
  onChange,
}: AlertCardProps) {
  const node = nodes.get(alert.node_id)
  const where = node?.code ?? 'an unknown node'
  const open = isOpen(alert)
  return (
    <article
      aria-label={`${alert.severity} alert: ${alert.rule_name} at ${where}`}
      className={`flex flex-col gap-0.5 rounded-md border border-l-4 border-slate-800 bg-slate-900 px-2.5 py-1.5 ${
        open ? SEVERITY_STYLES[alert.severity].edge : 'border-l-slate-600 opacity-80'
      } ${fresh ? 'ring-2 ring-sky-300/80' : ''}`}
    >
      <div className="flex items-center gap-2 text-sm leading-5">
        <SeverityBadge alert={alert} />
        <span className="truncate font-medium">{alert.rule_name}</span>
        <span className="shrink-0 font-mono text-xs text-slate-300" title={node?.name}>
          {where}
        </span>
        <time
          dateTime={alert.created_ts}
          className="ml-auto shrink-0 font-mono text-xs text-slate-400 tabular-nums"
        >
          {localTime(alert.created_ts, timeZone)}
        </time>
        <span className={`shrink-0 rounded px-1.5 text-xs ${STATUS[alert.status].style}`}>
          {STATUS[alert.status].text}
        </span>
      </div>
      <p className="truncate text-xs leading-4 text-slate-300" title={alert.detail}>
        {alert.detail}
      </p>
      {open ? (
        <>
          <div className="flex items-center gap-3 text-xs leading-4 text-slate-400">
            <NextCamera alert={alert} nodes={nodes} from={where} />
            <Assignee alert={alert} viewerId={viewerId} />
          </div>
          <AlertActions alertId={alert.id} onChange={onChange} />
        </>
      ) : (
        <Outcome alert={alert} timeZone={timeZone} viewerId={viewerId} />
      )}
    </article>
  )
})

/** Severity stays dashed while it is rule-based and provisional, until triage (D-61). */
function SeverityBadge({ alert }: { alert: Alert }) {
  const provisional = alert.triage_status === 'pending'
  return (
    <span
      title={provisional ? `${alert.severity_reason} Provisional.` : alert.severity_reason}
      className={`shrink-0 rounded border px-1.5 text-[11px] font-semibold tracking-wide uppercase ${
        SEVERITY_STYLES[alert.severity].badge
      } ${provisional ? 'border-dashed' : ''}`}
    >
      {alert.severity}
    </span>
  )
}

function NextCamera({
  alert,
  nodes,
  from,
}: {
  alert: Alert
  nodes: ReadonlyMap<string, LayoutNode>
  from: string
}) {
  if (!alert.next_node) return <span className="shrink-0">No camera links onward</span>
  const { basis } = alert.next_node
  const code = nodes.get(alert.next_node.id)?.code ?? 'unknown'
  const distance = basis.distance_m === null ? null : `${Math.round(basis.distance_m)} m`
  const walk = `${Math.round(basis.walk_s)} s`
  const share = `${Math.round(basis.transition_share * 100)} %`
  const why = [
    `Most likely next camera: ${code}`,
    `${distance ? `${distance}, ` : ''}about ${walk} on foot from ${from}`,
    `${share} of normal routes from ${from} go there`,
    basis.backtrack ? 'back the way it came' : basis.direction > 0 ? 'ahead of the movement' : null,
  ]
  return (
    <span className="shrink-0" title={why.filter(Boolean).join('; ')}>
      Next <span className="font-mono font-medium text-slate-100">{code}</span> ·{' '}
      {[distance, walk, `${share} of routes`].filter(Boolean).join(' · ')}
    </span>
  )
}

function Assignee({ alert, viewerId }: { alert: Alert; viewerId: string }) {
  const user = alert.assigned_user
  if (!user) return <span className="ml-auto truncate">Nobody assigned</span>
  const name = user.id === viewerId ? `${user.name} (you)` : user.name
  if (alert.status === 'escalated') {
    return (
      <span className="ml-auto truncate text-fuchsia-200" title="No guard on duty can take it">
        Escalated to {name}
      </span>
    )
  }
  const walk = alert.walk_s === null ? '' : ` · ${Math.round(alert.walk_s)} s away`
  return (
    <span className="ml-auto truncate" title="The on-duty guard with the shortest walk">
      → {name}
      {walk}
    </span>
  )
}

/** A one-line reason, then one click: the answer updates this card at once (F6). */
function AlertActions({ alertId, onChange }: { alertId: string; onChange: (alert: Alert) => void }) {
  const [reason, setReason] = useState('')
  const act = useAlertAction()
  const send = (action: AlertActionInput['action']) =>
    act.mutate({ alertId, action, reason: reason.trim() }, { onSuccess: onChange })
  const button = 'h-8 shrink-0 rounded px-2.5 text-xs font-medium disabled:opacity-50 lg:h-6'
  return (
    <>
      <div className="flex gap-1.5">
        <input
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={200}
          aria-label="Reason"
          placeholder="Reason (optional, one line)"
          className="h-8 min-w-0 flex-1 rounded border border-slate-700 bg-slate-950 px-2 text-xs placeholder:text-slate-500 focus:border-sky-500 focus:outline-none lg:h-6"
        />
        <button
          type="button"
          disabled={act.isPending}
          onClick={() => send('confirm')}
          className={`${button} bg-emerald-600 text-white hover:bg-emerald-500`}
        >
          Confirm
        </button>
        <button
          type="button"
          disabled={act.isPending}
          onClick={() => send('dismiss')}
          className={`${button} border border-slate-600 hover:border-slate-400`}
        >
          Dismiss
        </button>
      </div>
      {act.error && (
        <p role="alert" className="text-xs text-red-300">
          {act.error instanceof ApiError && act.error.code === 'alert_already_handled'
            ? 'Someone has already handled this alert.'
            : act.error.message}
        </p>
      )}
    </>
  )
}

/** Who handled the alert, when, and why. */
function Outcome({ alert, timeZone, viewerId }: { alert: Alert; timeZone: string; viewerId: string }) {
  const last = alert.actions.at(-1)
  if (!last) return null
  const who = last.user.id === viewerId ? `${last.user.name} (you)` : last.user.name
  return (
    <p className="truncate text-xs leading-4 text-slate-400" title={last.reason || undefined}>
      {DONE_TEXT[last.action]} by {who} at {localTime(last.ts, timeZone)}
      {last.reason && ` — “${last.reason}”`}
    </p>
  )
}

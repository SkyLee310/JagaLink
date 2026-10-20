import type { Alert } from '../api/types'

export const GUARD_C = { id: 'u3', code: 'u-guard-03', name: 'Guard C', role: 'guard' } as const
export const SUPERVISOR_REF = {
  id: 'u0',
  code: 'u-sup-01',
  name: 'Supervisor',
  role: 'supervisor',
} as const

/** An open after-hours alert at camera a, assigned to Guard C, pointing on to camera b. */
export function testAlert(id: string, overrides: Partial<Alert> = {}): Alert {
  return {
    id,
    run_id: 'r1',
    version: 1,
    status: 'new',
    rule: 'after_hours',
    rule_name: 'After-hours entry',
    detail: 'Appeared at c-a, in a lane zone, at 02:10: inside quiet hours 23:00–06:00.',
    score: null,
    track_id: 't1',
    track_anon_id: 'obj-t1',
    node_id: 'a',
    severity: 'medium',
    severity_reason: 'Rule-based: the after-hours entry rule.',
    triage_status: 'pending',
    assigned_user: GUARD_C,
    walk_s: 115.5,
    next_node: {
      id: 'b',
      basis: {
        walk_s: 15.5,
        distance_m: 30,
        transition_share: 0.4,
        direction: 0.9,
        backtrack: false,
        score: 2.1,
      },
    },
    evidence_event_ids: ['e1'],
    created_ts: '2026-10-21T18:10:00.000Z',
    updated_ts: '2026-10-21T18:10:00.000Z',
    acked_ts: null,
    actions: [],
    ...overrides,
  }
}

/** The alert after someone confirmed or dismissed it. */
export function handled(
  alert: Alert,
  action: 'confirm' | 'dismiss',
  user: Alert['actions'][number]['user'],
  reason = '',
): Alert {
  const ts = '2026-10-21T18:18:00.000Z'
  return {
    ...alert,
    version: alert.version + 1,
    status: action === 'confirm' ? 'acked' : 'dismissed',
    acked_ts: ts,
    updated_ts: ts,
    actions: [{ id: `act-${alert.id}`, action, reason, ts, user }],
  }
}

/** One stream message carrying an alert. */
export function alertFrame(kind: 'alert' | 'alert_update', alert: Alert): string {
  return `event: ${kind}\ndata: ${JSON.stringify(alert)}\n\n`
}

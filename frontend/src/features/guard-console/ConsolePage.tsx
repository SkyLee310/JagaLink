import { useCallback, useEffect, useMemo, useReducer } from 'react'
import { Navigate } from 'react-router'
import { useCurrentRun, useLayout } from '../../api/queries'
import { useRunStream } from '../../api/sse'
import type { Alert, Layout, Run, Session } from '../../api/types'
import { AppHeader } from '../../components/AppHeader'
import { CommunityMap } from '../../components/map/CommunityMap'
import {
  emptyLiveRun,
  liveRunReducer,
  mapAlerts,
  mapHighlights,
  mapPaths,
  sortedAlerts,
} from '../../lib/liveRun'
import { localTime, RUN_STATE_TEXT, runClock, useNow } from '../../lib/runTime'
import { useSession } from '../../lib/session'
import { AlertPanel } from './AlertPanel'
import { useAlertCue } from './useAlertCue'

/**
 * The console both roles land on (D-66, F6): the current run's alerts as cards beside the map,
 * which rings each open alert and points to the camera to check next.
 */
export function ConsolePage() {
  const session = useSession((state) => state.session)
  if (!session) return <Navigate to="/" replace />
  return <Console session={session} />
}

function Console({ session }: { session: Session }) {
  const layout = useLayout(session.community_id)
  const run = useCurrentRun()
  const failed = layout.error ?? run.error

  return (
    // Phones scroll the page; from lg the map and the alerts share one screen (D-67).
    <div className="flex min-h-dvh flex-col lg:h-dvh">
      <AppHeader session={session} communityName={layout.data?.community.name} />
      {layout.data && run.data !== undefined ? (
        // A new run starts with no alerts.
        <LiveConsole
          key={run.data?.id ?? 'none'}
          session={session}
          layout={layout.data}
          run={run.data}
          fetchedAt={run.dataUpdatedAt}
        />
      ) : (
        <main className="flex flex-1 p-4">
          {failed ? (
            <div
              role="alert"
              className="m-auto max-w-sm rounded-lg border border-red-500/40 bg-red-500/10 p-4"
            >
              <p className="font-medium text-red-200">Cannot load the console.</p>
              <p className="mt-1 text-sm text-red-200/80">{failed.message}</p>
              <button
                type="button"
                onClick={() => {
                  void layout.refetch()
                  void run.refetch()
                }}
                disabled={layout.isFetching || run.isFetching}
                className="mt-3 rounded-md bg-red-500/20 px-3 py-1.5 text-sm font-medium text-red-100 hover:bg-red-500/30 disabled:opacity-50"
              >
                Retry
              </button>
            </div>
          ) : (
            <p className="m-auto text-sm text-slate-400">Loading the console…</p>
          )}
        </main>
      )}
    </div>
  )
}

interface LiveConsoleProps {
  session: Session
  layout: Layout
  run: Run | null
  fetchedAt: number
}

function LiveConsole({ session, layout, run, fetchedAt }: LiveConsoleProps) {
  const [live, dispatch] = useReducer(liveRunReducer, emptyLiveRun)
  const status = useRunStream(
    run?.id ?? null,
    () => dispatch({ type: 'reset' }),
    (message) => dispatch({ type: 'message', message, receivedAt: Date.now() }),
  )
  const now = useNow(250)
  const nodes = useMemo(() => new Map(layout.nodes.map((node) => [node.id, node])), [layout])
  const alerts = useMemo(() => sortedAlerts(live.alerts), [live.alerts])
  const marks = useMemo(() => mapAlerts(alerts), [alerts])
  const paths = useMemo(() => mapPaths(live), [live])
  const onChange = useCallback(
    (alert: Alert) => dispatch({ type: 'alert', alert, receivedAt: Date.now() }),
    [],
  )
  useAlertCue(live.alerts)
  useOpenCountInTitle(marks.length)
  const timeZone = layout.community.timezone

  return (
    <main className="flex flex-1 flex-col gap-3 p-2 sm:p-3 lg:min-h-0 lg:flex-row">
      <section aria-label="Map" className="flex flex-col gap-2 lg:min-h-0 lg:flex-1">
        <RunLine run={run} fetchedAt={fetchedAt} now={now} timeZone={timeZone} />
        <div className="h-72 sm:h-96 lg:h-auto lg:min-h-0 lg:flex-1">
          <CommunityMap
            layout={layout}
            highlights={mapHighlights(live, now)}
            paths={paths}
            alerts={marks}
          />
        </div>
        <ConsoleLegend />
      </section>
      <aside className="order-first flex flex-col lg:order-none lg:min-h-0 lg:w-[30rem] xl:w-[32rem]">
        <AlertPanel
          alerts={alerts}
          alertSeen={live.alertSeen}
          now={now}
          nodes={nodes}
          timeZone={timeZone}
          viewerId={session.user.id}
          status={status}
          running={run !== null}
          onChange={onChange}
        />
      </aside>
    </main>
  )
}

/** Shows the open alert count in the tab title, for a console left behind other windows. */
function useOpenCountInTitle(open: number) {
  useEffect(() => {
    const title = document.title
    if (open > 0) document.title = `(${open}) ${title}`
    return () => {
      document.title = title
    }
  }, [open])
}

function RunLine({
  run,
  fetchedAt,
  now,
  timeZone,
}: {
  run: Run | null
  fetchedAt: number
  now: number
  timeZone: string
}) {
  if (!run) return <p className="text-sm text-slate-400">No scenario is running.</p>
  return (
    <p className="flex items-baseline gap-2 text-sm">
      <span className="truncate font-medium">{run.scenario_name}</span>
      <time className="shrink-0 font-mono text-slate-300 tabular-nums">
        {localTime(runClock(run, fetchedAt, now), timeZone)}
      </time>
      <span className="shrink-0 text-slate-400">{RUN_STATE_TEXT[run.state]}</span>
    </p>
  )
}

function ConsoleLegend() {
  return (
    <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-full border-2 border-red-500" /> open alert, in its
        severity colour
      </span>
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-full border-2 border-dashed border-slate-50" /> camera to
        check next
      </span>
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-full border-2 border-emerald-400" /> object in view
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-0.5 w-4 rounded-full bg-fuchsia-400" /> anonymous path
      </span>
    </p>
  )
}

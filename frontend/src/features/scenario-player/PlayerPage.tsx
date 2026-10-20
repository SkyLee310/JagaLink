import { useMemo, useReducer } from 'react'
import { Navigate } from 'react-router'
import { useCurrentRun, useLayout, useScenarios } from '../../api/queries'
import { useRunStream } from '../../api/sse'
import type { Layout, Run, Scenario, Session } from '../../api/types'
import { AppHeader } from '../../components/AppHeader'
import { CommunityMap } from '../../components/map/CommunityMap'
import { emptyLiveRun, liveRunReducer, mapHighlights, mapPaths } from '../../lib/liveRun'
import { useSession } from '../../lib/session'
import { EventFeed } from './EventFeed'
import { RunControls } from './RunControls'
import { useNow } from '../../lib/runTime'

/**
 * The supervisor's scenario player (F2, D-66): play, pause, reset; events light up cameras and
 * linked sightings grow into anonymous paths (F3).
 */
export function PlayerPage() {
  const session = useSession((state) => state.session)
  if (!session) return <Navigate to="/" replace />
  if (session.user.role !== 'supervisor') return <Navigate to="/console" replace />
  return <PlayerScreen session={session} />
}

function PlayerScreen({ session }: { session: Session }) {
  const layout = useLayout(session.community_id)
  const scenarios = useScenarios()
  const run = useCurrentRun()
  const failed = layout.error ?? scenarios.error ?? run.error

  return (
    // Phones scroll the page; from lg the map and feed share one screen.
    <div className="flex min-h-dvh flex-col lg:h-dvh">
      <AppHeader session={session} communityName={layout.data?.community.name} />
      {layout.data && scenarios.data && run.data !== undefined ? (
        // A new run starts with an empty feed and map.
        <LivePlayer
          key={run.data?.id ?? 'none'}
          layout={layout.data}
          scenarios={scenarios.data}
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
              <p className="font-medium text-red-200">Cannot load the scenario player.</p>
              <p className="mt-1 text-sm text-red-200/80">{failed.message}</p>
            </div>
          ) : (
            <p className="m-auto text-sm text-slate-400">Loading the scenarios…</p>
          )}
        </main>
      )}
    </div>
  )
}

interface LivePlayerProps {
  layout: Layout
  scenarios: Scenario[]
  run: Run | null
  fetchedAt: number
}

function LivePlayer({ layout, scenarios, run, fetchedAt }: LivePlayerProps) {
  const [live, dispatch] = useReducer(liveRunReducer, emptyLiveRun)
  const status = useRunStream(
    run?.id ?? null,
    () => dispatch({ type: 'reset' }),
    (message) => dispatch({ type: 'message', message, receivedAt: Date.now() }),
  )
  const now = useNow(250)
  const nodes = useMemo(() => new Map(layout.nodes.map((node) => [node.id, node])), [layout])
  const paths = useMemo(() => mapPaths(live), [live])
  const timeZone = layout.community.timezone

  return (
    <main className="flex flex-1 flex-col gap-3 p-2 sm:p-4 lg:min-h-0 lg:flex-row">
      <section className="flex flex-col gap-3 lg:min-h-0 lg:flex-1">
        <RunControls
          scenarios={scenarios}
          run={run}
          fetchedAt={fetchedAt}
          now={now}
          timeZone={timeZone}
        />
        <div className="h-72 sm:h-96 lg:h-auto lg:min-h-72 lg:flex-1">
          <CommunityMap layout={layout} highlights={mapHighlights(live, now)} paths={paths} />
        </div>
        <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full border-2 border-emerald-400" /> object in view
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full bg-yellow-400/60" /> new event
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded-full bg-fuchsia-400" /> path, tagged with its
            anonymous ID
          </span>
        </p>
      </section>
      <aside className="flex h-[28rem] flex-col lg:h-auto lg:w-[26rem]">
        <EventFeed events={live.events} nodes={nodes} timeZone={timeZone} status={status} />
      </aside>
    </main>
  )
}

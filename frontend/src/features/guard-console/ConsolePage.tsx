import { Navigate } from 'react-router'
import { useLayout } from '../../api/queries'
import type { Layout, Session } from '../../api/types'
import { CommunityMap } from '../../components/map/CommunityMap'
import { useSession } from '../../lib/session'

/** The console both roles land on (D-66). M0 shows the map; alerts and the timeline come later. */
export function ConsolePage() {
  const session = useSession((state) => state.session)
  if (!session) return <Navigate to="/" replace />
  return <Console session={session} />
}

function Console({ session }: { session: Session }) {
  const layout = useLayout(session.community_id)
  const signOut = useSession((state) => state.signOut)
  const { user } = session

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center gap-3 border-b border-slate-800 px-4 py-2">
        <span className="font-semibold tracking-wide text-sky-400">JagaLink</span>
        <span className="hidden truncate text-sm text-slate-400 sm:inline">
          {layout.data?.community.name}
        </span>
        <span className="ml-auto truncate text-sm">
          {user.name}{' '}
          <span className="text-slate-500">
            · {user.role === 'supervisor' ? 'Supervisor' : 'Guard'}
          </span>
        </span>
        <button
          type="button"
          onClick={signOut}
          className="shrink-0 rounded-md border border-slate-700 px-3 py-1 text-sm hover:border-slate-500"
        >
          Sign out
        </button>
      </header>

      <main className="flex min-h-0 flex-1 flex-col gap-2 p-2 sm:p-4">
        {layout.isPending && <p className="m-auto text-sm text-slate-400">Loading the map…</p>}
        {layout.isError && (
          <div
            role="alert"
            className="m-auto max-w-sm rounded-lg border border-red-500/40 bg-red-500/10 p-4"
          >
            <p className="font-medium text-red-200">Cannot load the map.</p>
            <p className="mt-1 text-sm text-red-200/80">{layout.error.message}</p>
            <button
              type="button"
              onClick={() => layout.refetch()}
              disabled={layout.isFetching}
              className="mt-3 rounded-md bg-red-500/20 px-3 py-1.5 text-sm font-medium text-red-100 hover:bg-red-500/30 disabled:opacity-50"
            >
              Retry
            </button>
          </div>
        )}
        {layout.data && (
          <>
            <MapLegend layout={layout.data} />
            <div className="min-h-0 flex-1">
              <CommunityMap layout={layout.data} />
            </div>
          </>
        )}
      </main>
    </div>
  )
}

function MapLegend({ layout }: { layout: Layout }) {
  const cameras = layout.nodes.filter((node) => node.kind === 'camera').length
  return (
    <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-full bg-sky-400" /> {cameras} cameras
      </span>
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-sm bg-amber-400" /> {layout.nodes.length - cameras}{' '}
        sensors
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-0.5 w-4 bg-slate-400" /> {layout.links.length} links, arrow = one-way
      </span>
    </p>
  )
}

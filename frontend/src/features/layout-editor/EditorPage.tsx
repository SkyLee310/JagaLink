import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useEffectEvent, useReducer, useState } from 'react'
import { Navigate } from 'react-router'
import { errorLines } from '../../api/client'
import {
  exportLayout,
  fetchLayout,
  useImportLayout,
  useLayout,
  useSaveLayout,
} from '../../api/queries'
import type { Layout, Session } from '../../api/types'
import { AppHeader } from '../../components/AppHeader'
import { downloadJson } from '../../lib/download'
import { useSession } from '../../lib/session'
import { EditorCanvas } from './EditorCanvas'
import {
  editorReducer,
  initEditor,
  isDirty,
  type Notice,
  toLayoutInput,
  TOOLS,
} from './editorState'
import { EditorToolbar } from './EditorToolbar'
import { PropertiesPanel } from './PropertiesPanel'

/** The supervisor's layout editor (F1, D-66): draw, link, save, export and import. */
export function EditorPage() {
  const session = useSession((state) => state.session)
  if (!session) return <Navigate to="/" replace />
  if (session.user.role !== 'supervisor') return <Navigate to="/console" replace />
  return <EditorScreen session={session} />
}

function EditorScreen({ session }: { session: Session }) {
  const layout = useLayout(session.community_id)
  if (layout.data) return <LayoutEditor session={session} initial={layout.data} />

  return (
    <div className="flex h-dvh flex-col">
      <AppHeader session={session} />
      <main className="flex flex-1 p-4">
        {layout.isPending && <p className="m-auto text-sm text-slate-400">Loading the layout…</p>}
        {layout.isError && (
          <div
            role="alert"
            className="m-auto max-w-sm rounded-lg border border-red-500/40 bg-red-500/10 p-4"
          >
            <p className="font-medium text-red-200">Cannot load the layout.</p>
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
      </main>
    </div>
  )
}

interface Failure {
  title: string
  error: unknown
}

const newId = () => crypto.randomUUID()

function LayoutEditor({ session, initial }: { session: Session; initial: Layout }) {
  const communityId = session.community_id
  const queryClient = useQueryClient()
  const [state, dispatch] = useReducer(editorReducer, initial, initEditor)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [loading, setLoading] = useState(false)
  const save = useSaveLayout(communityId)
  const importFile = useImportLayout(communityId)
  const dirty = isDirty(state)
  const busy = loading || save.isPending || importFile.isPending

  const confirmDiscard = () =>
    !dirty || window.confirm('Discard your unsaved changes to the layout?')

  const onSave = () => {
    setFailure(null)
    save.mutate(toLayoutInput(state.draft), {
      onSuccess: (layout) => dispatch({ type: 'loaded', layout }),
      onError: (error) => setFailure({ title: 'The layout was not saved', error }),
    })
  }

  // Reload and export read the server; each failure shows instead of the editor going stale.
  const fromServer = async (title: string, task: () => Promise<void>) => {
    setFailure(null)
    setLoading(true)
    try {
      await task()
    } catch (error) {
      setFailure({ title, error })
    } finally {
      setLoading(false)
    }
  }

  const onReload = () => {
    if (!confirmDiscard()) return
    void fromServer('Cannot reload the layout', async () => {
      const layout = await fetchLayout(communityId)
      queryClient.setQueryData(['layout', communityId], layout)
      dispatch({ type: 'loaded', layout })
    })
  }

  const onExport = () =>
    void fromServer('Cannot export the layout', async () => {
      downloadJson(await exportLayout(communityId), `${state.community.code}.json`)
    })

  const onImport = async (file: File) => {
    if (!confirmDiscard()) return
    setFailure(null)
    let content: unknown
    try {
      content = JSON.parse(await file.text())
    } catch {
      const error = new Error(`${file.name} is not a JSON layout file.`)
      setFailure({ title: 'The file was not imported', error })
      return
    }
    importFile.mutate(content, {
      onSuccess: (layout) => dispatch({ type: 'loaded', layout }),
      onError: (error) => setFailure({ title: 'The file was not imported', error }),
    })
  }

  const onClear = () => {
    const question = 'Remove every camera, sensor and link? The server keeps them until you save.'
    if (window.confirm(question)) dispatch({ type: 'clear' })
  }

  const onKeyDown = useEffectEvent((event: KeyboardEvent) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
      event.preventDefault()
      if (dirty && !busy) onSave()
      return
    }
    if (event.ctrlKey || event.metaKey || event.altKey || isTyping(event.target)) return
    if (event.key === 'Delete' || event.key === 'Backspace') {
      dispatch({ type: 'deleteSelection' })
    } else if (event.key === 'Escape') {
      dispatch({ type: 'cancel' })
    } else {
      const item = TOOLS.find(({ key }) => key === event.key.toLowerCase())
      if (item) dispatch({ type: 'setTool', tool: item.tool })
    }
  })

  useEffect(() => {
    const listener = (event: KeyboardEvent) => onKeyDown(event)
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  }, [])

  // Closing or refreshing the tab with unsaved edits asks first.
  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  return (
    <div className="flex h-dvh flex-col">
      <AppHeader
        session={session}
        communityName={state.community.name}
        confirmLeave={confirmDiscard}
      />
      <EditorToolbar
        tool={state.tool}
        onTool={(tool) => dispatch({ type: 'setTool', tool })}
        dirty={dirty}
        busy={busy}
        onSave={onSave}
        onReload={onReload}
        onExport={onExport}
        onImport={(file) => void onImport(file)}
        onClear={onClear}
      />
      <main className="flex min-h-0 flex-1 flex-col overflow-y-auto md:flex-row md:overflow-hidden">
        <div className="relative h-[55dvh] shrink-0 p-2 md:h-auto md:min-h-0 md:flex-1">
          <EditorCanvas state={state} dispatch={dispatch} newId={newId} />
          {/* Messages float over the map, so it keeps its size and nodes stay under the pointer. */}
          {(state.notice || failure) && (
            <div className="pointer-events-none absolute inset-x-4 top-4 z-10 flex flex-col gap-2">
              {state.notice && (
                <NoticeBar
                  notice={state.notice}
                  onDismiss={() => dispatch({ type: 'dismissNotice' })}
                />
              )}
              {failure && <FailureBar failure={failure} onDismiss={() => setFailure(null)} />}
            </div>
          )}
        </div>
        <PropertiesPanel state={state} dispatch={dispatch} />
      </main>
    </div>
  )
}

function NoticeBar({ notice, onDismiss }: { notice: Notice; onDismiss: () => void }) {
  const error = notice.tone === 'error'
  return (
    <div
      role={error ? 'alert' : 'status'}
      className={`pointer-events-auto flex items-center gap-3 rounded-md border px-3 py-2 text-sm shadow-lg ${
        error
          ? 'border-red-500/50 bg-red-950/95 text-red-200'
          : 'border-sky-500/50 bg-sky-950/95 text-sky-200'
      }`}
    >
      <p className="flex-1">{notice.text}</p>
      <DismissButton onClick={onDismiss} />
    </div>
  )
}

function FailureBar({ failure, onDismiss }: { failure: Failure; onDismiss: () => void }) {
  const message = failure.error instanceof Error ? failure.error.message : String(failure.error)
  const lines = errorLines(failure.error).filter((line) => line !== message)
  return (
    <div
      role="alert"
      className="pointer-events-auto flex max-h-64 items-start gap-3 overflow-y-auto rounded-md border border-red-500/50 bg-red-950/95 px-3 py-2 text-sm text-red-200 shadow-lg"
    >
      <div className="flex-1">
        <p className="font-medium">{failure.title}</p>
        <p className="text-red-200/90">{message}</p>
        {lines.length > 0 && (
          <ul className="mt-1 list-disc pl-5 text-xs text-red-200/80">
            {lines.slice(0, 8).map((line, index) => (
              <li key={index}>{line}</li>
            ))}
            {lines.length > 8 && <li>…and {lines.length - 8} more</li>}
          </ul>
        )}
      </div>
      <DismissButton onClick={onDismiss} />
    </div>
  )
}

function DismissButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="shrink-0 rounded-md px-2 py-0.5 text-xs opacity-80 hover:bg-white/10 hover:opacity-100"
    >
      Dismiss
    </button>
  )
}

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return target.isContentEditable || ['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName)
}

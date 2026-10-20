import { useRef } from 'react'
import { type Tool, TOOLS } from './editorState'

interface EditorToolbarProps {
  tool: Tool
  onTool: (tool: Tool) => void
  dirty: boolean
  /** A save, reload, export or import is waiting for the server. */
  busy: boolean
  onSave: () => void
  onReload: () => void
  onExport: () => void
  onImport: (file: File) => void
  onClear: () => void
}

const BUTTON =
  'rounded-md border border-slate-700 px-3 py-1 text-sm hover:border-slate-500 disabled:cursor-not-allowed disabled:opacity-40'

export function EditorToolbar(props: EditorToolbarProps) {
  const { tool, dirty, busy } = props
  const fileRef = useRef<HTMLInputElement>(null)

  return (
    <div
      role="toolbar"
      aria-label="Layout tools"
      className="flex flex-wrap items-center gap-2 border-b border-slate-800 px-4 py-2"
    >
      <div role="group" aria-label="Tools" className="flex gap-1">
        {TOOLS.map((item) => (
          <button
            key={item.tool}
            type="button"
            aria-pressed={tool === item.tool}
            title={`${item.label} (${item.key.toUpperCase()})`}
            onClick={() => props.onTool(item.tool)}
            className={`rounded-md px-3 py-1 text-sm ${
              tool === item.tool
                ? 'bg-sky-500 font-medium text-slate-950'
                : 'border border-slate-700 hover:border-slate-500'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <span
        role="status"
        className={`ml-auto rounded-full px-2.5 py-0.5 text-xs ${
          dirty ? 'bg-amber-500/15 text-amber-300' : 'bg-emerald-500/15 text-emerald-300'
        }`}
      >
        {dirty ? 'Unsaved changes' : 'All changes saved'}
      </span>
      <button
        type="button"
        onClick={props.onSave}
        disabled={!dirty || busy}
        className="rounded-md bg-sky-500 px-3 py-1 text-sm font-medium text-slate-950 hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Save
      </button>
      <button type="button" onClick={props.onReload} disabled={busy} className={BUTTON}>
        Reload
      </button>
      <button
        type="button"
        onClick={props.onExport}
        disabled={busy || dirty}
        title={dirty ? 'Save first: the file holds the saved layout' : 'Download the saved layout'}
        className={BUTTON}
      >
        Export
      </button>
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        disabled={busy}
        className={BUTTON}
      >
        Import
      </button>
      <input
        ref={fileRef}
        type="file"
        accept="application/json,.json"
        aria-label="Layout file to import"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = '' // picking the same file again still imports it
          if (file) props.onImport(file)
        }}
      />
      <button type="button" onClick={props.onClear} disabled={busy} className={BUTTON}>
        Clear
      </button>
    </div>
  )
}

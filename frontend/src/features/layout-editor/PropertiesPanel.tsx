import { type Dispatch, type ReactNode, useId, useState } from 'react'
import type { LayoutLink, LayoutNode } from '../../api/types'
import {
  arrow,
  type EditorAction,
  type EditorState,
  findNode,
  type LinkChanges,
  type NodeChanges,
  TOOLS,
  WALK_SPEED,
} from './editorState'

// The API's rule for node codes (D-75), e.g. c-gate-02.
const CODE_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/

interface PanelProps {
  state: EditorState
  dispatch: Dispatch<EditorAction>
}

/** Fields of the selected node or link, or what the current tool does. */
export function PropertiesPanel({ state, dispatch }: PanelProps) {
  const { selection } = state
  const node = selection?.kind === 'node' ? findNode(state, selection.id) : undefined
  const link =
    selection?.kind === 'link'
      ? state.draft.links.find((item) => item.id === selection.id)
      : undefined

  return (
    <aside
      aria-label="Properties"
      className="w-full shrink-0 overflow-y-auto border-t border-slate-800 p-4 md:w-80 md:border-t-0 md:border-l"
    >
      {node ? (
        <NodeFields key={node.id} node={node} state={state} dispatch={dispatch} />
      ) : link ? (
        <LinkFields key={link.id} link={link} state={state} dispatch={dispatch} />
      ) : (
        <ToolHint state={state} />
      )}
    </aside>
  )
}

function NodeFields({ node, state, dispatch }: PanelProps & { node: LayoutNode }) {
  const update = (changes: NodeChanges) => dispatch({ type: 'updateNode', id: node.id, changes })
  const kindName = node.kind === 'camera' ? 'camera' : 'sensor'
  const codeTaken = state.draft.nodes.some(
    (other) => other.id !== node.id && other.code === node.code,
  )
  const codeProblem = !CODE_PATTERN.test(node.code)
    ? 'Lowercase letters and digits in groups joined by single dashes, e.g. c-gate-02'
    : node.code.length > 40
      ? 'At most 40 characters'
      : codeTaken
        ? 'Another node already has this code'
        : null
  const linkCount = state.draft.links.filter(
    (link) => link.from_node_id === node.id || link.to_node_id === node.id,
  ).length

  return (
    <section aria-labelledby="node-heading" className="flex flex-col gap-3">
      <h2 id="node-heading" className="text-sm font-semibold text-slate-200 capitalize">
        {kindName} {node.code}
      </h2>
      <Field label="Name" problem={node.name.trim() ? null : 'A name is required'}>
        {(id) => (
          <input
            id={id}
            value={node.name}
            maxLength={80}
            onChange={(event) => update({ name: event.target.value })}
            className={INPUT}
          />
        )}
      </Field>
      <Field label="Code" problem={codeProblem}>
        {(id) => (
          <input
            id={id}
            value={node.code}
            spellCheck={false}
            onChange={(event) => update({ code: event.target.value.trim().toLowerCase() })}
            className={`${INPUT} font-mono`}
          />
        )}
      </Field>
      <Field label="Kind">
        {(id) => (
          <select
            id={id}
            value={node.kind}
            onChange={(event) => update({ kind: event.target.value as LayoutNode['kind'] })}
            className={INPUT}
          >
            <option value="camera">Camera</option>
            <option value="sensor">Sensor</option>
          </select>
        )}
      </Field>
      <Field label="Zone" hint="Set from the map when you place or move the node.">
        {(id) => (
          <select
            id={id}
            value={node.zone_id ?? ''}
            onChange={(event) => update({ zone_id: event.target.value || null })}
            className={INPUT}
          >
            <option value="">No zone</option>
            {state.zones.map((zone) => (
              <option key={zone.id} value={zone.id}>
                {zone.name} ({zone.kind})
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field label="Facing (degrees, 0 = up)">
        {(id) => (
          <div className="flex items-center gap-2">
            <input
              type="range"
              min={0}
              max={359}
              value={node.heading_deg}
              aria-label="Facing slider"
              onChange={(event) => update({ heading_deg: Number(event.target.value) })}
              className="flex-1 accent-sky-400"
            />
            <NumberInput
              id={id}
              value={node.heading_deg}
              integer
              onChange={(value) => value !== null && update({ heading_deg: value })}
              className={`${INPUT} w-16`}
            />
          </div>
        )}
      </Field>
      <p className="text-xs text-slate-500">
        At x {node.x}, y {node.y} · {linkCount} {linkCount === 1 ? 'link' : 'links'}
      </p>
      <DeleteButton dispatch={dispatch}>Delete {kindName}</DeleteButton>
    </section>
  )
}

function LinkFields({ link, state, dispatch }: PanelProps & { link: LayoutLink }) {
  const update = (changes: LinkChanges) => dispatch({ type: 'updateLink', id: link.id, changes })
  const windowProblem =
    link.travel_min_s <= 0
      ? 'The minimum must be above 0 s'
      : link.travel_min_s > link.travel_max_s
        ? 'The minimum must not exceed the maximum'
        : null

  return (
    <section aria-labelledby="link-heading" className="flex flex-col gap-3">
      <h2 id="link-heading" className="text-sm font-semibold text-slate-200">
        Link {arrow(state, link)}
      </h2>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Min walk (s)">
          {(id) => (
            <NumberInput
              id={id}
              value={link.travel_min_s}
              integer
              onChange={(value) => value !== null && update({ travel_min_s: value })}
              className={INPUT}
            />
          )}
        </Field>
        <Field label="Max walk (s)">
          {(id) => (
            <NumberInput
              id={id}
              value={link.travel_max_s}
              integer
              onChange={(value) => value !== null && update({ travel_max_s: value })}
              className={INPUT}
            />
          )}
        </Field>
      </div>
      {windowProblem && <p className="-mt-1 text-xs text-red-300">{windowProblem}</p>}
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={link.bidirectional}
          onChange={(event) => update({ bidirectional: event.target.checked })}
          className="accent-sky-400"
        />
        Two-way
      </label>
      <Field
        label="Walking distance (m)"
        hint={`New links start from the straight-line distance, walked at ${WALK_SPEED.slow}–${WALK_SPEED.fast} m/s.`}
      >
        {(id) => (
          <NumberInput
            id={id}
            value={link.distance_m}
            allowEmpty
            onChange={(value) => update({ distance_m: value })}
            className={INPUT}
          />
        )}
      </Field>
      <DeleteButton dispatch={dispatch}>Delete link</DeleteButton>
    </section>
  )
}

function ToolHint({ state }: { state: EditorState }) {
  const start = state.linkStart ? findNode(state, state.linkStart) : undefined
  const hints: Record<EditorState['tool'], string> = {
    select: 'Click a camera, sensor or link to edit it. Drag a node to move it; drag the white handle of a camera to turn it.',
    camera: 'Click the map to place a camera.',
    sensor: 'Click the map to place a sensor.',
    link: start
      ? `Now pick the node to link ${start.code} to.`
      : 'Pick the first node, then the second; the link gets walking times from the distance.',
  }
  return (
    <section aria-labelledby="hint-heading" className="flex flex-col gap-3 text-sm text-slate-300">
      <h2 id="hint-heading" className="font-semibold text-slate-200">
        {TOOLS.find(({ tool }) => tool === state.tool)?.label} tool
      </h2>
      <p>{hints[state.tool]}</p>
      <p className="text-xs text-slate-500">
        {state.draft.nodes.length} nodes · {state.draft.links.length} links
      </p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs text-slate-400">
        {TOOLS.map(({ label, key }) => (
          <Shortcut key={key} keys={key.toUpperCase()} action={`${label} tool`} />
        ))}
        <Shortcut keys="Del" action="Delete the selection" />
        <Shortcut keys="Esc" action="Cancel" />
        <Shortcut keys="Ctrl S" action="Save" />
      </dl>
    </section>
  )
}

function Shortcut({ keys, action }: { keys: string; action: string }) {
  return (
    <>
      <dt>
        <kbd className="rounded border border-slate-700 px-1 font-mono">{keys}</kbd>
      </dt>
      <dd>{action}</dd>
    </>
  )
}

const INPUT =
  'w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm outline-none focus:border-sky-500 aria-invalid:border-red-400'

function Field(props: {
  label: string
  problem?: string | null
  hint?: string
  children: (id: string) => ReactNode
}) {
  const id = useId()
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs text-slate-400">
        {props.label}
      </label>
      {props.children(id)}
      {props.problem && <p className="text-xs text-red-300">{props.problem}</p>}
      {props.hint && !props.problem && <p className="text-xs text-slate-500">{props.hint}</p>}
    </div>
  )
}

/**
 * A text box for a number. It keeps what was typed while it is not yet a number ("4." or ""),
 * and reports only valid values.
 */
function NumberInput(props: {
  id: string
  value: number | null
  onChange: (value: number | null) => void
  integer?: boolean
  allowEmpty?: boolean
  className: string
}) {
  const { value, integer = false, allowEmpty = false } = props
  const parse = (raw: string): number | null | undefined => {
    const text = raw.trim()
    if (text === '') return allowEmpty ? null : undefined
    const number = Number(text)
    if (!Number.isFinite(number) || (integer && !Number.isInteger(number))) return undefined
    return number
  }
  const [text, setText] = useState(value === null ? '' : String(value))
  const [shown, setShown] = useState(value)
  if (value !== shown) {
    // The value changed from outside (a drag, a reload): show it unless the text already says so.
    setShown(value)
    if (parse(text) !== value) setText(value === null ? '' : String(value))
  }
  return (
    <input
      id={props.id}
      inputMode={integer ? 'numeric' : 'decimal'}
      value={text}
      aria-invalid={parse(text) === undefined}
      onChange={(event) => {
        setText(event.target.value)
        const number = parse(event.target.value)
        if (number !== undefined) props.onChange(number)
      }}
      className={props.className}
    />
  )
}

function DeleteButton({
  dispatch,
  children,
}: {
  dispatch: Dispatch<EditorAction>
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={() => dispatch({ type: 'deleteSelection' })}
      className="mt-2 self-start rounded-md border border-red-500/40 px-3 py-1 text-sm text-red-200 hover:bg-red-500/10"
    >
      {children}
    </button>
  )
}

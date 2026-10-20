import { useState } from 'react'
import { errorLines } from '../../api/client'
import { useRunAction, useStartRun } from '../../api/queries'
import type { Run, Scenario } from '../../api/types'
import { localTime, RUN_STATE_TEXT, runClock, runProgress } from '../../lib/runTime'

const SPEEDS = [1, 5, 10, 30, 60, 120]

interface RunControlsProps {
  scenarios: Scenario[]
  run: Run | null
  /** When `run` was fetched (ms), to tick its clock between polls. */
  fetchedAt: number
  now: number
  timeZone: string
}

/** Pick a scenario and speed; play, pause and reset are one click each (F2). */
export function RunControls({ scenarios, run, fetchedAt, now, timeZone }: RunControlsProps) {
  const [picked, setPicked] = useState<string | null>(null)
  const [chosenSpeed, setChosenSpeed] = useState<number | null>(null)
  const start = useStartRun()
  const act = useRunAction()

  const scenarioId = picked ?? run?.scenario_id ?? scenarios[0]?.id
  const scenario = scenarios.find((item) => item.id === scenarioId)
  // The controls act on the live run only while it plays the picked scenario.
  const active = run && run.scenario_id === scenarioId && run.state !== 'stopped' ? run : null
  const speed = chosenSpeed ?? active?.speed ?? scenario?.default_speed ?? 10
  const busy = start.isPending || act.isPending
  const failure = start.error ?? act.error

  const play = () => {
    start.reset()
    act.reset()
    if (active && (active.state === 'ready' || active.state === 'paused')) {
      act.mutate({ runId: active.id, action: 'resume', speed })
    } else if (scenarioId) {
      start.mutate({ scenario_id: scenarioId, speed })
    }
  }
  const control = (action: 'pause' | 'reset') => {
    start.reset()
    act.reset()
    if (active) act.mutate({ runId: active.id, action })
  }
  const changeSpeed = (value: number) => {
    setChosenSpeed(value)
    if (active?.state === 'playing') act.mutate({ runId: active.id, action: 'resume', speed: value })
  }

  const clock = active ? runClock(active, fetchedAt, now) : null
  const shown = active ?? scenario

  return (
    <section aria-label="Scenario controls" className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex min-w-48 flex-1 flex-col gap-1 text-xs text-slate-400">
          Scenario
          <select
            value={scenarioId ?? ''}
            onChange={(event) => {
              setPicked(event.target.value)
              setChosenSpeed(null)
            }}
            className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          >
            {scenarios.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Speed
          <select
            value={speed}
            onChange={(event) => changeSpeed(Number(event.target.value))}
            disabled={busy}
            className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          >
            {[...new Set([...SPEEDS, speed])]
              .sort((a, b) => a - b)
              .map((value) => (
                <option key={value} value={value}>
                  {value}×
                </option>
              ))}
          </select>
        </label>
        <div className="flex gap-1.5">
          <button
            type="button"
            onClick={play}
            disabled={busy || !scenarioId || active?.state === 'playing'}
            className="rounded-md bg-sky-500 px-3 py-1.5 text-sm font-medium text-slate-950 hover:bg-sky-400 disabled:opacity-40"
          >
            Play
          </button>
          <button
            type="button"
            onClick={() => control('pause')}
            disabled={busy || active?.state !== 'playing'}
            className="rounded-md border border-slate-600 px-3 py-1.5 text-sm hover:border-slate-400 disabled:opacity-40"
          >
            Pause
          </button>
          <button
            type="button"
            onClick={() => control('reset')}
            disabled={busy || !active || active.state === 'ready'}
            className="rounded-md border border-slate-600 px-3 py-1.5 text-sm hover:border-slate-400 disabled:opacity-40"
          >
            Reset
          </button>
        </div>
      </div>

      {scenario && <p className="text-xs text-slate-400">{scenario.description}</p>}

      {shown && (
        <div className="flex items-center gap-3 text-sm">
          <span
            className={`rounded px-2 py-0.5 text-xs font-medium ${
              active?.state === 'playing'
                ? 'bg-emerald-500/15 text-emerald-300'
                : 'bg-slate-700/60 text-slate-300'
            }`}
          >
            {active ? RUN_STATE_TEXT[active.state] : 'Not started'}
          </span>
          <span className="font-mono tabular-nums" aria-label="Simulated time">
            {localTime(clock ?? shown.window_start, timeZone)}
          </span>
          <div
            role="progressbar"
            aria-label="Live window played"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round((active && clock ? runProgress(active, clock) : 0) * 100)}
            className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800"
          >
            <div
              className="h-full bg-sky-500 transition-[width] duration-200"
              style={{ width: `${(active && clock ? runProgress(active, clock) : 0) * 100}%` }}
            />
          </div>
          <span className="font-mono text-xs text-slate-400 tabular-nums">
            {localTime(shown.window_start, timeZone).slice(0, 5)}–
            {localTime(shown.window_end, timeZone).slice(0, 5)}
          </span>
          {active && (
            <span className="text-xs text-slate-400 tabular-nums">
              {active.events_emitted}/{active.events_total} events
            </span>
          )}
        </div>
      )}

      {failure && (
        <div
          role="alert"
          className="rounded-md border border-red-500/50 bg-red-950/60 px-3 py-2 text-sm text-red-200"
        >
          <p>{failure.message}</p>
          {errorLines(failure)
            .filter((line) => line !== failure.message)
            .slice(0, 6)
            .map((line) => (
              <p key={line} className="text-xs text-red-200/80">
                {line}
              </p>
            ))}
        </div>
      )}
    </section>
  )
}

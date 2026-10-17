import { useNavigate } from 'react-router'
import { useCreateSession, useSessionUsers } from '../../api/queries'
import type { SessionUser } from '../../api/types'

const ROLE_GROUPS = [
  { role: 'supervisor', title: 'Supervisor', hint: 'Runs the guard team and sets up the cameras' },
  { role: 'guard', title: 'Guards', hint: 'On shift at the gate or on patrol' },
] as const

/** Pick a seeded staff member instead of logging in (D-28). */
export function RolePickerPage() {
  const users = useSessionUsers()
  const createSession = useCreateSession()
  const navigate = useNavigate()

  const pick = (user: SessionUser) =>
    createSession.mutate(user.id, { onSuccess: () => navigate('/console') })

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col gap-8 px-4 py-10">
      <header>
        <p className="text-sm font-semibold tracking-[0.2em] text-sky-400 uppercase">JagaLink</p>
        <h1 className="mt-2 text-2xl font-semibold">Who is on shift?</h1>
        <p className="mt-2 text-sm text-slate-400">
          Pick a staff member to open the console. This prototype has no real login.
        </p>
      </header>

      {users.isPending && <p className="text-sm text-slate-400">Loading staff…</p>}

      {users.isError && (
        <div role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 p-4">
          <p className="font-medium text-red-200">Cannot load the staff list.</p>
          <p className="mt-1 text-sm text-red-200/80">{users.error.message}</p>
          <button
            type="button"
            onClick={() => users.refetch()}
            disabled={users.isFetching}
            className="mt-3 rounded-md bg-red-500/20 px-3 py-1.5 text-sm font-medium text-red-100 hover:bg-red-500/30 disabled:opacity-50"
          >
            Retry
          </button>
        </div>
      )}

      {users.data &&
        ROLE_GROUPS.map(({ role, title, hint }) => {
          const members = users.data.filter((user) => user.role === role)
          if (members.length === 0) return null
          return (
            <section key={role} aria-labelledby={`role-${role}`}>
              <h2 id={`role-${role}`} className="text-sm font-semibold text-slate-200">
                {title}
              </h2>
              <p className="text-xs text-slate-500">{hint}</p>
              <ul className="mt-3 grid gap-2">
                {members.map((user) => (
                  <li key={user.id}>
                    <button
                      type="button"
                      onClick={() => pick(user)}
                      disabled={createSession.isPending}
                      className="flex w-full items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900 px-4 py-3 text-left outline-none transition hover:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-400 disabled:opacity-60"
                    >
                      <span>
                        <span className="block font-medium">{user.name}</span>
                        <span className="block text-xs text-slate-500">{user.code}</span>
                      </span>
                      <DutyBadge onDuty={user.on_duty} />
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )
        })}

      {createSession.isError && (
        <p role="alert" className="text-sm text-red-300">
          Could not start the session: {createSession.error.message}
        </p>
      )}
    </main>
  )
}

function DutyBadge({ onDuty }: { onDuty: boolean }) {
  return onDuty ? (
    <span className="shrink-0 rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-300">
      On duty
    </span>
  ) : (
    <span className="shrink-0 rounded-full bg-slate-700/40 px-2 py-0.5 text-xs text-slate-400">
      Off duty
    </span>
  )
}

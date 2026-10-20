import type { MouseEvent } from 'react'
import { NavLink } from 'react-router'
import type { Session } from '../api/types'
import { useSession } from '../lib/session'

type Role = Session['user']['role']

// Screens per role (D-66): a guard gets the console; a supervisor also gets the editor and the
// scenario player.
const PAGES: { to: string; label: string; roles: Role[] }[] = [
  { to: '/console', label: 'Console', roles: ['guard', 'supervisor'] },
  { to: '/editor', label: 'Layout', roles: ['supervisor'] },
  { to: '/player', label: 'Scenarios', roles: ['supervisor'] },
]

interface AppHeaderProps {
  session: Session
  communityName?: string
  /** Asked before leaving the page; returning false keeps the user here (unsaved edits). */
  confirmLeave?: () => boolean
}

export function AppHeader({ session, communityName, confirmLeave }: AppHeaderProps) {
  const signOut = useSession((state) => state.signOut)
  const { user } = session
  const pages = PAGES.filter((page) => page.roles.includes(user.role))
  const guardLeave = (event: MouseEvent) => {
    if (confirmLeave && !confirmLeave()) event.preventDefault()
  }

  return (
    <header className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-slate-800 px-4 py-2">
      <span className="font-semibold tracking-wide text-sky-400">JagaLink</span>
      {pages.length > 1 && (
        // On a phone the page links take their own row under the brand and Sign out.
        <nav aria-label="Pages" className="order-last flex w-full gap-1 sm:order-none sm:w-auto">
          {pages.map((page) => (
            <NavLink
              key={page.to}
              to={page.to}
              onClick={guardLeave}
              className={({ isActive }) =>
                `rounded-md px-2.5 py-1 text-sm ${
                  isActive ? 'bg-slate-800 text-slate-100' : 'text-slate-400 hover:text-slate-100'
                }`
              }
            >
              {page.label}
            </NavLink>
          ))}
        </nav>
      )}
      <span className="hidden truncate text-sm text-slate-400 md:inline">{communityName}</span>
      <span className="ml-auto truncate text-sm">
        {user.name}{' '}
        <span className="text-slate-500">· {user.role === 'supervisor' ? 'Supervisor' : 'Guard'}</span>
      </span>
      <button
        type="button"
        onClick={(event) => {
          guardLeave(event)
          if (!event.defaultPrevented) signOut()
        }}
        className="shrink-0 rounded-md border border-slate-700 px-3 py-1 text-sm hover:border-slate-500"
      >
        Sign out
      </button>
    </header>
  )
}

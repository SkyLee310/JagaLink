import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type { Session } from '../api/types'

interface SessionStore {
  session: Session | null
  signIn: (session: Session) => void
  signOut: () => void
}

/**
 * The picked seeded user and their token (D-28). It lives in sessionStorage, so a refresh keeps
 * it and each browser tab can hold a different role.
 */
export const useSession = create<SessionStore>()(
  persist(
    (set) => ({
      session: null,
      signIn: (session) => set({ session }),
      signOut: () => set({ session: null }),
    }),
    {
      name: 'jagalink-session',
      storage: createJSONStorage(() => sessionStorage),
      partialize: ({ session }) => ({ session }),
    },
  ),
)

import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import { useSession } from '../lib/session'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  useSession.getState().signOut()
  sessionStorage.clear()
})

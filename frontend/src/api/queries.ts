import { useMutation, useQuery } from '@tanstack/react-query'
import { useSession } from '../lib/session'
import { apiFetch } from './client'
import type { Layout, Session, SessionUser } from './types'

export function useSessionUsers() {
  return useQuery({
    queryKey: ['session-users'],
    queryFn: () => apiFetch<SessionUser[]>('/session/users'),
  })
}

export function useCreateSession() {
  const signIn = useSession((state) => state.signIn)
  return useMutation({
    mutationFn: (userId: string) =>
      apiFetch<Session>('/session', { method: 'POST', body: JSON.stringify({ user_id: userId }) }),
    onSuccess: signIn,
  })
}

export function useLayout(communityId: string) {
  return useQuery({
    queryKey: ['layout', communityId],
    queryFn: () => apiFetch<Layout>(`/communities/${communityId}/layout`),
  })
}

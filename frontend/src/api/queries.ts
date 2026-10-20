import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSession } from '../lib/session'
import { apiFetch } from './client'
import type { Layout, LayoutFile, LayoutInput, Session, SessionUser } from './types'

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

export function fetchLayout(communityId: string) {
  return apiFetch<Layout>(`/communities/${communityId}/layout`)
}

export function useLayout(communityId: string) {
  return useQuery({ queryKey: ['layout', communityId], queryFn: () => fetchLayout(communityId) })
}

/** The layout as a file with codes instead of IDs (D-75); it reflects the last save. */
export function exportLayout(communityId: string) {
  return apiFetch<LayoutFile>(`/communities/${communityId}/export`)
}

/** Saves the whole layout in one transaction (F1); the answer is the layout as stored. */
export function useSaveLayout(communityId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: LayoutInput) =>
      apiFetch<Layout>(`/communities/${communityId}/layout`, {
        method: 'PUT',
        body: JSON.stringify(body),
      }),
    onSuccess: (layout) => queryClient.setQueryData(['layout', communityId], layout),
  })
}

/** Replaces the stored layout with a layout file's (F1). */
export function useImportLayout(communityId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: unknown) =>
      apiFetch<Layout>(`/communities/${communityId}/import`, {
        method: 'POST',
        body: JSON.stringify(file),
      }),
    onSuccess: (layout) => queryClient.setQueryData(['layout', communityId], layout),
  })
}

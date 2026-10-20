import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSession } from '../lib/session'
import { apiFetch } from './client'
import type {
  Alert,
  AlertActionInput,
  Layout,
  LayoutFile,
  LayoutInput,
  Run,
  Scenario,
  Session,
  SessionUser,
} from './types'

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

/** Scripted scenarios with their live window (F2); never their ground truth (D-70). */
export function useScenarios() {
  return useQuery({ queryKey: ['scenarios'], queryFn: () => apiFetch<Scenario[]>('/scenarios') })
}

const CURRENT_RUN = ['current-run']

/** The community's live run, or null; polled faster while it plays. */
export function useCurrentRun() {
  return useQuery({
    queryKey: CURRENT_RUN,
    queryFn: () => apiFetch<Run | null>('/scenario-runs/current'),
    refetchInterval: (query) => (query.state.data?.state === 'playing' ? 1000 : 5000),
  })
}

/** Plays a scenario; the community's previous run stops (D-77). */
export function useStartRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { scenario_id: string; speed?: number }) =>
      apiFetch<Run>('/scenario-runs', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: (run) => queryClient.setQueryData(CURRENT_RUN, run),
  })
}

export type RunAction = 'pause' | 'resume' | 'reset'

/** Pause, resume (optionally at a new speed) or reset the run. */
export function useRunAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ runId, action, speed }: { runId: string; action: RunAction; speed?: number }) =>
      apiFetch<Run>(`/scenario-runs/${runId}/${action}`, {
        method: 'POST',
        body: speed === undefined ? undefined : JSON.stringify({ speed }),
      }),
    onSuccess: (run) => queryClient.setQueryData(CURRENT_RUN, run),
  })
}

/**
 * Confirms or dismisses an alert with an optional one-line reason (F6). The answer is the alert
 * as stored; every other open screen gets it as `alert_update`.
 */
export function useAlertAction() {
  return useMutation({
    mutationFn: ({ alertId, ...body }: AlertActionInput & { alertId: string }) =>
      apiFetch<Alert>(`/alerts/${alertId}/actions`, { method: 'POST', body: JSON.stringify(body) }),
  })
}

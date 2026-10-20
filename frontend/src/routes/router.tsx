import { createBrowserRouter, Navigate } from 'react-router'
import { ConsolePage } from '../features/guard-console/ConsolePage'
import { EditorPage } from '../features/layout-editor/EditorPage'
import { PlayerPage } from '../features/scenario-player/PlayerPage'
import { RolePickerPage } from '../features/session/RolePickerPage'

// Both roles land on /console; supervisor pages check the role themselves (D-66).
export const router = createBrowserRouter([
  { path: '/', element: <RolePickerPage /> },
  { path: '/console', element: <ConsolePage /> },
  { path: '/editor', element: <EditorPage /> },
  { path: '/player', element: <PlayerPage /> },
  { path: '*', element: <Navigate to="/" replace /> },
])

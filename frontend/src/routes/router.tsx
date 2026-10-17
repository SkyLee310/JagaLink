import { createBrowserRouter, Navigate } from 'react-router'
import { ConsolePage } from '../features/guard-console/ConsolePage'
import { RolePickerPage } from '../features/session/RolePickerPage'

// Both roles land on /console; supervisor-only pages arrive from M1 (D-66).
export const router = createBrowserRouter([
  { path: '/', element: <RolePickerPage /> },
  { path: '/console', element: <ConsolePage /> },
  { path: '*', element: <Navigate to="/" replace /> },
])

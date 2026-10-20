import type { MapAlert, ZoneShape } from './mapShapes'

/** Colours shared by the read-only map and the layout editor. */
export const COLORS = {
  camera: '#38bdf8', // sky-400
  sensor: '#fbbf24', // amber-400
  offline: '#64748b', // slate-500
  link: '#94a3b8', // slate-400
  label: '#e2e8f0', // slate-200
  outline: '#020617', // slate-950
  selected: '#f8fafc', // slate-50
  pending: '#f472b6', // pink-400
  occupied: '#34d399', // emerald-400: an object is in view
  flash: '#facc15', // yellow-400: an event just arrived
  path: '#e879f9', // fuchsia-400: an anonymous path (F3)
  next: '#f8fafc', // slate-50: the camera to check next (F5)
}

/** An open alert's ring on the map, by severity (F6). */
export const ALERT_COLORS: Record<MapAlert['severity'], string> = {
  high: '#ef4444', // red-500
  medium: '#f97316', // orange-500
  low: '#eab308', // yellow-500
}

export const ZONE_COLORS: Record<ZoneShape['kind'], string> = {
  gate: '#f472b6', // pink-400
  street: '#a78bfa', // violet-400
  lane: '#34d399', // emerald-400
}

/** Text labels appear once the map is drawn at 60 % of its full size or more. */
export const LABEL_MIN_SCALE = 0.6

/** On-screen width kept for a node code label, in pixels. */
export const LABEL_WIDTH = 64

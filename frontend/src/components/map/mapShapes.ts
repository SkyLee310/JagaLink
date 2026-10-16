import type { Layout, LayoutNode, LayoutZone } from '../../api/types'

export interface Size {
  width: number
  height: number
}

/** World size of a community plan in canvas pixels: 1200 × 800 at 0.25 m/px (D-69). */
export const MAP_SIZE: Size = { width: 1200, height: 800 }

/** Field of view drawn for each camera, in degrees. */
export const CAMERA_FOV_DEG = 60

const ZONE_LABEL_INSET = 6

export type LinePoints = [number, number, number, number]

export interface ZoneShape {
  id: string
  name: string
  kind: LayoutZone['kind']
  points: number[]
  labelAt: { x: number; y: number }
}

export interface LinkShape {
  id: string
  points: LinePoints
  oneWay: boolean
}

export interface NodeShape {
  id: string
  code: string
  kind: LayoutNode['kind']
  x: number
  y: number
  offline: boolean
  wedgeRotation: number
}

export interface MapShapes {
  zones: ZoneShape[]
  links: LinkShape[]
  nodes: NodeShape[]
}

/** Largest scale that shows the whole world inside the viewport; 0 until the viewport has a size. */
export function fitScale(viewport: Size, world: Size = MAP_SIZE): number {
  if (viewport.width <= 0 || viewport.height <= 0) return 0
  return Math.min(viewport.width / world.width, viewport.height / world.height)
}

/** Konva rotation for a camera's view wedge: headings are 0 = up, clockwise; wedges start at 3 o'clock. */
export function wedgeRotation(headingDeg: number, fovDeg = CAMERA_FOV_DEG): number {
  return headingDeg - 90 - fovDeg / 2
}

/** Puts a label right of its marker, or left of it where the right side would run off the map. */
export function labelSide(
  markerX: number,
  offset: number,
  width: number,
  world: Size = MAP_SIZE,
): { x: number; align: 'left' | 'right' } {
  return markerX + offset + width <= world.width
    ? { x: markerX + offset, align: 'left' }
    : { x: markerX - offset - width, align: 'right' }
}

/** Moves both ends of a line inwards, so it stops at the edge of the markers it joins. */
export function trimLine([x1, y1, x2, y2]: LinePoints, startBy: number, endBy: number): LinePoints {
  const length = Math.hypot(x2 - x1, y2 - y1)
  if (length <= startBy + endBy) return [x1, y1, x2, y2]
  const [ux, uy] = [(x2 - x1) / length, (y2 - y1) / length]
  return [x1 + ux * startBy, y1 + uy * startBy, x2 - ux * endBy, y2 - uy * endBy]
}

/** Turns an API layout into plain shapes in world coordinates, ready for the canvas. */
export function toMapShapes(layout: Layout): MapShapes {
  const nodesById = new Map(layout.nodes.map((node) => [node.id, node]))
  return {
    zones: layout.zones.map((zone) => ({
      id: zone.id,
      name: zone.name,
      kind: zone.kind,
      points: zone.polygon.flat(),
      labelAt: {
        x: Math.min(...zone.polygon.map(([x]) => x)) + ZONE_LABEL_INSET,
        y: Math.min(...zone.polygon.map(([, y]) => y)) + ZONE_LABEL_INSET,
      },
    })),
    links: layout.links.flatMap((link) => {
      const from = nodesById.get(link.from_node_id)
      const to = nodesById.get(link.to_node_id)
      if (!from || !to) return []
      const points: LinePoints = [from.x, from.y, to.x, to.y]
      return [{ id: link.id, points, oneWay: !link.bidirectional }]
    }),
    nodes: layout.nodes.map((node) => ({
      id: node.id,
      code: node.code,
      kind: node.kind,
      x: node.x,
      y: node.y,
      offline: node.status === 'offline',
      wedgeRotation: wedgeRotation(node.heading_deg),
    })),
  }
}

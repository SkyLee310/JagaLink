import type { Alert, Layout, LayoutNode, LayoutZone } from '../../api/types'

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

export interface Point {
  x: number
  y: number
}

/** An anonymous path (F3) to draw: the nodes it passed through in order, labelled at its head. */
export interface MapPath {
  id: string
  label: string
  nodeIds: string[]
  /** Still being followed. A closed path is drawn faint and without its label. */
  active: boolean
}

/** An open alert (F6): a ring at its node, and a dashed arrow to the camera to check next (F5). */
export interface MapAlert {
  id: string
  nodeId: string
  nextNodeId: string | null
  severity: Alert['severity']
}

export interface HeadLabel extends Point {
  id: string
  text: string
  /** How many labels of other paths already sit at this node: the label goes above them. */
  stack: number
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

/**
 * A path's points through the centres of its nodes, in order, ending `endBy` short of the last
 * node so an arrowhead shows beside its marker. Nodes missing from the layout are skipped.
 */
export function pathPoints(
  nodeIds: readonly string[],
  nodes: ReadonlyMap<string, Point>,
  endBy = 0,
): number[] {
  const points = nodeIds.flatMap((id) => {
    const node = nodes.get(id)
    return node ? [node.x, node.y] : []
  })
  if (points.length < 4) return points
  const last = points.slice(-4) as LinePoints
  return [...points.slice(0, -2), ...trimLine(last, 0, endBy).slice(2)]
}

/** A label at the head of each active path; labels of paths that end at one node stack up. */
export function headLabels(
  paths: readonly MapPath[],
  nodes: ReadonlyMap<string, Point>,
): HeadLabel[] {
  const stacks = new Map<string, number>()
  return paths.flatMap((path) => {
    const headId = path.nodeIds.findLast((id) => nodes.has(id))
    const head = headId === undefined ? undefined : nodes.get(headId)
    if (!path.active || headId === undefined || !head) return []
    const stack = stacks.get(headId) ?? 0
    stacks.set(headId, stack + 1)
    return [{ id: path.id, text: path.label, x: head.x, y: head.y, stack }]
  })
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

import type { Layout, LayoutLink, LayoutNode } from '../../api/types'

/** A small layout for editor tests: two lane cameras, a street camera, and two links. */
export function testLayout(): Layout {
  return {
    community: {
      id: 'c1',
      code: 'taman-ujian',
      name: 'Taman Ujian',
      map_image_url: null,
      scale_m_per_px: 0.25,
      timezone: 'Asia/Kuala_Lumpur',
    },
    zones: [
      { id: 'z-lane', code: 'z-lane', name: 'Lane', kind: 'lane', polygon: square(0, 0, 400) },
      { id: 'z-street', code: 'z-street', name: 'Street', kind: 'street', polygon: square(400, 0, 400) },
    ],
    nodes: [
      testNode('a', 100, 100, 'z-lane'),
      testNode('b', 220, 100, 'z-lane'),
      testNode('c', 500, 100, 'z-street'),
    ],
    links: [testLink('ab', 'a', 'b', true), testLink('cb', 'c', 'b', false)],
  }
}

export function testNode(id: string, x: number, y: number, zone: string | null): LayoutNode {
  return {
    id,
    code: `c-${id}`,
    kind: 'camera',
    name: `Camera ${id}`,
    x,
    y,
    heading_deg: 90,
    status: 'online',
    zone_id: zone,
  }
}

export function testLink(id: string, from: string, to: string, twoWay: boolean): LayoutLink {
  return {
    id,
    from_node_id: from,
    to_node_id: to,
    travel_min_s: 21,
    travel_max_s: 25,
    bidirectional: twoWay,
    distance_m: 30,
  }
}

function square(x: number, y: number, size: number): [number, number][] {
  return [
    [x, y],
    [x + size, y],
    [x + size, y + size],
    [x, y + size],
  ]
}

import { describe, expect, it } from 'vitest'
import type { Layout, LayoutLink, LayoutNode } from '../../api/types'
import {
  fitScale,
  labelSide,
  MAP_SIZE,
  toMapShapes,
  trimLine,
  wedgeRotation,
} from './mapShapes'

function node(id: string, x: number, y: number, extra: Partial<LayoutNode> = {}): LayoutNode {
  const base = { code: id, kind: 'camera', name: id, heading_deg: 90, status: 'online' } as const
  return { ...base, id, x, y, zone_id: null, ...extra }
}

function link(id: string, from: string, to: string, bidirectional: boolean): LayoutLink {
  const travel = { travel_min_s: 21, travel_max_s: 25 }
  return { id, from_node_id: from, to_node_id: to, bidirectional, distance_m: null, ...travel }
}

const LAYOUT: Layout = {
  community: {
    id: 'c1',
    code: 'taman-ujian',
    name: 'Taman Ujian',
    map_image_url: null,
    scale_m_per_px: 0.25,
    timezone: 'Asia/Kuala_Lumpur',
  },
  zones: [
    {
      id: 'z1',
      code: 'z-gate',
      name: 'Main gate',
      kind: 'gate',
      polygon: [
        [40, 340],
        [160, 340],
        [160, 460],
        [40, 460],
      ],
    },
  ],
  nodes: [
    node('gate', 90, 380),
    node('main', 320, 400, { heading_deg: 0 }),
    node('fence', 1180, 400, { kind: 'sensor', status: 'offline' }),
  ],
  links: [
    link('in', 'gate', 'main', false),
    link('road', 'main', 'fence', true),
    link('dangling', 'main', 'deleted-node', true),
  ],
}

describe('fitScale', () => {
  it('fits 1200×800 into a 375 px phone', () => {
    const scale = fitScale({ width: 375, height: 640 }, MAP_SIZE)
    expect(MAP_SIZE.width * scale).toBe(375)
    expect(MAP_SIZE.height * scale).toBeLessThanOrEqual(640)
  })

  it('fits a short laptop window by its height', () => {
    expect(fitScale({ width: 1366, height: 600 }, MAP_SIZE)).toBe(0.75)
  })

  it('is 0 until the viewport has a size', () => {
    expect(fitScale({ width: 0, height: 0 })).toBe(0)
  })
})

describe('wedgeRotation', () => {
  it.each([
    [0, -120],
    [90, -30],
    [180, 60],
    [270, 150],
  ])('turns heading %i° into Konva rotation %i°', (heading, rotation) => {
    expect(wedgeRotation(heading, 60)).toBe(rotation)
  })
})

describe('labelSide', () => {
  it('puts a label right of its marker', () => {
    expect(labelSide(90, 10, 60)).toEqual({ x: 100, align: 'left' })
  })

  it('flips a label left at the right edge of the map', () => {
    expect(labelSide(1180, 10, 60)).toEqual({ x: 1110, align: 'right' })
  })
})

describe('trimLine', () => {
  it('pulls both ends inwards along the line', () => {
    expect(trimLine([0, 0, 100, 0], 10, 20)).toEqual([10, 0, 80, 0])
  })

  it('leaves a line shorter than the trim alone', () => {
    expect(trimLine([0, 0, 10, 0], 8, 8)).toEqual([0, 0, 10, 0])
  })
})

describe('toMapShapes', () => {
  const shapes = toMapShapes(LAYOUT)

  it('draws links between node positions and marks one-way links', () => {
    expect(shapes.links).toEqual([
      { id: 'in', points: [90, 380, 320, 400], oneWay: true },
      { id: 'road', points: [320, 400, 1180, 400], oneWay: false },
    ])
  })

  it('flattens zone polygons and labels them inside the top-left corner', () => {
    expect(shapes.zones[0].points).toEqual([40, 340, 160, 340, 160, 460, 40, 460])
    expect(shapes.zones[0].labelAt).toEqual({ x: 46, y: 346 })
  })

  it('keeps kind, heading and status for each node', () => {
    expect(shapes.nodes.map(({ id, kind, offline, wedgeRotation }) => [id, kind, offline, wedgeRotation]))
      .toEqual([
        ['gate', 'camera', false, -30],
        ['main', 'camera', false, -120],
        ['fence', 'sensor', true, -30],
      ])
  })
})

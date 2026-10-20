import { useMemo, useRef } from 'react'
import { Arrow, Circle, Image, Label, Layer, Line, Rect, Stage, Tag, Text, Wedge } from 'react-konva'
import type { Layout } from '../../api/types'
import { useElementSize, useImage } from './hooks'
import {
  CAMERA_FOV_DEG,
  fitScale,
  headLabels,
  labelSide,
  MAP_SIZE,
  type MapAlert,
  type MapPath,
  type NodeShape,
  pathPoints,
  toMapShapes,
  trimLine,
} from './mapShapes'
import { ALERT_COLORS, COLORS, LABEL_MIN_SCALE, LABEL_WIDTH, ZONE_COLORS } from './mapTheme'

const SEVERITY_ORDER: Record<MapAlert['severity'], number> = { low: 0, medium: 1, high: 2 }

/** Nodes to light up on the map, by node ID. */
export interface MapHighlights {
  /** An object is in view of this camera or sensor. */
  occupied: ReadonlySet<string>
  /** An event from this node has just arrived. */
  flashing: ReadonlySet<string>
}

interface CommunityMapProps {
  layout: Layout
  highlights?: MapHighlights
  /** Anonymous paths (F3), drawn along the links with their ID at the head. */
  paths?: readonly MapPath[]
  /** Open alerts (F6), each ringed in its severity colour with an arrow to its next camera. */
  alerts?: readonly MapAlert[]
}

/** Read-only plan of one community: background, zones, links, cameras and sensors (F1 view). */
export function CommunityMap({ layout, highlights, paths = [], alerts = [] }: CommunityMapProps) {
  const frameRef = useRef<HTMLDivElement>(null)
  const scale = fitScale(useElementSize(frameRef))
  const background = useImage(layout.community.map_image_url)
  const shapes = useMemo(() => toMapShapes(layout), [layout])
  const nodesById = useMemo(() => new Map(shapes.nodes.map((node) => [node.id, node])), [shapes])

  // Markers, lines and text keep a readable size on screen at any scale.
  const onScreen = (px: number) => px / scale
  const radius = Math.max(7, onScreen(5))
  const showLabels = scale >= LABEL_MIN_SCALE
  // Closed paths first, so the paths still being followed draw over them.
  const pathLines = [...paths]
    .sort((a, b) => Number(a.active) - Number(b.active))
    .map((path) => ({ ...path, points: pathPoints(path.nodeIds, nodesById, radius + onScreen(2)) }))
    .filter((path) => path.points.length >= 4)
  // The most severe alert draws last, on top.
  const alertMarks = [...alerts]
    .sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity])
    .flatMap((alert) => {
      const node = nodesById.get(alert.nodeId)
      const next = alert.nextNodeId ? nodesById.get(alert.nextNodeId) : undefined
      return node ? [{ id: alert.id, color: ALERT_COLORS[alert.severity], node, next }] : []
    })

  return (
    <div
      ref={frameRef}
      role="img"
      aria-label={`Map of ${layout.community.name}`}
      className="flex h-full w-full items-start justify-center overflow-hidden"
    >
      {scale > 0 && (
        <Stage
          width={MAP_SIZE.width * scale}
          height={MAP_SIZE.height * scale}
          scaleX={scale}
          scaleY={scale}
          listening={false}
        >
          <Layer listening={false}>
            {background && <Image image={background} {...MAP_SIZE} />}
            {shapes.zones.map((zone) => (
              <Line
                key={zone.id}
                points={zone.points}
                closed
                stroke={ZONE_COLORS[zone.kind]}
                strokeWidth={onScreen(1)}
                dash={[onScreen(6), onScreen(4)]}
                opacity={0.45}
              />
            ))}
            {showLabels &&
              shapes.zones.map((zone) => (
                <Text
                  key={`label-${zone.id}`}
                  {...zone.labelAt}
                  text={zone.name.toUpperCase()}
                  fontSize={onScreen(10)}
                  letterSpacing={onScreen(1)}
                  fill={ZONE_COLORS[zone.kind]}
                  opacity={0.8}
                />
              ))}
            {shapes.links.map((link) =>
              link.oneWay ? (
                <Arrow
                  key={link.id}
                  points={trimLine(link.points, radius + onScreen(2), radius + onScreen(3))}
                  stroke={COLORS.link}
                  fill={COLORS.link}
                  strokeWidth={onScreen(1.5)}
                  pointerLength={onScreen(8)}
                  pointerWidth={onScreen(7)}
                  opacity={0.8}
                />
              ) : (
                <Line
                  key={link.id}
                  points={trimLine(link.points, radius, radius)}
                  stroke={COLORS.link}
                  strokeWidth={onScreen(1.5)}
                  opacity={0.6}
                />
              ),
            )}
            {pathLines.map((path) => (
              <Arrow
                key={`path-${path.id}`}
                points={path.points}
                stroke={COLORS.path}
                fill={COLORS.path}
                strokeWidth={onScreen(path.active ? 3 : 2)}
                pointerLength={onScreen(9)}
                pointerWidth={onScreen(9)}
                lineCap="round"
                lineJoin="round"
                opacity={path.active ? 0.95 : 0.45}
              />
            ))}
            {highlights &&
              shapes.nodes.map((node) => (
                <NodeHighlight
                  key={`highlight-${node.id}`}
                  node={node}
                  radius={radius}
                  occupied={highlights.occupied.has(node.id)}
                  flashing={highlights.flashing.has(node.id)}
                />
              ))}
            {alertMarks.map((mark) => (
              <AlertMark key={`alert-${mark.id}`} {...mark} radius={radius} unit={onScreen(1)} />
            ))}
            {shapes.nodes.map((node) => (
              <NodeMarker key={node.id} node={node} radius={radius} />
            ))}
            {showLabels &&
              shapes.nodes.map((node) => (
                <Text
                  key={`label-${node.id}`}
                  {...labelSide(node.x, radius + onScreen(3), onScreen(LABEL_WIDTH))}
                  y={node.y - onScreen(6)}
                  width={onScreen(LABEL_WIDTH)}
                  wrap="none"
                  text={node.code}
                  fontSize={onScreen(11)}
                  fill={COLORS.label}
                />
              ))}
            {headLabels(paths, nodesById).map((label) => (
              <Label
                key={`path-label-${label.id}`}
                x={label.x}
                y={label.y - radius - onScreen(2) - label.stack * onScreen(24)}
              >
                <Tag
                  fill={COLORS.path}
                  cornerRadius={onScreen(3)}
                  pointerDirection="down"
                  pointerWidth={onScreen(8)}
                  pointerHeight={onScreen(5)}
                />
                <Text
                  text={label.text}
                  fontFamily="monospace"
                  fontSize={onScreen(11)}
                  padding={onScreen(3)}
                  fill={COLORS.outline}
                />
              </Label>
            ))}
          </Layer>
        </Stage>
      )}
    </div>
  )
}

/** A halo behind a node: a ring while it has an object in view, a glow when an event arrives. */
function NodeHighlight({
  node,
  radius,
  occupied,
  flashing,
}: {
  node: NodeShape
  radius: number
  occupied: boolean
  flashing: boolean
}) {
  return (
    <>
      {flashing && (
        <Circle x={node.x} y={node.y} radius={radius * 2.8} fill={COLORS.flash} opacity={0.35} />
      )}
      {occupied && (
        <Circle
          x={node.x}
          y={node.y}
          radius={radius * 1.9}
          stroke={COLORS.occupied}
          strokeWidth={radius / 2.5}
          opacity={0.9}
        />
      )}
    </>
  )
}

/**
 * An open alert: a ring in its severity colour at the node that raised it, and a dashed arrow to
 * a dashed ring at the camera to check next (F5). `unit` is one screen pixel in map units.
 */
function AlertMark({
  color,
  node,
  next,
  radius,
  unit,
}: {
  color: string
  node: NodeShape
  next?: NodeShape
  radius: number
  unit: number
}) {
  const ring = radius * 2.3
  return (
    <>
      {next && (
        <>
          <Arrow
            points={trimLine([node.x, node.y, next.x, next.y], ring + unit * 2, ring + unit * 3)}
            stroke={color}
            fill={color}
            strokeWidth={unit * 2.5}
            dash={[unit * 7, unit * 5]}
            pointerLength={unit * 10}
            pointerWidth={unit * 10}
          />
          <Circle
            x={next.x}
            y={next.y}
            radius={ring}
            stroke={COLORS.next}
            strokeWidth={unit * 2.5}
            dash={[unit * 5, unit * 4]}
          />
        </>
      )}
      <Circle x={node.x} y={node.y} radius={ring} fill={color} opacity={0.2} />
      <Circle x={node.x} y={node.y} radius={ring} stroke={color} strokeWidth={unit * 3.5} />
    </>
  )
}

/** A camera is a dot with its view wedge; a sensor is a square. Offline nodes turn grey. */
function NodeMarker({ node, radius }: { node: NodeShape; radius: number }) {
  const color = node.offline ? COLORS.offline : COLORS[node.kind]
  if (node.kind === 'sensor') {
    return (
      <Rect
        x={node.x - radius}
        y={node.y - radius}
        width={radius * 2}
        height={radius * 2}
        cornerRadius={radius / 3}
        fill={color}
        stroke={COLORS.outline}
        strokeWidth={radius / 4}
      />
    )
  }
  return (
    <>
      <Wedge
        x={node.x}
        y={node.y}
        radius={radius * 5}
        angle={CAMERA_FOV_DEG}
        rotation={node.wedgeRotation}
        fill={color}
        opacity={0.25}
      />
      <Circle
        x={node.x}
        y={node.y}
        radius={radius}
        fill={color}
        stroke={COLORS.outline}
        strokeWidth={radius / 4}
      />
    </>
  )
}

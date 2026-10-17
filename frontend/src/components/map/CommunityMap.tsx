import { type RefObject, useEffect, useMemo, useRef, useState } from 'react'
import { Arrow, Circle, Image, Layer, Line, Rect, Stage, Text, Wedge } from 'react-konva'
import type { Layout } from '../../api/types'
import {
  CAMERA_FOV_DEG,
  fitScale,
  labelSide,
  MAP_SIZE,
  type NodeShape,
  type Size,
  toMapShapes,
  trimLine,
  type ZoneShape,
} from './mapShapes'

const COLORS = {
  camera: '#38bdf8', // sky-400
  sensor: '#fbbf24', // amber-400
  offline: '#64748b', // slate-500
  link: '#94a3b8', // slate-400
  label: '#e2e8f0', // slate-200
  outline: '#020617', // slate-950
}

const ZONE_COLORS: Record<ZoneShape['kind'], string> = {
  gate: '#f472b6', // pink-400
  street: '#a78bfa', // violet-400
  lane: '#34d399', // emerald-400
}

/** Text labels appear once the map is drawn at 60 % of its full size or more. */
const LABEL_MIN_SCALE = 0.6

/** On-screen width kept for a node code label, in pixels. */
const LABEL_WIDTH = 64

/** Read-only plan of one community: background, zones, links, cameras and sensors (F1 view). */
export function CommunityMap({ layout }: { layout: Layout }) {
  const frameRef = useRef<HTMLDivElement>(null)
  const scale = fitScale(useElementSize(frameRef))
  const background = useImage(layout.community.map_image_url)
  const shapes = useMemo(() => toMapShapes(layout), [layout])

  // Markers, lines and text keep a readable size on screen at any scale.
  const onScreen = (px: number) => px / scale
  const radius = Math.max(7, onScreen(5))
  const showLabels = scale >= LABEL_MIN_SCALE

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
          </Layer>
        </Stage>
      )}
    </div>
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

function useElementSize(ref: RefObject<HTMLElement | null>): Size {
  const [size, setSize] = useState<Size>({ width: 0, height: 0 })
  useEffect(() => {
    const element = ref.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => {
      setSize({ width: entry.contentRect.width, height: entry.contentRect.height })
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [ref])
  return size
}

function useImage(src: string | null): HTMLImageElement | null {
  const [image, setImage] = useState<HTMLImageElement | null>(null)
  useEffect(() => {
    if (!src) return
    const element = new window.Image()
    element.onload = () => setImage(element)
    element.src = src
    return () => {
      element.onload = null
    }
  }, [src])
  return src ? image : null
}

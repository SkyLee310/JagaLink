import type Konva from 'konva'
import type { KonvaEventObject } from 'konva/lib/Node'
import { type Dispatch, useMemo, useRef, useState } from 'react'
import { Arrow, Circle, Group, Image, Layer, Line, Rect, Stage, Text, Wedge } from 'react-konva'
import type { LayoutNode } from '../../api/types'
import { useElementSize, useImage } from '../../components/map/hooks'
import {
  CAMERA_FOV_DEG,
  fitScale,
  labelSide,
  MAP_SIZE,
  type NodeShape,
  toMapShapes,
  trimLine,
} from '../../components/map/mapShapes'
import { COLORS, LABEL_MIN_SCALE, LABEL_WIDTH, ZONE_COLORS } from '../../components/map/mapTheme'
import { type EditorAction, type EditorState, headingTowards, type Tool } from './editorState'

const CURSORS: Record<Tool, string> = {
  select: 'cursor-default',
  camera: 'cursor-crosshair',
  sensor: 'cursor-crosshair',
  link: 'cursor-pointer',
}

type Point = { x: number; y: number }
type PointerEvent = KonvaEventObject<MouseEvent | TouchEvent>

interface EditorCanvasProps {
  state: EditorState
  dispatch: Dispatch<EditorAction>
  newId: () => string
}

/** The F1 editing canvas: place, drag, turn and link nodes over the read-only zones (D-64). */
export function EditorCanvas({ state, dispatch, newId }: EditorCanvasProps) {
  const frameRef = useRef<HTMLDivElement>(null)
  const scale = fitScale(useElementSize(frameRef))
  const background = useImage(state.community.map_image_url)
  const [pointer, setPointer] = useState<Point | null>(null)
  const { community, zones, draft, tool, selection, linkStart } = state
  const shapes = useMemo(
    () => toMapShapes({ community, zones, nodes: draft.nodes, links: draft.links }),
    [community, zones, draft],
  )
  const nodesById = useMemo(() => new Map(draft.nodes.map((node) => [node.id, node])), [draft])

  // Markers, lines and text keep a readable size on screen at any scale.
  const onScreen = (px: number) => px / scale
  const radius = Math.max(7, onScreen(6))
  const showLabels = scale >= LABEL_MIN_SCALE
  const selectedNode = selection?.kind === 'node' ? nodesById.get(selection.id) : undefined
  const startNode = linkStart ? nodesById.get(linkStart) : undefined

  const toWorld = (stage: Konva.Stage | null): Point | null => {
    const point = stage?.getPointerPosition()
    return point ? { x: point.x / scale, y: point.y / scale } : null
  }

  const onStageClick = (event: PointerEvent) => {
    const stage = event.target.getStage()
    if (event.target !== stage) return // a node or a link took the click
    const at = toWorld(stage)
    if ((tool === 'camera' || tool === 'sensor') && at) {
      dispatch({ type: 'addNode', id: newId(), kind: tool, ...at })
    } else {
      dispatch({ type: 'cancel' })
    }
  }

  const onNodeClick = (node: NodeShape) => () => {
    if (tool === 'link') dispatch({ type: 'pickLinkEnd', nodeId: node.id, linkId: newId() })
    else dispatch({ type: 'select', selection: { kind: 'node', id: node.id } })
  }

  const keepOnMap = (position: Point): Point => ({
    x: Math.min(MAP_SIZE.width * scale, Math.max(0, position.x)),
    y: Math.min(MAP_SIZE.height * scale, Math.max(0, position.y)),
  })

  return (
    <div
      ref={frameRef}
      role="application"
      aria-label={`Layout editor for ${community.name}`}
      className={`flex h-full w-full items-start justify-center overflow-hidden ${CURSORS[tool]}`}
    >
      {scale > 0 && (
        <Stage
          width={MAP_SIZE.width * scale}
          height={MAP_SIZE.height * scale}
          scaleX={scale}
          scaleY={scale}
          onClick={onStageClick}
          onTap={onStageClick}
          onMouseMove={(event) => linkStart && setPointer(toWorld(event.target.getStage()))}
          onMouseLeave={() => setPointer(null)}
        >
          <Layer listening={false}>
            <Rect {...MAP_SIZE} fill="#0f172a" />
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
          </Layer>

          <Layer>
            {shapes.links.map((link) => {
              const selected = selection?.kind === 'link' && selection.id === link.id
              const color = selected ? COLORS.selected : COLORS.link
              const common = {
                stroke: color,
                strokeWidth: onScreen(selected ? 3 : 1.5),
                hitStrokeWidth: onScreen(14),
                opacity: selected ? 1 : 0.7,
                // Only the select tool picks links, so a camera can go right on a street line.
                listening: tool === 'select',
                onClick: () => dispatch({ type: 'select', selection: { kind: 'link', id: link.id } }),
                onTap: () => dispatch({ type: 'select', selection: { kind: 'link', id: link.id } }),
              }
              return link.oneWay ? (
                <Arrow
                  key={link.id}
                  {...common}
                  points={trimLine(link.points, radius + onScreen(2), radius + onScreen(3))}
                  fill={color}
                  pointerLength={onScreen(8)}
                  pointerWidth={onScreen(7)}
                />
              ) : (
                <Line key={link.id} {...common} points={trimLine(link.points, radius, radius)} />
              )
            })}

            {startNode && pointer && (
              <Line
                points={[startNode.x, startNode.y, pointer.x, pointer.y]}
                stroke={COLORS.pending}
                strokeWidth={onScreen(2)}
                dash={[onScreen(6), onScreen(4)]}
                listening={false}
              />
            )}

            {shapes.nodes.map((node) => (
              <Group
                key={node.id}
                x={node.x}
                y={node.y}
                draggable={tool === 'select'}
                dragBoundFunc={keepOnMap}
                onDragStart={() =>
                  dispatch({ type: 'select', selection: { kind: 'node', id: node.id } })
                }
                onDragMove={(event) =>
                  dispatch({ type: 'moveNode', id: node.id, x: event.target.x(), y: event.target.y() })
                }
                onDragEnd={(event) =>
                  dispatch({
                    type: 'moveNode',
                    id: node.id,
                    x: event.target.x(),
                    y: event.target.y(),
                    dropped: true,
                  })
                }
                onClick={onNodeClick(node)}
                onTap={onNodeClick(node)}
                onMouseEnter={(event) => setCursor(event, tool === 'select' ? 'move' : 'pointer')}
                onMouseLeave={(event) => setCursor(event, '')}
              >
                <NodeMarker
                  node={node}
                  radius={radius}
                  ring={
                    node.id === linkStart
                      ? COLORS.pending
                      : node.id === selectedNode?.id
                        ? COLORS.selected
                        : null
                  }
                />
              </Group>
            ))}

            {selectedNode?.kind === 'camera' && tool === 'select' && (
              <HeadingHandle
                node={selectedNode}
                reach={radius * 4}
                radius={radius * 0.75}
                onTurn={(heading) =>
                  dispatch({
                    type: 'updateNode',
                    id: selectedNode.id,
                    changes: { heading_deg: heading },
                  })
                }
              />
            )}
          </Layer>

          <Layer listening={false}>
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

/** A camera is a dot with its view wedge; a sensor is a square. Drawn around (0, 0). */
function NodeMarker({ node, radius, ring }: { node: NodeShape; radius: number; ring: string | null }) {
  const color = node.offline ? COLORS.offline : COLORS[node.kind]
  return (
    <>
      {node.kind === 'camera' && (
        <Wedge
          radius={radius * 5}
          angle={CAMERA_FOV_DEG}
          rotation={node.wedgeRotation}
          fill={color}
          opacity={0.25}
          listening={false}
        />
      )}
      {ring && (
        <Circle
          radius={radius * 1.7}
          stroke={ring}
          strokeWidth={radius / 3}
          dash={ring === COLORS.pending ? [radius / 2, radius / 3] : undefined}
          listening={false}
        />
      )}
      {node.kind === 'sensor' ? (
        <Rect
          x={-radius}
          y={-radius}
          width={radius * 2}
          height={radius * 2}
          cornerRadius={radius / 3}
          fill={color}
          stroke={COLORS.outline}
          strokeWidth={radius / 4}
        />
      ) : (
        <Circle radius={radius} fill={color} stroke={COLORS.outline} strokeWidth={radius / 4} />
      )}
    </>
  )
}

/** A handle in front of the selected camera; dragging it around turns the camera. */
function HeadingHandle(props: {
  node: LayoutNode
  reach: number
  radius: number
  onTurn: (heading: number) => void
}) {
  const { node, reach, radius, onTurn } = props
  const angle = (node.heading_deg * Math.PI) / 180
  const x = node.x + Math.sin(angle) * reach
  const y = node.y - Math.cos(angle) * reach
  return (
    <>
      <Line
        points={[node.x, node.y, x, y]}
        stroke={COLORS.selected}
        strokeWidth={radius / 4}
        dash={[radius / 2, radius / 2]}
        listening={false}
      />
      <Circle
        x={x}
        y={y}
        radius={radius}
        fill={COLORS.selected}
        stroke={COLORS.outline}
        strokeWidth={radius / 4}
        draggable
        onDragMove={(event) =>
          onTurn(headingTowards(node, { x: event.target.x(), y: event.target.y() }))
        }
        onMouseEnter={(event) => setCursor(event, 'grab')}
        onMouseLeave={(event) => setCursor(event, '')}
      />
    </>
  )
}

function setCursor(event: KonvaEventObject<MouseEvent>, cursor: string) {
  const container = event.target.getStage()?.container()
  if (container) container.style.cursor = cursor
}

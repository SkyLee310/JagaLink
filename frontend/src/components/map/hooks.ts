import { type RefObject, useEffect, useState } from 'react'
import type { Size } from './mapShapes'

/** The element's content size, kept current as it resizes. */
export function useElementSize(ref: RefObject<HTMLElement | null>): Size {
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

/** The loaded image, or null while it loads or when there is no source. */
export function useImage(src: string | null): HTMLImageElement | null {
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

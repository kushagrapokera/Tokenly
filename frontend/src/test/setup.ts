import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

/**
 * Give Recharts a size to draw into.
 *
 * `ResponsiveContainer` measures its parent with a `ResizeObserver` and renders nothing
 * when that measurement is zero — which is exactly what jsdom reports. This stub
 * reports a fixed viewport instead, so a chart renders real geometry and the tests can
 * assert on it. It is test-only scaffolding: no component reads these dimensions.
 */
const CHART_WIDTH = 800
const CHART_HEIGHT = 400

class ResizeObserverStub {
  private readonly callback: ResizeObserverCallback

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback
  }

  observe(target: Element): void {
    this.callback([makeEntry(target)], this as unknown as ResizeObserver)
  }

  unobserve(): void {}
  disconnect(): void {}
}

function makeEntry(target: Element): ResizeObserverEntry {
  const box = {
    width: CHART_WIDTH,
    height: CHART_HEIGHT,
    top: 0,
    left: 0,
    bottom: CHART_HEIGHT,
    right: CHART_WIDTH,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  }
  return {
    target,
    contentRect: box,
    borderBoxSize: [],
    contentBoxSize: [],
    devicePixelContentBoxSize: [],
  } as unknown as ResizeObserverEntry
}

globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver

Element.prototype.getBoundingClientRect = function getBoundingClientRect(): DOMRect {
  return {
    width: CHART_WIDTH,
    height: CHART_HEIGHT,
    top: 0,
    left: 0,
    bottom: CHART_HEIGHT,
    right: CHART_WIDTH,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  } as DOMRect
}

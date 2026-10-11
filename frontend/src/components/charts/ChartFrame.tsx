/**
 * The frame every chart sits in.
 *
 * It owns the plot height and the empty state so no chart has to decide what "no usage"
 * looks like. An empty period is a normal state here, not a failure: a fresh install
 * legitimately has no usage yet, and a chart with no data should say so calmly.
 */

import type { ReactNode } from 'react'

import { StateMessage } from '../ui'

export function ChartFrame({
  height,
  isEmpty,
  emptyMessage,
  children,
}: {
  height: number
  isEmpty: boolean
  emptyMessage: string
  children: ReactNode
}) {
  if (isEmpty) {
    return <StateMessage kind="empty" message={emptyMessage} />
  }

  return (
    <figure className="m-0">
      <div style={{ height }}>{children}</div>
    </figure>
  )
}

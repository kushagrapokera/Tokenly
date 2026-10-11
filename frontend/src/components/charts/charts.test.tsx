import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { InputOutputChart } from './InputOutputChart'
import { TimelineChart } from './TimelineChart'
import { makeTimeline } from '../../test/fixtures'

describe('TimelineChart', () => {
  it('draws a line for daily usage', () => {
    const timeline = makeTimeline([
      { label: '2026-10-10', total: 100 },
      { label: '2026-10-11', total: 250 },
    ])

    const { container } = render(<TimelineChart timeline={timeline} kind="daily" />)

    expect(container.querySelector('.recharts-line')).not.toBeNull()
  })

  it('draws bars for monthly usage', () => {
    const timeline = makeTimeline(
      [
        { label: '2026-09', total: 100 },
        { label: '2026-10', total: 250 },
      ],
      { granularity: 'month' },
    )

    const { container } = render(<TimelineChart timeline={timeline} kind="monthly" />)

    expect(container.querySelector('.recharts-bar-rectangle')).not.toBeNull()
    expect(container.querySelector('.recharts-line')).toBeNull()
  })

  it('keeps buckets with no usage so a gap stays visible', () => {
    const timeline = makeTimeline([
      { label: '2026-10-09', total: 100 },
      { label: '2026-10-10', total: 0 },
      { label: '2026-10-11', total: 250 },
    ])

    const { container } = render(<TimelineChart timeline={timeline} kind="daily" />)

    // One dot per bucket, including the empty one in the middle.
    expect(container.querySelectorAll('.recharts-line-dots circle')).toHaveLength(3)
  })

  it('shows an empty state when nothing was used', () => {
    const timeline = makeTimeline([{ label: '2026-10-10', total: 0 }])

    render(<TimelineChart timeline={timeline} kind="daily" />)

    expect(screen.getByText('No usage recorded in this period.')).toBeInTheDocument()
  })

  it('renders no bars when every bucket is empty', () => {
    const timeline = makeTimeline([{ label: '2026-09', total: 0 }], { granularity: 'month' })

    const { container } = render(<TimelineChart timeline={timeline} kind="monthly" />)

    expect(container.querySelector('.recharts-bar-rectangle')).toBeNull()
  })
})

describe('InputOutputChart', () => {
  it('plots both series', () => {
    const timeline = makeTimeline([
      { label: '2026-10-10', total: 100, input: 80, output: 20 },
      { label: '2026-10-11', total: 250, input: 200, output: 50 },
    ])

    const { container } = render(<InputOutputChart timeline={timeline} />)

    // Two bars per bucket, one input and one output.
    expect(container.querySelectorAll('.recharts-bar-rectangle')).toHaveLength(4)
  })

  it('shows an empty state when there is no usage', () => {
    render(<InputOutputChart timeline={makeTimeline([{ label: '2026-10-10', total: 0 }])} />)

    expect(screen.getByText('No usage recorded in this period.')).toBeInTheDocument()
  })
})

/**
 * Input versus output over the selected period.
 *
 * A second chart because the model chart answers "which model" and this answers "which
 * direction": output tokens are what actually cost money on most providers, so a user
 * watching cost wants that split over time, not only in aggregate.
 */

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { TimelineResponse } from '../../api/types'
import { formatBucketLabel } from '../../lib/format'
import { ChartLegend } from './ChartLegend'
import {
  axisProps,
  compactTick,
  gridProps,
  integerValue,
  token,
  tooltipProps,
} from './chartTheme'
import { ChartFrame } from './ChartFrame'

export function InputOutputChart({ timeline }: { timeline: TimelineResponse }) {
  const points = timeline.buckets.map((bucket) => ({
    label: formatBucketLabel(bucket.label, timeline.granularity),
    input: bucket.totals.input_tokens,
    output: bucket.totals.output_tokens,
  }))
  const hasUsage = timeline.buckets.some((bucket) => bucket.request_count > 0)
  const inputTotal = sumOf(timeline, 'input_tokens')
  const outputTotal = sumOf(timeline, 'output_tokens')

  return (
    <ChartFrame
      height={260}
      isEmpty={!hasUsage}
      emptyMessage="No usage recorded in this period."
    >
      <ChartLegend
        entries={[
          { key: 'input', label: 'Input', color: token('input'), value: inputTotal },
          { key: 'output', label: 'Output', color: token('output'), value: outputTotal },
        ]}
      />
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid {...gridProps()} />
          <XAxis dataKey="label" {...axisProps()} />
          <YAxis {...axisProps()} tickFormatter={compactTick} width={48} />
          <Tooltip {...tooltipProps()} formatter={integerValue} />
          <Bar
            isAnimationActive={false}
            dataKey="input"
            name="Input"
            stackId="tokens"
            fill={token('input')}
          />
          <Bar
            isAnimationActive={false}
            dataKey="output"
            name="Output"
            stackId="tokens"
            fill={token('output')}
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

function sumOf(timeline: TimelineResponse, key: 'input_tokens' | 'output_tokens'): number {
  return timeline.buckets.reduce((total, bucket) => total + bucket.totals[key], 0)
}

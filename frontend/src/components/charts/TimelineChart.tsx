/**
 * Timeline chart used for daily, monthly, and yearly usage.
 *
 * One component serves all three because they differ only in granularity, and a shared
 * implementation means the axis, tooltip, and empty state cannot drift apart between
 * them. Buckets with no usage are kept rather than dropped: a gap in a usage chart is
 * meaningful, and filtering those points out would draw a straight line across days
 * that simply had none.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { TimelineResponse } from '../../api/types'
import { formatBucketLabel } from '../../lib/format'
import {
  axisProps,
  compactTick,
  gridProps,
  integerValue,
  token,
  tooltipProps,
} from './chartTheme'
import { ChartFrame } from './ChartFrame'

interface Point {
  label: string
  total: number
  input: number
  output: number
}

export function TimelineChart({
  timeline,
  kind,
}: {
  timeline: TimelineResponse
  kind: 'daily' | 'monthly' | 'yearly'
}) {
  const points: Point[] = timeline.buckets.map((bucket) => ({
    label: formatBucketLabel(bucket.label, timeline.granularity),
    total: bucket.totals.total_tokens,
    input: bucket.totals.input_tokens,
    output: bucket.totals.output_tokens,
  }))

  const hasUsage = timeline.buckets.some((bucket) => bucket.request_count > 0)

  return (
    <ChartFrame
      height={260}
      isEmpty={!hasUsage}
      emptyMessage="No usage recorded in this period."
    >
      <ResponsiveContainer width="100%" height="100%">
        {kind === 'daily' ? (
          <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid {...gridProps()} />
            <XAxis dataKey="label" {...axisProps()} />
            <YAxis {...axisProps()} tickFormatter={compactTick} width={48} />
            <Tooltip {...tooltipProps()} formatter={integerValue} />
            <Line
              isAnimationActive={false}
              type="monotone"
              dataKey="total"
              name="Total tokens"
              stroke={token('total')}
              strokeWidth={2}
              dot={{ r: 2, fill: token('total') }}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        ) : (
          <BarChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid {...gridProps()} />
            <XAxis dataKey="label" {...axisProps()} />
            <YAxis {...axisProps()} tickFormatter={compactTick} width={48} />
            <Tooltip {...tooltipProps()} formatter={integerValue} />
            <Bar
              isAnimationActive={false}
              dataKey="total"
              name="Total tokens"
              fill={token('total')}
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        )}
      </ResponsiveContainer>
    </ChartFrame>
  )
}

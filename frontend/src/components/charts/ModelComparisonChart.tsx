/**
 * Input versus output across models.
 *
 * A stacked bar rather than a grouped one: the point of this chart is the split of a
 * whole, so stacking shows each model's total height as well as its composition. The
 * two series keep the same colours as every other chart on the page.
 */

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { ModelBreakdownResponse } from '../../api/types'
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

const MAX_MODELS = 8

interface ModelPoint {
  name: string
  input: number
  output: number
}

export function ModelComparisonChart({ breakdown }: { breakdown: ModelBreakdownResponse }) {
  const models = breakdown.models.slice(0, MAX_MODELS)
  const points: ModelPoint[] = models.map((model) => ({
    name: model.model_id,
    input: model.totals.input_tokens,
    output: model.totals.output_tokens,
  }))
  const hasUsage = models.some((model) => model.totals.total_tokens > 0)

  return (
    <ChartFrame height={280} isEmpty={!hasUsage} emptyMessage="No model usage in this period.">
      <ChartLegend
        entries={[
          {
            key: 'input',
            label: 'Input',
            color: token('input'),
            value: sum(models, 'input_tokens'),
          },
          {
            key: 'output',
            label: 'Output',
            color: token('output'),
            value: sum(models, 'output_tokens'),
          },
        ]}
      />
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid {...gridProps()} />
          <XAxis
            dataKey="name"
            {...axisProps()}
            interval={0}
            angle={-25}
            textAnchor="end"
            height={64}
            tickFormatter={(value: string) => truncate(value, 16)}
          />
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

function sum(
  models: ModelBreakdownResponse['models'],
  key: 'input_tokens' | 'output_tokens',
): number {
  return models.reduce((total, model) => total + model.totals[key], 0)
}

/** Shorten a long model name so the axis stays readable; the tooltip keeps it whole. */
function truncate(value: string, limit: number): string {
  return value.length > limit ? `${value.slice(0, limit - 1)}…` : value
}

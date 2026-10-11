/**
 * Model usage comparison chart, fetched separately from the table beside it.
 *
 * It reads the all-time breakdown rather than the filtered one: a comparison chart whose
 * bars disappear when a single model is selected shows nothing, and the table directly
 * above it is already the filtered view.
 */

import { fetchModels } from '../api/client'
import type { ModelBreakdownResponse } from '../api/types'
import { useAsyncData } from '../hooks/useAsyncData'
import { ModelComparisonChart } from './charts/ModelComparisonChart'
import { Panel, StateMessage } from './ui'

export function ModelComparisonPanel({ timezone }: { timezone: string }) {
  const { state, reload } = useAsyncData<ModelBreakdownResponse>(
    () => fetchModels({ range: 'all_time', timezone }),
    [timezone],
  )

  return (
    <Panel title="Model comparison" subtitle="Input versus output tokens by model">
      {state.status === 'loading' ? <StateMessage kind="loading" /> : null}
      {state.status === 'error' ? (
        <StateMessage kind="error" message={state.error.message} onRetry={reload} />
      ) : null}
      {state.status === 'ready' ? <ModelComparisonChart breakdown={state.data} /> : null}
    </Panel>
  )
}

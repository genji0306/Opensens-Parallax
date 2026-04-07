import { computed, type Ref } from 'vue'
import { useSSE } from '@/composables/useSSE'
import { usePipelineStore } from '@/stores/pipeline'
import type { StageId, StageStatus } from '@/types/pipeline'
import type { SSEEvent } from '@/types/api'

interface PipelineSSEPayload {
  stage?: StageId
  status?: StageStatus
  metric?: string
  result?: Record<string, unknown>
  cost?: { paid: number; free: number; total: number }
}

/**
 * Pipeline-specific SSE composable.
 *
 * Connects to the AIS run stream and pushes stage updates directly into the
 * pipeline Pinia store so every component stays in sync.
 */
export function usePipelineSSE(runId: Ref<string | null>) {
  const pipeline = usePipelineStore()

  const url = computed(() =>
    runId.value ? `/api/research/ais/${runId.value}/stream` : null,
  )

  function handleEvent(event: SSEEvent<PipelineSSEPayload>): void {
    const payload = event.payload ?? event.data
    if (!payload) return

    // Update individual stage info when the backend pushes progress
    if (payload.stage && payload.status) {
      const existing = pipeline.stages[payload.stage]
      if (existing) {
        pipeline.stages[payload.stage] = {
          ...existing,
          status: payload.status,
          metric: payload.metric ?? existing.metric,
        }
      }
    }

    // Merge stage result blob if present
    if (payload.stage && payload.result) {
      pipeline.stageResults[payload.stage] = payload.result
    }

    // Update running cost
    if (payload.cost) {
      pipeline.costEstimate = {
        paid: payload.cost.paid,
        free: payload.cost.free,
        total: payload.cost.total,
      }
    }
  }

  const { data, status, close } = useSSE<PipelineSSEPayload>(url, {
    onEvent: handleEvent,
  })

  return { data, status, close }
}

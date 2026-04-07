import { ref, computed, type Ref } from 'vue'
import { useSSE } from '@/composables/useSSE'
import type { SSEEvent } from '@/types/api'

export interface ReviewEvent {
  type: 'review' | 'revision' | 'score' | 'complete' | 'error'
  round?: number
  reviewer?: string
  content?: string
  score?: number
  scores?: number[]
  message?: string
  timestamp?: string
}

/**
 * Paper Rehabilitation SSE composable.
 *
 * Connects to the paper-lab stream for a given upload and accumulates review
 * events and score updates as rounds progress.
 */
export function usePaperRehabSSE(uploadId: Ref<string | null>) {
  const reviewEvents = ref<ReviewEvent[]>([])
  const currentScores = ref<number[]>([])
  const latestScore = ref<number | null>(null)
  const currentRound = ref(0)
  const isComplete = ref(false)
  const rehabError = ref<string | null>(null)

  const url = computed(() =>
    uploadId.value ? `/api/research/paper-lab/${uploadId.value}/stream` : null,
  )

  function handleEvent(event: SSEEvent<ReviewEvent>): void {
    const payload = event.payload ?? event.data
    if (!payload) return

    reviewEvents.value.push(payload)

    switch (payload.type) {
      case 'review':
      case 'revision':
        if (payload.round != null) {
          currentRound.value = payload.round
        }
        break

      case 'score':
        if (payload.score != null) {
          latestScore.value = payload.score
        }
        if (payload.scores) {
          currentScores.value = payload.scores
        }
        break

      case 'complete':
        isComplete.value = true
        if (payload.scores) {
          currentScores.value = payload.scores
        }
        if (payload.score != null) {
          latestScore.value = payload.score
        }
        break

      case 'error':
        rehabError.value = payload.message ?? 'Unknown paper rehab error'
        break
    }
  }

  const { status, close } = useSSE<ReviewEvent>(url, {
    onEvent: handleEvent,
  })

  function reset(): void {
    close()
    reviewEvents.value = []
    currentScores.value = []
    latestScore.value = null
    currentRound.value = 0
    isComplete.value = false
    rehabError.value = null
  }

  return {
    reviewEvents,
    currentScores,
    latestScore,
    currentRound,
    isComplete,
    rehabError,
    status,
    close,
    reset,
  }
}

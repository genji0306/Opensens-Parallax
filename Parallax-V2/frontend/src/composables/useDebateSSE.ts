import { ref, computed, type Ref } from 'vue'
import { useSSE } from '@/composables/useSSE'
import type { SSEEvent } from '@/types/api'

export interface DebateTurn {
  agent: string
  role?: string
  content: string
  round: number
  stance?: number
  timestamp?: string
}

export interface AgentStance {
  agent: string
  stance: number
  role?: string
}

interface DebateSSEPayload {
  type?: 'turn' | 'round_start' | 'round_end' | 'complete' | 'error'
  agent?: string
  role?: string
  content?: string
  round?: number
  stance?: number
  stances?: AgentStance[]
  timestamp?: string
  message?: string
}

/**
 * Debate-specific SSE composable.
 *
 * Connects to the simulation stream and accumulates transcript turns,
 * tracks the current round, and maintains the latest agent stances.
 */
export function useDebateSSE(simId: Ref<string | null>) {
  const transcript = ref<DebateTurn[]>([])
  const currentRound = ref(0)
  const agentStances = ref<AgentStance[]>([])
  const isComplete = ref(false)
  const debateError = ref<string | null>(null)

  const url = computed(() =>
    simId.value ? `/api/research/simulate/${simId.value}/stream` : null,
  )

  function handleEvent(event: SSEEvent<DebateSSEPayload>): void {
    const payload = event.payload ?? event.data
    if (!payload) return

    switch (payload.type) {
      case 'turn':
        if (payload.agent && payload.content != null) {
          transcript.value.push({
            agent: payload.agent,
            role: payload.role,
            content: payload.content,
            round: payload.round ?? currentRound.value,
            stance: payload.stance,
            timestamp: payload.timestamp,
          })
        }
        if (payload.stance != null && payload.agent) {
          updateStance(payload.agent, payload.stance, payload.role)
        }
        break

      case 'round_start':
        if (payload.round != null) {
          currentRound.value = payload.round
        }
        break

      case 'round_end':
        if (payload.stances) {
          agentStances.value = payload.stances
        }
        break

      case 'complete':
        isComplete.value = true
        if (payload.stances) {
          agentStances.value = payload.stances
        }
        break

      case 'error':
        debateError.value = payload.message ?? 'Unknown debate error'
        break
    }
  }

  function updateStance(agent: string, stance: number, role?: string): void {
    const idx = agentStances.value.findIndex((s) => s.agent === agent)
    if (idx >= 0) {
      agentStances.value[idx] = { agent, stance, role }
    } else {
      agentStances.value.push({ agent, stance, role })
    }
  }

  const { status, close } = useSSE<DebateSSEPayload>(url, {
    onEvent: handleEvent,
  })

  function reset(): void {
    close()
    transcript.value = []
    currentRound.value = 0
    agentStances.value = []
    isComplete.value = false
    debateError.value = null
  }

  return {
    transcript,
    currentRound,
    agentStances,
    isComplete,
    debateError,
    status,
    close,
    reset,
  }
}

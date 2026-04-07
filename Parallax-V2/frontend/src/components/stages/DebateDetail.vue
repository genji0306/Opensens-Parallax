<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import MetricCard from '@/components/shared/MetricCard.vue'
import ProgressBar from '@/components/shared/ProgressBar.vue'
import ActionButton from '@/components/shared/ActionButton.vue'
import { startDebate, getDebateSummary } from '@/api/ais'
import { getTranscript } from '@/api/simulation'
import { usePipelineStore } from '@/stores/pipeline'
import type { DebateSummary } from '@/types/api'

const props = defineProps<{
  result: Record<string, unknown>
  runId?: string
  simulationId?: string
}>()

const pipeline = usePipelineStore()
const starting = ref(false)
const startError = ref<string | null>(null)
const showTranscript = ref(false)

interface Turn {
  agent_name: string
  agent_role?: string
  content: string
  round_num: number
}

const transcript = ref<Turn[]>([])
const loadingTranscript = ref(false)
const summary = ref<DebateSummary | null>(null)
const loadingSummary = ref(false)

const agentCount = computed(() =>
  (props.result.agent_count as number)
  ?? (Array.isArray(props.result.agents) ? props.result.agents.length : 0),
)

const roundCount = computed(() =>
  (props.result.round_count as number)
  ?? (props.result.rounds as number)
  ?? (props.result.rounds_completed as number)
  ?? 0,
)

const totalWords = computed(() => {
  if (transcript.value.length > 0) {
    return transcript.value.reduce((sum, t) => sum + t.content.trim().split(/\s+/).length, 0)
  }
  const explicit = props.result.total_words as number | undefined
  if (typeof explicit === 'number' && explicit > 100) return explicit
  return 0
})

const consensusScore = computed(() => {
  const legacy = props.result.consensus_score as number | undefined
  if (typeof legacy === 'number') return legacy
  const fromSummary = summary.value?.consensus?.consensus_level
  return typeof fromSummary === 'number' ? fromSummary : null
})
const consensusPercent = computed(() => consensusScore.value !== null ? Math.round(consensusScore.value * 100) : 0)

function consensusColor(score: number | null): string {
  if (score === null) return 'var(--text-tertiary)'
  if (score >= 0.7) return 'var(--success)'
  if (score >= 0.4) return 'var(--warning)'
  return 'var(--error)'
}

const resolvedSimId = computed(() =>
  props.simulationId ?? (props.result.simulation_id as string | undefined),
)

const selectedIdeaId = computed(() => {
  const fromResult = props.result.selected_idea_id
  if (typeof fromResult === 'string' && fromResult) return fromResult
  const fromStore = pipeline.stageResults['selected_idea_id']
  return typeof fromStore === 'string' && fromStore ? fromStore : null
})

const hasDebateData = computed(() => agentCount.value > 0 || roundCount.value > 0)

const canStartDebate = computed(() => {
  if (!props.runId || hasDebateData.value) return false
  return !!selectedIdeaId.value && debateStageStatus.value !== 'active'
})

const isAwaitingIdeas = computed(() =>
  !selectedIdeaId.value,
)

const debateStageStatus = computed(() => pipeline.stages['debate']?.status ?? 'pending')

// Group transcript by round
const transcriptByRound = computed(() => {
  const grouped: Record<number, Turn[]> = {}
  for (const t of transcript.value) {
    const r = t.round_num
    if (!grouped[r]) grouped[r] = []
    grouped[r]!.push(t)
  }
  return Object.entries(grouped)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([round, turns]) => ({ round: Number(round), turns }))
})

async function handleStartDebate() {
  if (!props.runId || starting.value) return
  starting.value = true
  startError.value = null
  try {
    await startDebate(props.runId)
    await pipeline.refreshStages()
  } catch (err) {
    startError.value = err instanceof Error ? err.message : 'Failed to start debate'
  } finally {
    starting.value = false
  }
}

async function fetchTranscript() {
  if (!resolvedSimId.value || loadingTranscript.value) return
  loadingTranscript.value = true
  try {
    const res = await getTranscript(resolvedSimId.value)
    const data = res.data?.data
    const raw = Array.isArray(data) ? data : []
    transcript.value = raw.map((t) => {
      const entry = t as unknown as Record<string, unknown>
      return {
        agent_name: (entry.agent_name ?? entry.agent ?? 'Agent') as string,
        agent_role: entry.agent_role as string | undefined,
        content: (entry.content ?? '') as string,
        round_num: (entry.round_num ?? 0) as number,
      }
    })
  } catch {
    // Non-critical
  } finally {
    loadingTranscript.value = false
  }
}

async function fetchSummary() {
  if (!resolvedSimId.value || loadingSummary.value) return
  loadingSummary.value = true
  try {
    const res = await getDebateSummary(resolvedSimId.value)
    summary.value = (res.data?.data ?? null) as DebateSummary | null
  } catch {
    // Non-critical
  } finally {
    loadingSummary.value = false
  }
}

function toggleTranscript() {
  showTranscript.value = !showTranscript.value
  if (showTranscript.value && transcript.value.length === 0) {
    fetchTranscript()
  }
}

function formatWords(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

watch(
  () => resolvedSimId.value,
  (nextSimId, previousSimId) => {
    if (!nextSimId) {
      transcript.value = []
      summary.value = null
      return
    }

    if (nextSimId !== previousSimId) {
      transcript.value = []
      summary.value = null
    }

    if ((showTranscript.value || hasDebateData.value) && transcript.value.length === 0) {
      fetchTranscript()
    }
    if (summary.value == null) {
      fetchSummary()
    }
  },
  { immediate: true },
)

watch(showTranscript, (visible) => {
  if (visible && resolvedSimId.value && transcript.value.length === 0) {
    fetchTranscript()
  }
})
</script>

<template>
  <div class="debate-detail">
    <!-- ── Has debate results ── -->
    <template v-if="hasDebateData">
      <div class="debate-detail__metrics">
        <MetricCard label="Agents" :value="agentCount" icon="group" />
        <MetricCard label="Rounds" :value="roundCount" icon="repeat" />
        <MetricCard label="Words" :value="formatWords(totalWords)" icon="text_fields" />
      </div>

      <!-- Consensus Gauge -->
      <div v-if="consensusScore !== null" class="consensus-gauge">
        <div class="consensus-gauge__header">
          <span class="detail-heading">Consensus</span>
          <span class="consensus-gauge__value font-mono" :style="{ color: consensusColor(consensusScore) }">
            {{ consensusPercent }}%
          </span>
        </div>
        <ProgressBar :progress="consensusPercent" :color="consensusColor(consensusScore)" height="8px" />
      </div>

      <!-- Transcript Toggle -->
      <div class="debate-detail__actions">
        <ActionButton
          :variant="showTranscript ? 'primary' : 'secondary'"
          size="sm"
          :icon="showTranscript ? 'expand_less' : 'chat'"
          @click="toggleTranscript"
        >
          {{ showTranscript ? 'Hide Transcript' : 'View Transcript' }}
        </ActionButton>
      </div>

      <!-- Transcript -->
      <div v-if="showTranscript" class="transcript">
        <div v-if="loadingTranscript" class="transcript__loading">
          <span class="material-symbols-outlined spin" style="font-size: 18px">progress_activity</span>
          Loading transcript...
        </div>
        <template v-else-if="transcriptByRound.length > 0">
          <div v-for="group in transcriptByRound" :key="group.round" class="transcript__round">
            <div class="transcript__round-header">Round {{ group.round }}</div>
            <div
              v-for="(turn, i) in group.turns"
              :key="i"
              class="transcript__turn"
            >
              <div class="transcript__agent">
                <span class="transcript__name">{{ turn.agent_name }}</span>
                <span v-if="turn.agent_role" class="transcript__role">{{ turn.agent_role }}</span>
              </div>
              <p class="transcript__content">{{ turn.content }}</p>
            </div>
          </div>
        </template>
        <div v-else class="transcript__empty">No transcript data available</div>
      </div>
    </template>

    <!-- ── No debate yet — show start action ── -->
    <template v-else>
      <div class="debate-start">
        <span class="material-symbols-outlined" style="font-size: 32px; color: var(--text-tertiary)">forum</span>
        <strong>Agent Debate</strong>
        <span class="debate-start__desc">
          <template v-if="canStartDebate">
            Ready to start. The system will auto-generate research agents and run a multi-round debate.
          </template>
          <template v-else-if="debateStageStatus === 'active'">
            Debate is currently running...
          </template>
          <template v-else-if="isAwaitingIdeas">
            Open the <strong>Idea Ranking</strong> stage and select an idea first.
          </template>
          <template v-else>
            Complete the Ideas stage and select an idea to start the debate.
          </template>
        </span>
        <ActionButton v-if="canStartDebate" variant="primary" icon="play_arrow" :loading="starting" @click="handleStartDebate">
          Start Debate
        </ActionButton>
        <div v-if="debateStageStatus === 'active'" class="debate-start__running">
          <span class="material-symbols-outlined spin" style="font-size: 18px; color: var(--os-brand)">progress_activity</span>
          Debate in progress...
        </div>
        <div v-if="startError" class="debate-start__error">{{ startError }}</div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.debate-detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 14px;
}

.debate-detail__metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
}

.detail-heading {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.consensus-gauge { display: flex; flex-direction: column; gap: 6px; }
.consensus-gauge__header { display: flex; align-items: center; justify-content: space-between; }
.consensus-gauge__value { font-size: 16px; font-weight: 700; }

.debate-detail__actions { display: flex; gap: 8px; }

/* ── Transcript ── */
.transcript {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 500px;
  overflow-y: auto;
  padding-right: 4px;
}

.transcript__loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  color: var(--text-secondary);
  font-size: 13px;
}

.transcript__round-header {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-tertiary);
  padding: 4px 0;
  border-bottom: 1px solid var(--border-secondary);
  margin-bottom: 8px;
}

.transcript__round {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.transcript__turn {
  padding: 10px 12px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--os-brand);
}

.transcript__agent {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.transcript__name {
  font-size: 12px;
  font-weight: 600;
  color: var(--os-brand);
}

.transcript__role {
  font-size: 10px;
  color: var(--text-tertiary);
  padding: 1px 6px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-pill);
}

.transcript__content {
  font-size: 12px;
  color: var(--text-primary);
  line-height: 1.6;
  margin: 0;
  white-space: pre-wrap;
}

.transcript__empty {
  padding: 16px;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
}

/* ── Start Debate ── */
.debate-start {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 24px;
  background: var(--bg-secondary);
  border: 1px dashed var(--border-primary);
  border-radius: var(--radius-md);
  align-items: center;
  text-align: center;
}

.debate-start strong { font-size: 14px; color: var(--text-primary); }

.debate-start__desc {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.5;
  max-width: 400px;
}

.debate-start__running {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--os-brand);
}

.debate-start__error { font-size: 12px; color: var(--error); }

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>

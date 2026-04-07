<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ProgressBar from '@/components/shared/ProgressBar.vue'
import ActionButton from '@/components/shared/ActionButton.vue'
import MetricCard from '@/components/shared/MetricCard.vue'
import { exportDocx } from '@/api/paperLab'
import { getRevisionHistory } from '@/api/ais'
import type { RevisionRound } from '@/api/ais'
import service from '@/api/client'

const props = defineProps<{
  result: Record<string, unknown>
  runId?: string
}>()

const error = ref<string | null>(null)
const loadingDraft = ref(false)

interface RoundScore {
  round: number
  score: number
}

const roundProgression = computed<RoundScore[]>(() => {
  // Accept either an array of scores or an array of {round, score} objects
  const scores = (props.result.review_scores ?? props.result.score_progression) as number[] | RoundScore[] | undefined
  if (scores && Array.isArray(scores)) {
    return scores.map((entry, i) => {
      if (typeof entry === 'number') {
        return { round: i + 1, score: entry }
      }
      return entry as RoundScore
    })
  }

  const lastScore = props.result.last_score as number | undefined
  if (typeof lastScore === 'number') {
    return [{
      round: ((props.result.revision_count as number | undefined) ?? 1),
      score: lastScore,
    }]
  }

  return []
})

const roundsCompleted = computed(() => {
  const raw = props.result.rounds_completed as number | undefined
  if (typeof raw === 'number') return raw
  if (roundProgression.value.length > 0) return roundProgression.value.length
  return (props.result.revision_count as number | undefined) ?? 0
})

const reviewerCount = computed(() => {
  if (reviewerAgents.value.length > 0) return reviewerAgents.value.length
  return (props.result.reviewer_count as number | undefined) ?? 0
})

const latestScore = computed(() => {
  if (roundProgression.value.length === 0) return null
  return roundProgression.value[roundProgression.value.length - 1]?.score ?? null
})

const finalDecision = computed(() => {
  return (props.result.final_decision as string | undefined)
    ?? (props.result.status as string | undefined)
    ?? null
})

function scoreColor(score: number): string {
  if (score >= 7) return 'var(--success)'
  if (score >= 4) return 'var(--warning)'
  return 'var(--error)'
}

const hasData = computed(() =>
  roundProgression.value.length > 0 || reviewerAgents.value.length > 0 || roundsCompleted.value > 0,
)

// The upload_id for paper-lab routes (rehab result may carry it)
const uploadId = computed(() => (props.result.upload_id as string) ?? props.runId ?? null)

async function handleViewDraft() {
  if (!uploadId.value) return
  loadingDraft.value = true
  error.value = null
  try {
    // Try paper-lab draft endpoint first (rehab uses paper-lab API)
    const baseURL = service.defaults.baseURL || ''
    window.open(`${baseURL}/api/research/paper-lab/${uploadId.value}/draft`, '_blank')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to view draft'
    console.error('Failed to view draft:', err)
  } finally {
    loadingDraft.value = false
  }
}

function handleExportDocx() {
  if (!uploadId.value) {
    error.value = 'No upload ID available for export'
    return
  }
  try {
    exportDocx(uploadId.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to export DOCX'
    console.error('Failed to export DOCX:', err)
  }
}
interface ReviewerAgent {
  name: string
  role?: string
  score?: number
}

const reviewerAgents = computed<ReviewerAgent[]>(() => {
  const raw = props.result.reviewers as ReviewerAgent[] | undefined
  if (!raw || !Array.isArray(raw)) return []
  return raw
})

// ── P-3 Revision History ──
const revisionRounds = ref<RevisionRound[]>([])
const revisionTrajectory = ref<Array<{ round: number; avg_score: number }>>([])
const regressionWarnings = ref<Array<{ metric: string; detail: string }>>([])
const historyLoaded = ref(false)

async function fetchRevisionHistory() {
  if (!props.runId || historyLoaded.value) return
  try {
    const res = await getRevisionHistory(props.runId)
    const data = res.data?.data
    if (data) {
      revisionRounds.value = data.rounds ?? []
      revisionTrajectory.value = data.score_trajectory ?? []
      regressionWarnings.value = data.regression_warnings ?? []
      historyLoaded.value = true
    }
  } catch {
    // best effort
  }
}

watch(() => props.runId, (id) => {
  if (id) fetchRevisionHistory()
}, { immediate: true })
</script>

<template>
  <div class="rehab-detail">
    <template v-if="hasData">
      <!-- Metrics -->
      <div class="rehab-detail__metrics">
        <MetricCard
          label="Rounds"
          :value="roundsCompleted"
          icon="repeat"
        />
        <MetricCard
          v-if="latestScore !== null"
          label="Latest Score"
          :value="latestScore?.toFixed(1) ?? '--'"
          icon="grade"
        />
        <MetricCard
          label="Reviewers"
          :value="reviewerCount"
          icon="group"
        />
        <MetricCard
          v-if="finalDecision"
          label="Decision"
          :value="finalDecision"
          icon="gavel"
        />
      </div>

      <!-- Round Progression Chart -->
      <div v-if="roundProgression.length > 0" class="score-chart">
        <h5 class="detail-heading">Score Progression</h5>
        <div class="score-chart__bars">
          <div
            v-for="entry in roundProgression"
            :key="entry.round"
            class="round-bar"
          >
            <span class="round-bar__label font-mono">Round {{ entry.round }}</span>
            <ProgressBar
              :progress="entry.score * 10"
              :color="scoreColor(entry.score)"
              height="8px"
            />
            <span
              class="round-bar__value font-mono"
              :style="{ color: scoreColor(entry.score) }"
            >
              {{ entry.score.toFixed(1) }}
            </span>
          </div>
        </div>
      </div>

      <!-- Reviewer Agent Cards -->
      <div v-if="reviewerAgents.length > 0" class="reviewer-section">
        <h5 class="detail-heading">Reviewer Agents</h5>
        <div class="reviewer-grid">
          <div
            v-for="(agent, i) in reviewerAgents"
            :key="i"
            class="reviewer-card"
          >
            <div class="reviewer-card__avatar">
              <span class="material-symbols-outlined" style="font-size: 18px">person</span>
            </div>
            <div class="reviewer-card__info">
              <span class="reviewer-card__name">{{ agent.name }}</span>
              <span v-if="agent.role" class="reviewer-card__role">{{ agent.role }}</span>
            </div>
            <span
              v-if="agent.score"
              class="reviewer-card__score font-mono"
              :style="{ color: scoreColor(agent.score) }"
            >
              {{ agent.score.toFixed(1) }}
            </span>
          </div>
        </div>
      </div>

      <div v-if="error" class="rehab-detail__error">
        <span class="material-symbols-outlined" style="font-size: 16px; color: var(--error)">error</span>
        <span>{{ error }}</span>
      </div>

      <!-- Actions -->
      <div class="rehab-detail__actions">
        <ActionButton
          variant="secondary"
          size="sm"
          icon="visibility"
          :loading="loadingDraft"
          @click="handleViewDraft"
        >
          View Draft
        </ActionButton>
        <ActionButton
          variant="ghost"
          size="sm"
          icon="download"
          @click="handleExportDocx"
        >
          Export DOCX
        </ActionButton>
      </div>
    </template>

    <div v-else class="rehab-detail__empty">
      <span class="material-symbols-outlined" style="font-size: 24px; color: var(--text-tertiary)">healing</span>
      <span>No rehabilitation data available yet</span>
    </div>

    <!-- P-3: Revision Board History -->
    <div v-if="revisionRounds.length > 0" class="revision-board-history">
      <h5 class="detail-heading">Review Board History</h5>

      <div v-if="regressionWarnings.length > 0" class="revision-board-history__warnings">
        <div v-for="(warn, i) in regressionWarnings" :key="i" class="revision-board-history__warning">
          <span class="material-symbols-outlined" style="font-size: 14px; color: var(--warning, #f59e0b)">warning</span>
          {{ warn.detail }}
        </div>
      </div>

      <div class="revision-board-history__rounds">
        <div v-for="round in revisionRounds" :key="round.round_id" class="revision-round-card">
          <div class="revision-round-card__header">
            <span class="revision-round-card__num font-mono">Round {{ round.round_number }}</span>
            <span class="revision-round-card__mode">{{ round.rewrite_mode }}</span>
            <span class="revision-round-card__score font-mono" :style="{ color: round.avg_score >= 7 ? 'var(--success, #22c55e)' : round.avg_score >= 4 ? 'var(--warning, #f59e0b)' : 'var(--danger, #ef4444)' }">
              {{ round.avg_score.toFixed(1) }}
            </span>
          </div>
          <div class="revision-round-card__reviewers">
            <span v-for="r in round.results" :key="r.reviewer_type" class="revision-round-card__reviewer">
              {{ r.reviewer_name }}: {{ r.overall_score.toFixed(1) }}
            </span>
          </div>
          <div v-if="round.themes.length" class="revision-round-card__themes">
            <span v-for="t in round.themes" :key="t.theme_id" class="revision-round-card__theme">
              P{{ t.priority }} {{ t.title }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rehab-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 14px;
}

.detail-heading {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin: 0 0 8px;
}

.rehab-detail__metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
}

/* ── Score Chart ── */
.score-chart__bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.round-bar {
  display: grid;
  grid-template-columns: 72px 1fr 40px;
  gap: 10px;
  align-items: center;
}

.round-bar__label {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.round-bar__value {
  font-size: 13px;
  font-weight: 700;
  text-align: right;
}

/* ── Reviewer Cards ── */
.reviewer-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px;
}

.reviewer-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  transition: border-color var(--transition-fast);
}

.reviewer-card:hover {
  border-color: var(--border-primary);
}

.reviewer-card__avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--bg-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.reviewer-card__info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  flex: 1;
}

.reviewer-card__name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reviewer-card__role {
  font-size: 10px;
  color: var(--text-tertiary);
}

.reviewer-card__score {
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}

/* ── Actions ── */
.rehab-detail__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.rehab-detail__empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 20px;
  color: var(--text-tertiary);
  font-size: 13px;
  justify-content: center;
}

.rehab-detail__error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  font-size: 12px;
  color: var(--error);
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: var(--radius-md);
}

/* ── Revision Board History (P-3) ── */
.revision-board-history { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.revision-board-history__warnings { display: flex; flex-direction: column; gap: 4px; }
.revision-board-history__warning {
  display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--warning, #f59e0b);
  padding: 6px 10px; background: color-mix(in srgb, var(--warning, #f59e0b) 8%, transparent);
  border-radius: var(--radius-sm);
}
.revision-board-history__rounds { display: flex; flex-direction: column; gap: 6px; }
.revision-round-card {
  padding: 10px 12px; background: var(--bg-secondary);
  border: 1px solid var(--border-secondary); border-radius: var(--radius-md);
}
.revision-round-card__header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.revision-round-card__num { font-size: 11px; font-weight: 700; color: var(--os-brand); }
.revision-round-card__mode { font-size: 10px; color: var(--text-tertiary); text-transform: capitalize; }
.revision-round-card__score { font-size: 12px; font-weight: 700; margin-left: auto; }
.revision-round-card__reviewers { display: flex; flex-wrap: wrap; gap: 8px; font-size: 11px; color: var(--text-secondary); }
.revision-round-card__reviewer { display: inline; }
.revision-round-card__themes { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.revision-round-card__theme {
  font-size: 9px; font-weight: 600; padding: 2px 6px; border-radius: var(--radius-pill, 999px);
  background: var(--bg-primary); border: 1px solid var(--border-secondary); color: var(--text-tertiary);
}
</style>

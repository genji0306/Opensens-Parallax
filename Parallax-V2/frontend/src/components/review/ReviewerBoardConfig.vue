<script setup lang="ts">
/**
 * ReviewerBoardConfig — Select and configure reviewer panel (Sprint 9).
 */

import { ref, onMounted, watch } from 'vue'
import { getReviewerArchetypes, getRevisionHistory, runReviewRound } from '@/api/ais'
import type { RevisionRound, RewriteMode } from '@/api/ais'

const props = defineProps<{ runId: string }>()
const emit = defineEmits<{ 'review-complete': [round: RevisionRound] }>()

const archetypes = ref<Record<string, { name: string; focus: string; rubric: string[] }>>({})
const selected = ref<string[]>([])
const strictness = ref(0.7)
const rewriteMode = ref<RewriteMode>('conservative')
const loading = ref(false)
const error = ref<string | null>(null)
const latestRound = ref<RevisionRound | null>(null)
const totalRounds = ref(0)
const latestScore = ref(0)
const improving = ref(false)

async function hydrateReviewHistory() {
  if (!props.runId) {
    latestRound.value = null
    totalRounds.value = 0
    latestScore.value = 0
    improving.value = false
    return
  }

  try {
    const res = await getRevisionHistory(props.runId)
    const data = res.data?.data
    const rounds = Array.isArray(data?.rounds) ? data.rounds : []
    latestRound.value = rounds.length ? (rounds[rounds.length - 1] ?? null) : null
    totalRounds.value = Number(data?.total_rounds ?? rounds.length)
    latestScore.value = Number(data?.latest_score ?? latestRound.value?.avg_score ?? 0)
    improving.value = Boolean(data?.improving)
  } catch {
    latestRound.value = null
    totalRounds.value = 0
    latestScore.value = 0
    improving.value = false
  }
}

onMounted(async () => {
  try {
    const res = await getReviewerArchetypes()
    archetypes.value = res.data?.data ?? {}
    selected.value = Object.keys(archetypes.value)
  } catch { /* best effort */ }

  await hydrateReviewHistory()
})

watch(() => props.runId, () => {
  hydrateReviewHistory()
})

function toggleReviewer(key: string) {
  const idx = selected.value.indexOf(key)
  if (idx >= 0) selected.value = selected.value.filter((_, i) => i !== idx)
  else selected.value = [...selected.value, key]
}

async function startReview() {
  if (!selected.value.length) return
  loading.value = true
  error.value = null
  try {
    const res = await runReviewRound(props.runId, {
      reviewer_types: selected.value,
      strictness: strictness.value,
      rewrite_mode: rewriteMode.value,
    })
    const round = res.data?.data
    if (round) {
      latestRound.value = round
      emit('review-complete', round)
      await hydrateReviewHistory()
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Review failed'
  } finally {
    loading.value = false
  }
}

const strictnessLabel = (v: number) => v > 0.8 ? 'Very Strict' : v > 0.4 ? 'Moderate' : 'Lenient'
</script>

<template>
  <div class="board-config">
    <h5 class="board-config__title">Reviewer Board</h5>

    <div class="board-config__reviewers">
      <button
        v-for="(info, key) in archetypes"
        :key="key"
        class="board-config__reviewer"
        :class="{ 'board-config__reviewer--active': selected.includes(key as string) }"
        @click="toggleReviewer(key as string)"
      >
        <span class="board-config__reviewer-name">{{ info.name }}</span>
        <span class="board-config__reviewer-focus">{{ info.focus }}</span>
      </button>
    </div>

    <div class="board-config__controls">
      <div class="board-config__field">
        <label>Strictness: <strong>{{ strictnessLabel(strictness) }}</strong></label>
        <input type="range" min="0" max="1" step="0.1" v-model.number="strictness" class="board-config__slider" />
      </div>

      <div class="board-config__field">
        <label>Rewrite Mode</label>
        <select v-model="rewriteMode" class="board-config__select">
          <option value="conservative">Conservative</option>
          <option value="novelty">Novelty-Maximizing</option>
          <option value="clarity">Clarity-First</option>
          <option value="journal">Journal-Style</option>
        </select>
      </div>
    </div>

    <div v-if="error" class="board-config__error">{{ error }}</div>

    <button class="board-config__start" :disabled="loading || !selected.length" @click="startReview">
      {{ loading ? 'Running Review...' : `Run Review (${selected.length} reviewers)` }}
    </button>

    <div v-if="latestRound" class="board-config__latest">
      <div class="board-config__latest-header">
        <h6 class="board-config__latest-title">Latest Round</h6>
        <div class="board-config__latest-meta">
          <span class="board-config__chip">Round {{ latestRound.round_number }}</span>
          <span class="board-config__chip">Score {{ latestScore.toFixed(1) }}/10</span>
          <span v-if="totalRounds > 1" class="board-config__chip">
            {{ improving ? 'Improving' : 'Needs follow-up' }}
          </span>
        </div>
      </div>

      <div class="board-config__results">
        <div v-for="result in latestRound.results" :key="result.reviewer_type" class="board-config__result">
          <div class="board-config__result-header">
            <span class="board-config__result-name">{{ result.reviewer_name }}</span>
            <span class="board-config__result-score font-mono">{{ result.overall_score.toFixed(1) }}</span>
          </div>
          <p class="board-config__result-summary">{{ result.summary }}</p>
          <div class="board-config__result-meta">
            <span>{{ result.comments.length }} comments</span>
            <span>{{ result.strengths.length }} strengths</span>
            <span>{{ result.weaknesses.length }} weaknesses</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.board-config { display: flex; flex-direction: column; gap: 12px; }
.board-config__title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); margin: 0; }

.board-config__reviewers { display: flex; flex-direction: column; gap: 6px; }
.board-config__reviewer {
  display: flex; flex-direction: column; gap: 2px; padding: 8px 10px; text-align: left;
  background: var(--bg-secondary); border: 1px solid var(--border-secondary); border-radius: var(--radius-md);
  cursor: pointer; transition: border-color 0.15s ease;
}
.board-config__reviewer:hover { border-color: var(--text-tertiary); }
.board-config__reviewer--active { border-color: var(--os-brand); background: color-mix(in srgb, var(--os-brand) 8%, transparent); }
.board-config__reviewer-name { font-size: 12px; font-weight: 500; color: var(--text-primary); }
.board-config__reviewer-focus { font-size: 10px; color: var(--text-tertiary); }

.board-config__controls { display: flex; gap: 12px; flex-wrap: wrap; }
.board-config__field { display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 140px; }
.board-config__field label { font-size: 11px; color: var(--text-secondary); }
.board-config__slider { accent-color: var(--os-brand); }
.board-config__select {
  padding: 5px 8px; font-size: 12px; background: var(--bg-secondary);
  border: 1px solid var(--border-secondary); border-radius: var(--radius-sm);
  color: var(--text-primary); cursor: pointer;
}

.board-config__error { font-size: 12px; color: var(--danger, #ef4444); }
.board-config__start {
  padding: 8px 16px; font-size: 12px; font-weight: 500; color: #fff;
  background: var(--os-brand); border: none; border-radius: var(--radius-md); cursor: pointer;
}
.board-config__start:disabled { opacity: 0.5; cursor: not-allowed; }

.board-config__latest {
  display: flex; flex-direction: column; gap: 10px; padding: 12px;
  background: var(--bg-secondary); border: 1px solid var(--border-secondary); border-radius: var(--radius-md);
}
.board-config__latest-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.board-config__latest-title { margin: 0; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); }
.board-config__latest-meta, .board-config__result-meta { display: flex; gap: 8px; flex-wrap: wrap; }
.board-config__chip {
  font-size: 10px; padding: 2px 8px; border-radius: var(--radius-pill, 999px);
  background: var(--bg-primary); border: 1px solid var(--border-secondary); color: var(--text-tertiary);
}
.board-config__results { display: flex; flex-direction: column; gap: 8px; }
.board-config__result {
  display: flex; flex-direction: column; gap: 6px; padding: 10px 12px;
  background: var(--bg-primary); border: 1px solid var(--border-secondary); border-radius: var(--radius-md);
}
.board-config__result-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.board-config__result-name { font-size: 12px; font-weight: 500; color: var(--text-primary); }
.board-config__result-score { font-size: 11px; color: var(--os-brand); }
.board-config__result-summary { margin: 0; font-size: 12px; color: var(--text-secondary); line-height: 1.45; }
.board-config__result-meta { font-size: 10px; color: var(--text-tertiary); }
</style>

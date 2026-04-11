<script setup lang="ts">
import { computed } from 'vue'

interface Weakness {
  text?: string
  description?: string
}

interface TriageItem {
  weakness: string
  action: string
  justification?: string
}

interface RoundData {
  round_num?: number
  round?: number
  review?: {
    avg_overall_score?: number
    final_decision?: string
    all_weaknesses?: Weakness[]
  }
  revision?: {
    triage?: TriageItem[]
    accepted_count?: number
    rebutted_count?: number
    deferred_count?: number
  }
}

interface RoundsResponse {
  rounds: RoundData[]
  score_progression: number[]
  source_audit?: {
    verified?: string[]
    unverified?: string[]
    method?: string
  }
}

const props = defineProps<{
  title: string
  roundsData: RoundsResponse | null
  currentDraft: { draft: string; word_count: number } | null
  specialistResults: Record<string, unknown> | null
  specialistStatus: 'idle' | 'running' | 'done' | 'error'
}>()

const latestRound = computed(() => {
  const rounds = props.roundsData?.rounds ?? []
  return rounds.length ? rounds[rounds.length - 1] : null
})

const topWeaknesses = computed(() =>
  (latestRound.value?.review?.all_weaknesses ?? [])
    .map(item => item.text || item.description || '')
    .filter(Boolean)
    .slice(0, 4),
)

const triage = computed(() => (latestRound.value?.revision?.triage ?? []).slice(0, 4))
const scoreProgression = computed(() => props.roundsData?.score_progression ?? [])
const specialistFindingCount = computed(() => {
  const reviews = (props.specialistResults?.reviews as Array<{ findings?: unknown[] }> | undefined) ?? []
  return reviews.reduce((sum, review) => sum + ((review.findings ?? []).length), 0)
})
const unverifiedCount = computed(() => props.roundsData?.source_audit?.unverified?.length ?? 0)
const nextAction = computed(() => {
  if (!props.roundsData?.rounds?.length) return 'Run the adversarial review to generate findings, revisions, and visual planning inputs.'
  if (topWeaknesses.value.some(text => /figure|visual|diagram|table/i.test(text))) return 'Generate a visualization plan to address reviewer-facing evidence gaps.'
  if (unverifiedCount.value > 0) return 'Strengthen the literature review and verify source coverage before export.'
  if (props.specialistStatus !== 'done') return 'Run specialist review to deepen domain-specific critique before final outputs.'
  return 'Move into the Visualization Studio to create export-ready figures and communication artifacts.'
})
</script>

<template>
  <div class="review-overview">
    <div class="review-overview__hero">
      <div>
        <p class="eyebrow">Review Overview</p>
        <h3>{{ title }}</h3>
        <p class="summary">{{ nextAction }}</p>
      </div>
      <div class="metrics">
        <div class="metric">
          <span class="metric__label">Rounds</span>
          <span class="metric__value">{{ roundsData?.rounds?.length ?? 0 }}</span>
        </div>
        <div class="metric">
          <span class="metric__label">Scores</span>
          <span class="metric__value">{{ scoreProgression.length ? scoreProgression.join(' → ') : '—' }}</span>
        </div>
        <div class="metric">
          <span class="metric__label">Draft Words</span>
          <span class="metric__value">{{ currentDraft?.word_count ?? 0 }}</span>
        </div>
      </div>
    </div>

    <div class="review-overview__grid">
      <section class="card">
        <h4>Reviewer Themes</h4>
        <ul v-if="topWeaknesses.length" class="list">
          <li v-for="item in topWeaknesses" :key="item">{{ item }}</li>
        </ul>
        <p v-else class="empty">No review weaknesses available yet.</p>
      </section>

      <section class="card">
        <h4>Revision Triage</h4>
        <ul v-if="triage.length" class="list">
          <li v-for="item in triage" :key="`${item.weakness}-${item.action}`">
            <strong>{{ item.action }}</strong>: {{ item.weakness }}
          </li>
        </ul>
        <p v-else class="empty">No revision triage recorded yet.</p>
      </section>

      <section class="card">
        <h4>Draft Snapshot</h4>
        <p class="draft-preview">{{ currentDraft?.draft?.slice(0, 380) || 'Current draft will appear here after review.' }}</p>
      </section>

      <section class="card">
        <h4>Specialist Review</h4>
        <p class="specialist-status">Status: <strong>{{ specialistStatus }}</strong></p>
        <p class="empty" v-if="specialistStatus !== 'done'">Run specialist review to surface domain-specific findings.</p>
        <p v-else class="empty">{{ specialistFindingCount }} findings captured across specialist reviewers.</p>
      </section>

      <section class="card">
        <h4>Source Audit</h4>
        <p class="empty">Verified: {{ roundsData?.source_audit?.verified?.length ?? 0 }}</p>
        <p class="empty">Unverified: {{ unverifiedCount }}</p>
        <p class="empty">Method: {{ roundsData?.source_audit?.method || '—' }}</p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.review-overview {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.review-overview__hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 18px;
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, rgba(204, 255, 0, 0.08), rgba(255, 255, 255, 0.02));
}

.eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--os-brand);
}

h3 {
  margin: 0;
  font-size: 18px;
  color: var(--text-primary);
}

.summary {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
  max-width: 720px;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(92px, 1fr));
  gap: 10px;
  min-width: 300px;
}

.metric {
  padding: 12px;
  border-radius: var(--radius-md);
  background: rgba(0, 0, 0, 0.18);
  border: 1px solid var(--border-secondary);
}

.metric__label {
  display: block;
  margin-bottom: 6px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-tertiary);
}

.metric__value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 600;
}

.review-overview__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.card {
  padding: 16px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-secondary);
  background: var(--bg-secondary);
}

.card h4 {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--text-primary);
}

.list {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 12px;
}

.draft-preview,
.empty,
.specialist-status {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  white-space: pre-wrap;
}

@media (max-width: 960px) {
  .review-overview__hero,
  .review-overview__grid {
    grid-template-columns: 1fr;
    display: grid;
  }

  .metrics {
    min-width: 0;
  }
}
</style>

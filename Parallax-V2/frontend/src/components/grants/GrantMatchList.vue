<script setup lang="ts">
import { computed, ref } from 'vue'

import GlassPanel from '@/components/shared/GlassPanel.vue'
import { useGrantsStore } from '@/stores/grants'
import type { MatchedOpportunity } from '@/types/grants'

const emit = defineEmits<{ (e: 'open-proposal'): void }>()

const store = useGrantsStore()

const minScore = ref(0)
const query = ref('')

const filtered = computed<MatchedOpportunity[]>(() => {
  const q = query.value.trim().toLowerCase()
  return store.topMatches.filter(m => {
    if (m.match.fit_score < minScore.value) return false
    if (!q) return true
    const o = m.opportunity
    return (
      o.title.toLowerCase().includes(q)
      || o.funder.toLowerCase().includes(q)
      || o.themes.some(t => t.toLowerCase().includes(q))
    )
  })
})

function scoreClass(score: number): string {
  if (score >= 80) return 'score--excellent'
  if (score >= 60) return 'score--good'
  if (score >= 40) return 'score--partial'
  return 'score--weak'
}

async function shortlist(match: MatchedOpportunity): Promise<void> {
  await store.recordFeedback({
    event_type: 'opportunity_shortlisted',
    target_id: match.opportunity.opportunity_id,
    payload: { fit_score: match.match.fit_score },
  })
}

async function dismiss(match: MatchedOpportunity): Promise<void> {
  await store.recordFeedback({
    event_type: 'opportunity_dismissed',
    target_id: match.opportunity.opportunity_id,
    payload: { fit_score: match.match.fit_score },
  })
}

async function start(match: MatchedOpportunity): Promise<void> {
  const proposal = await store.startProposal(match.opportunity.opportunity_id)
  if (proposal) {
    await store.recordFeedback({
      event_type: 'match_accepted',
      target_id: match.opportunity.opportunity_id,
      payload: { fit_score: match.match.fit_score, proposal_id: proposal.proposal_id },
    })
    await store.runPlanner(proposal.proposal_id)
    emit('open-proposal')
  }
}
</script>

<template>
  <GlassPanel title="Ranked matches" icon="insights">
    <div class="match-list">
      <div class="match-list__filters">
        <input v-model="query" placeholder="Search title / funder / theme" />
        <label>
          <span>Min score {{ minScore }}</span>
          <input v-model.number="minScore" type="range" min="0" max="100" step="5" />
        </label>
      </div>

      <div v-if="store.matches.length === 0" class="empty">
        No ranked matches yet — run Score matches in the Discover stage.
      </div>

      <ul v-else class="matches">
        <li
          v-for="m in filtered"
          :key="m.opportunity.opportunity_id"
          class="match"
        >
          <div class="match__header">
            <div :class="['score', scoreClass(m.match.fit_score)]">
              {{ Math.round(m.match.fit_score) }}
            </div>
            <div class="match__title">
              <a :href="m.opportunity.call_url || m.opportunity.source_url" target="_blank" rel="noopener">
                {{ m.opportunity.title }}
              </a>
              <div class="match__meta">
                <span v-if="m.opportunity.funder">{{ m.opportunity.funder }}</span>
                <span v-if="m.opportunity.amount">{{ m.opportunity.amount }}</span>
                <span v-if="m.opportunity.deadline">Due {{ m.opportunity.deadline }}</span>
              </div>
            </div>
          </div>

          <p v-if="m.opportunity.summary" class="match__summary">{{ m.opportunity.summary }}</p>

          <div v-if="m.match.fit_reasons.length" class="match__reasons">
            <strong>Why it fits:</strong>
            <ul>
              <li v-for="(r, i) in m.match.fit_reasons" :key="i">{{ r }}</li>
            </ul>
          </div>

          <div v-if="m.match.red_flags.length" class="match__flags">
            <strong>Red flags:</strong>
            <ul>
              <li v-for="(flag, i) in m.match.red_flags" :key="i">{{ flag }}</li>
            </ul>
          </div>

          <p v-if="m.match.suggested_angle" class="match__angle">
            <span class="material-icons">lightbulb</span>
            {{ m.match.suggested_angle }}
          </p>

          <div class="match__actions">
            <button class="btn-primary" @click="start(m)">
              <span class="material-icons">edit_note</span>
              Start proposal
            </button>
            <button class="btn-ghost" @click="shortlist(m)">
              <span class="material-icons">bookmark</span>
              Shortlist
            </button>
            <button class="btn-ghost" @click="dismiss(m)">
              <span class="material-icons">block</span>
              Dismiss
            </button>
          </div>
        </li>
      </ul>
    </div>
  </GlassPanel>
</template>

<style scoped>
.match-list__filters {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.match-list__filters input[type='text'],
.match-list__filters > input {
  flex: 1;
  min-width: 240px;
  background: var(--color-surface, rgba(255, 255, 255, 0.04));
  color: inherit;
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.08));
  border-radius: 6px;
  padding: 0.5rem 0.7rem;
  font: inherit;
  font-size: 0.85rem;
}

.match-list__filters label {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted, #8e95a8);
}

.empty {
  padding: 2rem 0;
  text-align: center;
  color: var(--color-text-muted, #8e95a8);
  font-size: 0.9rem;
}

.matches {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.match {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.06));
  border-radius: 10px;
  padding: 0.9rem 1rem;
}

.match__header {
  display: flex;
  gap: 0.85rem;
  align-items: flex-start;
  margin-bottom: 0.5rem;
}

.score {
  min-width: 2.5rem;
  height: 2.5rem;
  border-radius: 8px;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 1rem;
}

.score--excellent {
  background: rgba(120, 220, 160, 0.2);
  color: #78dca0;
  border: 1px solid rgba(120, 220, 160, 0.4);
}

.score--good {
  background: rgba(122, 162, 255, 0.2);
  color: #7aa2ff;
  border: 1px solid rgba(122, 162, 255, 0.4);
}

.score--partial {
  background: rgba(255, 196, 96, 0.2);
  color: #ffc460;
  border: 1px solid rgba(255, 196, 96, 0.4);
}

.score--weak {
  background: rgba(255, 142, 142, 0.16);
  color: #ff8e8e;
  border: 1px solid rgba(255, 142, 142, 0.35);
}

.match__title a {
  color: inherit;
  text-decoration: none;
  font-weight: 600;
  font-size: 0.95rem;
}

.match__title a:hover {
  color: var(--color-accent, #7aa2ff);
}

.match__meta {
  display: flex;
  gap: 0.7rem;
  font-size: 0.77rem;
  color: var(--color-text-muted, #8e95a8);
  margin-top: 0.2rem;
}

.match__summary {
  margin: 0.35rem 0;
  font-size: 0.83rem;
  line-height: 1.5;
  color: var(--color-text, inherit);
}

.match__reasons,
.match__flags {
  font-size: 0.78rem;
  margin-top: 0.4rem;
}

.match__reasons strong,
.match__flags strong {
  color: var(--color-text-muted, #8e95a8);
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.match__reasons ul,
.match__flags ul {
  margin: 0.2rem 0 0;
  padding-left: 1.1rem;
  line-height: 1.45;
}

.match__flags ul {
  color: #ff8e8e;
}

.match__angle {
  margin: 0.6rem 0 0;
  font-size: 0.82rem;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--color-accent, #7aa2ff);
}

.match__angle .material-icons {
  font-size: 1rem;
}

.match__actions {
  display: flex;
  gap: 0.4rem;
  margin-top: 0.7rem;
}

.btn-primary,
.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  font: inherit;
  font-size: 0.8rem;
  cursor: pointer;
  border: 1px solid transparent;
}

.btn-primary {
  background: var(--color-accent, #7aa2ff);
  color: #0b0f18;
  font-weight: 600;
}

.btn-ghost {
  background: transparent;
  color: inherit;
  border-color: var(--color-border, rgba(255, 255, 255, 0.12));
}
</style>

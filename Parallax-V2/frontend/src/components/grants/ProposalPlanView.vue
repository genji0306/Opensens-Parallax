<script setup lang="ts">
import { computed } from 'vue'

import GlassPanel from '@/components/shared/GlassPanel.vue'
import { useGrantsStore } from '@/stores/grants'

defineEmits<{ (e: 'next'): void }>()

const store = useGrantsStore()

const proposal = computed(() => store.activeProposal)
const planning = computed(() => Boolean(store.loading.plan))

async function regeneratePlan(): Promise<void> {
  if (!proposal.value) return
  await store.runPlanner(proposal.value.proposal_id)
}
</script>

<template>
  <GlassPanel title="Proposal Plan" icon="format_list_numbered">
    <div v-if="!proposal" class="empty">
      No proposal selected. Start one from the Match stage.
    </div>

    <div v-else class="plan">
      <div class="plan__header">
        <div>
          <div class="plan__meta">Proposal {{ proposal.proposal_id }}</div>
          <div class="plan__status">Status: <strong>{{ proposal.status }}</strong></div>
        </div>
        <div class="plan__actions">
          <button class="btn-ghost" :disabled="planning" @click="regeneratePlan">
            <span class="material-icons">{{ planning ? 'hourglass_top' : 'refresh' }}</span>
            {{ planning ? 'Planning…' : 'Regenerate plan' }}
          </button>
          <button class="btn-primary" :disabled="proposal.plan.sections.length === 0" @click="$emit('next')">
            <span class="material-icons">edit_note</span>
            Start drafting
          </button>
        </div>
      </div>

      <div v-if="proposal.plan.sections.length === 0" class="empty">
        Plan not generated yet.
      </div>

      <div v-else>
        <h4>Sections</h4>
        <ol class="sections">
          <li v-for="s in proposal.plan.sections" :key="s.key">
            <div class="sections__title">{{ s.title }}</div>
            <div v-if="s.word_limit" class="sections__word-limit">{{ s.word_limit }} words</div>
            <p v-if="s.guidance" class="sections__guidance">{{ s.guidance }}</p>
          </li>
        </ol>

        <div v-if="proposal.plan.narrative_hooks.length" class="block">
          <h4>Narrative hooks</h4>
          <ul>
            <li v-for="(h, i) in proposal.plan.narrative_hooks" :key="i">{{ h }}</li>
          </ul>
        </div>

        <div v-if="proposal.plan.risks.length" class="block">
          <h4>Risks to address</h4>
          <ul class="warn">
            <li v-for="(r, i) in proposal.plan.risks" :key="i">{{ r }}</li>
          </ul>
        </div>

        <div v-if="proposal.plan.required_attachments.length" class="block">
          <h4>Required attachments</h4>
          <ul>
            <li v-for="(a, i) in proposal.plan.required_attachments" :key="i">{{ a }}</li>
          </ul>
        </div>

        <div v-if="proposal.plan.budget_skeleton.length" class="block">
          <h4>Budget skeleton</h4>
          <table class="budget">
            <thead>
              <tr><th>Category</th><th>% of total</th><th>Notes</th></tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in proposal.plan.budget_skeleton" :key="i">
                <td>{{ row.category ?? '' }}</td>
                <td>{{ row.amount_pct ?? '' }}</td>
                <td>{{ row.notes ?? '' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <p v-if="proposal.plan.notes" class="notes">{{ proposal.plan.notes }}</p>
      </div>
    </div>
  </GlassPanel>
</template>

<style scoped>
.empty {
  padding: 2rem 0;
  text-align: center;
  color: var(--color-text-muted, #8e95a8);
  font-size: 0.9rem;
}

.plan__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.plan__meta {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-muted, #8e95a8);
}

.plan__status strong {
  color: var(--color-accent, #7aa2ff);
  text-transform: capitalize;
}

.plan__actions {
  display: flex;
  gap: 0.4rem;
}

.btn-primary,
.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.45rem 0.8rem;
  border-radius: 6px;
  font: inherit;
  font-size: 0.82rem;
  cursor: pointer;
  border: 1px solid transparent;
}

.btn-primary {
  background: var(--color-accent, #7aa2ff);
  color: #0b0f18;
  font-weight: 600;
}

.btn-primary:disabled,
.btn-ghost:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn-ghost {
  background: transparent;
  color: inherit;
  border-color: var(--color-border, rgba(255, 255, 255, 0.12));
}

h4 {
  margin: 1rem 0 0.4rem;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-muted, #8e95a8);
}

.sections {
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: item;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.sections li {
  counter-increment: item;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.06));
  border-radius: 8px;
  padding: 0.7rem 0.85rem;
  position: relative;
}

.sections li::before {
  content: counter(item);
  position: absolute;
  top: 0.7rem;
  left: -1.8rem;
  width: 1.3rem;
  height: 1.3rem;
  border-radius: 50%;
  background: rgba(122, 162, 255, 0.2);
  color: var(--color-accent, #7aa2ff);
  display: grid;
  place-items: center;
  font-size: 0.7rem;
  font-weight: 700;
}

.sections {
  padding-left: 1.8rem;
}

.sections__title {
  font-weight: 600;
  font-size: 0.9rem;
}

.sections__word-limit {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-accent, #7aa2ff);
  margin-top: 0.15rem;
}

.sections__guidance {
  margin: 0.3rem 0 0;
  font-size: 0.82rem;
  color: var(--color-text, inherit);
  line-height: 1.45;
}

.block ul {
  margin: 0;
  padding-left: 1.2rem;
  font-size: 0.83rem;
  line-height: 1.5;
}

.block ul.warn {
  color: #ffc460;
}

.budget {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.budget th,
.budget td {
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid var(--color-border, rgba(255, 255, 255, 0.06));
  text-align: left;
}

.budget th {
  font-weight: 600;
  color: var(--color-text-muted, #8e95a8);
}

.notes {
  margin: 1rem 0 0;
  padding: 0.6rem 0.8rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.06));
  border-radius: 8px;
  font-size: 0.82rem;
}
</style>

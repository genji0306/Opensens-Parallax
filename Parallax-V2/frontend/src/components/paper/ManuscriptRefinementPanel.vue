<script setup lang="ts">
import { ref } from 'vue'
import type {
  ApplyRefinementResult,
  DraftHistoryPayload,
  GroundedLiteratureReviewResult,
  RevertRefinementResult,
  SectionRefinementResult,
  VisualizationPlan,
} from '@/api/paperLab'
import {
  applyPaperRefinement,
  getDraftHistory,
  groundedLiteratureReview,
  refinePaperSection,
  revertPaperRefinement,
} from '@/api/paperLab'
import ActionButton from '@/components/shared/ActionButton.vue'

const props = defineProps<{
  uploadId: string
  visualizationPlan: VisualizationPlan | null
}>()

const refinementAction = ref('improve_introduction')
const literatureFocus = ref('literature review')
const loadingRefinement = ref(false)
const loadingLiterature = ref(false)
const applyingRefinement = ref(false)
const loadingHistory = ref(false)
const revertingRefinementId = ref<string | null>(null)
const refinement = ref<SectionRefinementResult | null>(null)
const literature = ref<GroundedLiteratureReviewResult | null>(null)
const appliedRefinement = ref<ApplyRefinementResult | null>(null)
const draftHistory = ref<DraftHistoryPayload | null>(null)
const revertedRefinement = ref<RevertRefinementResult | null>(null)
const feedback = ref<string | null>(null)

const refinementActions = [
  { value: 'improve_introduction', label: 'Improve Introduction' },
  { value: 'strengthen_literature_review', label: 'Strengthen Literature Review' },
  { value: 'rewrite_methods_for_clarity', label: 'Rewrite Methods for Clarity' },
  { value: 'connect_results_to_figures', label: 'Connect Results to Figures' },
  { value: 'prepare_rebuttal_oriented_revision', label: 'Prepare Rebuttal-Oriented Revision' },
]

async function runRefinement() {
  loadingRefinement.value = true
  feedback.value = null
  try {
    const res = await refinePaperSection(props.uploadId, refinementAction.value, props.visualizationPlan)
    refinement.value = res.data?.data ?? null
    feedback.value = `Refined section: ${refinement.value?.section ?? 'unknown'}`
  } finally {
    loadingRefinement.value = false
  }
}

async function loadHistory() {
  loadingHistory.value = true
  try {
    const res = await getDraftHistory(props.uploadId)
    draftHistory.value = res.data?.data ?? null
  } finally {
    loadingHistory.value = false
  }
}

async function runLiteratureReview() {
  loadingLiterature.value = true
  feedback.value = null
  try {
    const res = await groundedLiteratureReview(props.uploadId, literatureFocus.value)
    literature.value = res.data?.data ?? null
    feedback.value = literature.value?.ready
      ? 'All suggested citations are verified.'
      : `${literature.value?.unverified_count ?? 0} suggestions still need verification.`
  } finally {
    loadingLiterature.value = false
  }
}

async function applyRefinement() {
  if (!refinement.value) return
  applyingRefinement.value = true
  feedback.value = null
  try {
    const res = await applyPaperRefinement(props.uploadId, refinement.value)
    appliedRefinement.value = res.data?.data ?? null
    refinement.value = {
      ...refinement.value,
      applied: true,
    }
    feedback.value = `Applied refinement to ${appliedRefinement.value?.section ?? refinement.value.section}`
    await loadHistory()
  } finally {
    applyingRefinement.value = false
  }
}

async function revertRefinement(refinementId: string) {
  revertingRefinementId.value = refinementId
  feedback.value = null
  try {
    const res = await revertPaperRefinement(props.uploadId, refinementId)
    revertedRefinement.value = res.data?.data ?? null
    feedback.value = `Reverted refinement ${refinementId}`
    await loadHistory()
  } finally {
    revertingRefinementId.value = null
  }
}

void loadHistory()
</script>

<template>
  <section class="refinement-panel">
    <div class="refinement-panel__header">
      <div>
        <h4>Manuscript Refinement</h4>
        <p>PaperOrchestra-style section rewrites and grounded literature suggestions, scoped to the current manuscript.</p>
      </div>
    </div>

    <div v-if="feedback" class="refinement-panel__feedback">{{ feedback }}</div>

    <div class="refinement-panel__grid">
      <section class="card">
        <h5>Section Refinement</h5>
        <label class="field">
          <span>Action</span>
          <select v-model="refinementAction">
            <option v-for="item in refinementActions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
        </label>
        <ActionButton variant="secondary" size="sm" icon="edit_note" :loading="loadingRefinement" @click="runRefinement">
          Refine Section
        </ActionButton>

        <div v-if="refinement" class="result">
          <p><strong>{{ refinement.section }}</strong></p>
          <p>{{ refinement.diff.summary }}</p>
          <p><strong>Addressed:</strong> {{ refinement.addressed_recommendations.join(' | ') || '—' }}</p>
          <p><strong>Status:</strong> {{ refinement.applied ? 'applied to draft' : 'draft only' }}</p>
          <ActionButton
            variant="ghost"
            size="sm"
            icon="check_circle"
            :loading="applyingRefinement"
            :disabled="Boolean(refinement.applied)"
            @click="applyRefinement"
          >
            Apply to Draft
          </ActionButton>
          <details>
            <summary>Revised Text</summary>
            <pre>{{ refinement.revised_text }}</pre>
          </details>
          <details v-if="appliedRefinement">
            <summary>Applied Draft Snapshot</summary>
            <pre>{{ appliedRefinement.current_draft }}</pre>
          </details>
        </div>
      </section>

      <section class="card">
        <h5>Grounded Literature Review</h5>
        <label class="field">
          <span>Focus</span>
          <input v-model="literatureFocus" type="text" placeholder="e.g. battery benchmark" />
        </label>
        <ActionButton variant="secondary" size="sm" icon="menu_book" :loading="loadingLiterature" @click="runLiteratureReview">
          Find Verified Citations
        </ActionButton>

        <div v-if="literature" class="result">
          <p><strong>Ready:</strong> {{ literature.ready ? 'yes' : 'no' }}</p>
          <p><strong>Queries:</strong> {{ literature.queries.join(' | ') }}</p>
          <ul v-if="literature.suggestions.length" class="literature-list">
            <li v-for="item in literature.suggestions" :key="item.citation_id">
              <strong>{{ item.title }}</strong>
              <span> · {{ item.verified ? 'verified' : 'unverified' }} · {{ item.insertion_point }}</span>
            </li>
          </ul>
        </div>
      </section>
    </div>

    <section class="card">
      <div class="history-header">
        <h5>Draft History</h5>
        <ActionButton variant="ghost" size="sm" icon="refresh" :loading="loadingHistory" @click="loadHistory">
          Refresh History
        </ActionButton>
      </div>

      <div v-if="draftHistory?.applied_refinements?.length" class="history-group">
        <p class="history-title">Applied refinements</p>
        <ul class="history-list">
          <li v-for="item in draftHistory.applied_refinements.slice().reverse()" :key="item.refinement_id">
            <div class="history-item">
              <div>
                <strong>{{ item.section }}</strong> · {{ item.action }} · {{ item.applied_at }}
              </div>
              <ActionButton
                variant="ghost"
                size="sm"
                icon="undo"
                :loading="revertingRefinementId === item.refinement_id"
                @click="revertRefinement(item.refinement_id)"
              >
                Revert
              </ActionButton>
            </div>
          </li>
        </ul>
      </div>

      <div v-if="draftHistory?.grounded_literature_history?.length" class="history-group">
        <p class="history-title">Grounded literature runs</p>
        <ul class="history-list">
          <li v-for="item in draftHistory.grounded_literature_history.slice().reverse()" :key="`${item.focus}-${item.created_at}`">
            <strong>{{ item.focus }}</strong> · {{ item.verified_count ?? 0 }}/{{ item.suggestion_count }} verified · {{ item.ready ? 'ready' : 'needs review' }}
          </li>
        </ul>
      </div>

      <p v-if="!draftHistory?.applied_refinements?.length && !draftHistory?.grounded_literature_history?.length" class="empty-state">
        No persisted refinement or literature history yet.
      </p>

      <details v-if="revertedRefinement" class="result">
        <summary>Last Reverted Draft Snapshot</summary>
        <pre>{{ revertedRefinement.current_draft }}</pre>
      </details>
    </section>
  </section>
</template>

<style scoped>
.refinement-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.refinement-panel__header h4,
.card h5 {
  margin: 0;
  color: var(--text-primary);
}

.refinement-panel__header p,
.refinement-panel__feedback,
.result,
.field span {
  font-size: 12px;
  color: var(--text-secondary);
}

.refinement-panel__feedback {
  padding: 12px 14px;
  border-radius: var(--radius-md);
  border: 1px solid rgba(59, 130, 246, 0.2);
  background: rgba(59, 130, 246, 0.08);
}

.refinement-panel__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-secondary);
  background: var(--bg-secondary);
}

.history-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field select,
.field input {
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  background: rgba(0, 0, 0, 0.2);
  color: var(--text-primary);
  padding: 10px 12px;
  font: inherit;
}

.result p {
  margin: 0;
}

.result pre {
  margin: 8px 0 0;
  padding: 12px;
  white-space: pre-wrap;
  border-radius: var(--radius-md);
  background: rgba(0, 0, 0, 0.22);
}

.literature-list {
  margin: 8px 0 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.history-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-title,
.empty-state {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.history-list {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 12px;
}

.history-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

@media (max-width: 1080px) {
  .refinement-panel__grid {
    grid-template-columns: 1fr;
  }
}
</style>

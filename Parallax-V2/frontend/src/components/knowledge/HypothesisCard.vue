<script setup lang="ts">
/**
 * HypothesisCard — Structured contribution hypothesis display (Sprint 7.1).
 */

import { ref, watch } from 'vue'
import { buildHypothesis, getKnowledgeArtifact } from '@/api/ais'
import type { KnowledgeArtifact, KnowledgeHypothesis } from '@/api/ais'

const props = defineProps<{ runId: string }>()

const hypothesis = ref<KnowledgeHypothesis | null>(null)
const context = ref<Record<string, number>>({})
const loading = ref(false)
const error = ref<string | null>(null)

function buildSupportingContext(artifact: KnowledgeArtifact | null | undefined): Record<string, number> {
  if (!artifact) return {}

  const noveltyAssessments = Array.isArray(artifact.novelty_assessments) ? artifact.novelty_assessments : []
  return {
    claims: Array.isArray(artifact.claims) ? artifact.claims.length : 0,
    gaps: Array.isArray(artifact.gaps) ? artifact.gaps.length : 0,
    novel_claims: noveltyAssessments.filter(item => Number(item.novelty_score ?? 0) >= 0.7).length,
  }
}

async function hydrateHypothesis() {
  if (!props.runId) {
    hypothesis.value = null
    context.value = {}
    return
  }

  try {
    const res = await getKnowledgeArtifact(props.runId)
    const artifact = res.data?.data ?? null
    hypothesis.value = artifact?.hypothesis ?? null
    context.value = buildSupportingContext(artifact)
  } catch {
    hypothesis.value = null
    context.value = {}
  }
}

async function generate() {
  if (!props.runId) return
  loading.value = true
  error.value = null
  try {
    const res = await buildHypothesis(props.runId)
    const data = res.data?.data
    hypothesis.value = data?.hypothesis ?? null
    context.value = data?.supporting_context ?? {}
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to build hypothesis'
  } finally {
    loading.value = false
  }
}

watch(() => props.runId, () => {
  hydrateHypothesis()
}, { immediate: true })
</script>

<template>
  <div class="hypothesis-card">
    <div class="hypothesis-card__header">
      <h5 class="detail-heading">Contribution Hypothesis</h5>
      <button v-if="!hypothesis" class="hypothesis-card__btn" :disabled="loading" @click="generate">
        {{ loading ? 'Building...' : 'Build Hypothesis' }}
      </button>
    </div>

    <div v-if="error" class="hypothesis-card__error">{{ error }}</div>

    <template v-if="hypothesis">
      <div class="hypothesis-card__section">
        <span class="hypothesis-card__label">Problem Statement</span>
        <p class="hypothesis-card__text">{{ hypothesis.problem_statement }}</p>
      </div>

      <div class="hypothesis-card__section">
        <span class="hypothesis-card__label">Contribution</span>
        <p class="hypothesis-card__text hypothesis-card__text--highlight">{{ hypothesis.contribution }}</p>
      </div>

      <div class="hypothesis-card__section">
        <span class="hypothesis-card__label">Differentiators</span>
        <ul class="hypothesis-card__list">
          <li v-for="(d, i) in hypothesis.differentiators" :key="i">{{ d }}</li>
        </ul>
      </div>

      <div class="hypothesis-card__section">
        <span class="hypothesis-card__label">Predicted Impact</span>
        <p class="hypothesis-card__text">{{ hypothesis.predicted_impact }}</p>
      </div>

      <div class="hypothesis-card__context">
        <span>Based on {{ context.claims ?? 0 }} claims, {{ context.gaps ?? 0 }} gaps, {{ context.novel_claims ?? 0 }} novel findings</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.hypothesis-card { display: flex; flex-direction: column; gap: 12px; }
.hypothesis-card__header { display: flex; justify-content: space-between; align-items: center; }
.detail-heading { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); margin: 0; }
.hypothesis-card__btn {
  padding: 5px 12px; font-size: 11px; font-weight: 500; color: var(--os-brand);
  background: color-mix(in srgb, var(--os-brand) 10%, transparent);
  border: 1px solid var(--os-brand); border-radius: var(--radius-md); cursor: pointer;
}
.hypothesis-card__btn:disabled { opacity: 0.5; cursor: not-allowed; }
.hypothesis-card__error { font-size: 12px; color: var(--danger, #ef4444); }

.hypothesis-card__section {
  padding: 10px 12px; background: var(--bg-secondary);
  border: 1px solid var(--border-secondary); border-radius: var(--radius-md);
}
.hypothesis-card__label {
  display: block; font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--text-tertiary); margin-bottom: 4px;
}
.hypothesis-card__text { font-size: 12px; line-height: 1.5; color: var(--text-primary); margin: 0; }
.hypothesis-card__text--highlight { font-weight: 500; color: var(--os-brand); }
.hypothesis-card__list {
  margin: 0; padding-left: 16px; font-size: 12px; line-height: 1.6; color: var(--text-primary);
}
.hypothesis-card__context {
  font-size: 10px; color: var(--text-tertiary); text-align: right;
}
</style>

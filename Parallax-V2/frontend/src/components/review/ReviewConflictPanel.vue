<script setup lang="ts">
/**
 * ReviewConflictPanel — Display conflicts between reviewers and revision themes (Sprint 10).
 */

import { ref, watch } from 'vue'
import { detectConflicts, getRevisionHistory } from '@/api/ais'
import type { ReviewConflict, RevisionTheme } from '@/api/ais'

const props = defineProps<{ runId: string }>()

const conflicts = ref<ReviewConflict[]>([])
const themes = ref<RevisionTheme[]>([])
const stats = ref<{ conflict_count: number; theme_count: number; critical_themes: number } | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

function applyConflictState(nextConflicts: ReviewConflict[], nextThemes: RevisionTheme[]) {
  conflicts.value = nextConflicts
  themes.value = nextThemes
  if (!nextConflicts.length && !nextThemes.length) {
    stats.value = null
    return
  }
  stats.value = {
    conflict_count: nextConflicts.length,
    theme_count: nextThemes.length,
    critical_themes: nextThemes.filter(theme => theme.priority <= 2 && theme.impact === 'high').length,
  }
}

async function hydrateConflictState() {
  if (!props.runId) {
    applyConflictState([], [])
    return
  }

  try {
    const res = await getRevisionHistory(props.runId)
    const rounds = res.data?.data?.rounds ?? []
    const latest = Array.isArray(rounds) && rounds.length ? rounds[rounds.length - 1] : null
    applyConflictState(latest?.conflicts ?? [], latest?.themes ?? [])
  } catch {
    applyConflictState([], [])
  }
}

async function analyze() {
  if (!props.runId) return
  loading.value = true
  error.value = null
  try {
    const res = await detectConflicts(props.runId)
    const data = res.data?.data
    applyConflictState(data?.conflicts ?? [], data?.themes ?? [])
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Analysis failed'
  } finally {
    loading.value = false
  }
}

watch(() => props.runId, () => {
  hydrateConflictState()
}, { immediate: true })

function severityColor(impact: string): string {
  return impact === 'high' ? 'var(--danger, #ef4444)' : impact === 'medium' ? 'var(--warning, #f59e0b)' : 'var(--text-tertiary)'
}
</script>

<template>
  <div class="conflict-panel">
    <div class="conflict-panel__header">
      <h5 class="detail-heading">Conflicts & Themes</h5>
      <button v-if="!stats" class="conflict-panel__btn" :disabled="loading" @click="analyze">
        {{ loading ? 'Analyzing...' : 'Analyze' }}
      </button>
    </div>

    <div v-if="error" class="conflict-panel__error">{{ error }}</div>

    <template v-if="stats">
      <div v-if="conflicts.length > 0" class="conflict-panel__conflicts">
        <h6 class="conflict-panel__subtitle">Reviewer Conflicts ({{ conflicts.length }})</h6>
        <div v-for="cf in conflicts" :key="cf.conflict_id" class="conflict-card">
          <div class="conflict-card__header">
            <span class="conflict-card__vs">{{ cf.reviewer_a }} vs {{ cf.reviewer_b }}</span>
          </div>
          <p class="conflict-card__desc">{{ cf.description }}</p>
          <p class="conflict-card__resolution">{{ cf.resolution_suggestion }}</p>
        </div>
      </div>

      <div v-if="themes.length > 0" class="conflict-panel__themes">
        <h6 class="conflict-panel__subtitle">Revision Themes ({{ themes.length }})</h6>
        <div v-for="th in themes" :key="th.theme_id" class="theme-card">
          <div class="theme-card__header">
            <span class="theme-card__priority font-mono">P{{ th.priority }}</span>
            <span class="theme-card__title">{{ th.title }}</span>
            <span class="theme-card__impact" :style="{ color: severityColor(th.impact) }">{{ th.impact }}</span>
          </div>
          <p class="theme-card__desc">{{ th.description }}</p>
          <p class="theme-card__action">{{ th.suggested_action }}</p>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.conflict-panel { display: flex; flex-direction: column; gap: 12px; }
.conflict-panel__header { display: flex; justify-content: space-between; align-items: center; }
.detail-heading { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); margin: 0; }
.conflict-panel__btn {
  padding: 5px 12px; font-size: 11px; font-weight: 500; color: var(--os-brand);
  background: color-mix(in srgb, var(--os-brand) 10%, transparent);
  border: 1px solid var(--os-brand); border-radius: var(--radius-md); cursor: pointer;
}
.conflict-panel__btn:disabled { opacity: 0.5; cursor: not-allowed; }
.conflict-panel__error { font-size: 12px; color: var(--danger, #ef4444); }
.conflict-panel__subtitle { font-size: 11px; font-weight: 600; color: var(--text-secondary); margin: 0 0 6px; }

.conflict-card, .theme-card {
  padding: 10px 12px; background: var(--bg-secondary);
  border: 1px solid var(--border-secondary); border-radius: var(--radius-md); margin-bottom: 6px;
}
.conflict-card__header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.conflict-card__vs { font-size: 10px; font-weight: 600; text-transform: uppercase; color: var(--danger, #ef4444); }
.conflict-card__desc { font-size: 12px; color: var(--text-primary); margin: 0 0 4px; line-height: 1.4; }
.conflict-card__resolution { font-size: 11px; color: var(--text-tertiary); margin: 0; font-style: italic; }

.theme-card__header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.theme-card__priority { font-size: 10px; font-weight: 700; color: var(--os-brand); }
.theme-card__title { font-size: 12px; font-weight: 500; color: var(--text-primary); flex: 1; }
.theme-card__impact { font-size: 10px; font-weight: 600; text-transform: uppercase; }
.theme-card__desc { font-size: 12px; color: var(--text-secondary); margin: 0 0 4px; line-height: 1.4; }
.theme-card__action { font-size: 11px; color: var(--text-tertiary); margin: 0; }
</style>

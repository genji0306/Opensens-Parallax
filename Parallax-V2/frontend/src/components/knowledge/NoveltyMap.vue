<script setup lang="ts">
/**
 * NoveltyMap — Heatmap visualization of claim novelty (Sprint 6.1).
 * Shows novel (green) vs well-covered (gray) zones.
 */

import { ref, watch } from 'vue'
import { getKnowledgeArtifact, mapNovelty } from '@/api/ais'
import type { KnowledgeArtifact, NoveltyMapData } from '@/api/ais'

const props = defineProps<{ runId: string }>()

const data = ref<NoveltyMapData | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

function buildNoveltyMap(artifact: KnowledgeArtifact | null | undefined): NoveltyMapData | null {
  if (!artifact) return null

  const claims = Array.isArray(artifact.claims) ? artifact.claims : []
  const assessments = Array.isArray(artifact.novelty_assessments) ? artifact.novelty_assessments : []
  if (!assessments.length) return null

  const claimById = new Map(claims.map(claim => [claim.claim_id, claim]))
  const heatmap = assessments.map((assessment) => {
    const score = Number(assessment.novelty_score ?? 0)
    return {
      claim_id: assessment.claim_id,
      text: claimById.get(assessment.claim_id)?.text ?? '',
      novelty_score: score,
      zone: score >= 0.7 ? 'novel' : score >= 0.3 ? 'partial' : 'covered',
      explanation: assessment.explanation ?? '',
    } as NoveltyMapData['heatmap'][number]
  })

  const scores = heatmap.map(item => item.novelty_score)
  return {
    assessments,
    heatmap,
    stats: {
      avg_novelty: scores.length ? Number((scores.reduce((sum, score) => sum + score, 0) / scores.length).toFixed(2)) : 0,
      novel_count: heatmap.filter(item => item.zone === 'novel').length,
      covered_count: heatmap.filter(item => item.zone === 'covered').length,
    },
  }
}

async function hydrateNoveltyMap() {
  if (!props.runId) {
    data.value = null
    return
  }

  try {
    const res = await getKnowledgeArtifact(props.runId)
    data.value = buildNoveltyMap(res.data?.data ?? null)
  } catch {
    data.value = null
  }
}

async function runNoveltyMap() {
  if (!props.runId) return
  loading.value = true
  error.value = null
  try {
    const res = await mapNovelty(props.runId)
    data.value = res.data?.data ?? null
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to map novelty'
  } finally {
    loading.value = false
  }
}

watch(() => props.runId, () => {
  hydrateNoveltyMap()
}, { immediate: true })

function zoneColor(zone: string): string {
  return zone === 'novel' ? 'var(--success, #22c55e)'
    : zone === 'partial' ? 'var(--warning, #f59e0b)'
    : 'var(--text-tertiary)'
}

function scoreBg(score: number): string {
  if (score >= 0.7) return 'color-mix(in srgb, var(--success, #22c55e) 15%, transparent)'
  if (score >= 0.3) return 'color-mix(in srgb, var(--warning, #f59e0b) 15%, transparent)'
  return 'var(--bg-secondary)'
}
</script>

<template>
  <div class="novelty-map">
    <div class="novelty-map__header">
      <h5 class="detail-heading">Novelty Map</h5>
      <button v-if="!data" class="novelty-map__btn" :disabled="loading" @click="runNoveltyMap">
        <span v-if="loading" class="material-symbols-outlined novelty-map__spinner">progress_activity</span>
        {{ loading ? 'Analyzing...' : 'Map Novelty' }}
      </button>
    </div>

    <div v-if="error" class="novelty-map__error">{{ error }}</div>

    <template v-if="data">
      <div class="novelty-map__stats">
        <span>Avg: <strong>{{ (data.stats.avg_novelty * 100).toFixed(0) }}%</strong></span>
        <span class="novelty-map__stat-novel">{{ data.stats.novel_count }} novel</span>
        <span class="novelty-map__stat-covered">{{ data.stats.covered_count }} covered</span>
      </div>

      <div class="novelty-map__grid">
        <div
          v-for="item in data.heatmap"
          :key="item.claim_id"
          class="novelty-map__cell"
          :style="{ background: scoreBg(item.novelty_score) }"
        >
          <div class="novelty-map__cell-header">
            <span class="novelty-map__zone" :style="{ color: zoneColor(item.zone) }">
              {{ item.zone }}
            </span>
            <span class="novelty-map__score font-mono">
              {{ (item.novelty_score * 100).toFixed(0) }}%
            </span>
          </div>
          <p class="novelty-map__claim-text">{{ item.text }}</p>
          <p class="novelty-map__explanation">{{ item.explanation }}</p>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.novelty-map { display: flex; flex-direction: column; gap: 12px; }
.novelty-map__header { display: flex; justify-content: space-between; align-items: center; }
.detail-heading { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); margin: 0; }
.novelty-map__btn {
  display: inline-flex; align-items: center; gap: 4px; padding: 5px 12px;
  font-size: 11px; font-weight: 500; color: var(--os-brand); background: color-mix(in srgb, var(--os-brand) 10%, transparent);
  border: 1px solid var(--os-brand); border-radius: var(--radius-md); cursor: pointer;
}
.novelty-map__btn:disabled { opacity: 0.5; cursor: not-allowed; }
.novelty-map__spinner { font-size: 14px; animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.novelty-map__error { font-size: 12px; color: var(--danger, #ef4444); }
.novelty-map__stats { display: flex; gap: 12px; font-size: 11px; color: var(--text-secondary); }
.novelty-map__stat-novel { color: var(--success, #22c55e); }
.novelty-map__stat-covered { color: var(--text-tertiary); }
.novelty-map__grid { display: flex; flex-direction: column; gap: 6px; }
.novelty-map__cell {
  padding: 10px 12px; border: 1px solid var(--border-secondary); border-radius: var(--radius-md);
}
.novelty-map__cell-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.novelty-map__zone { font-size: 10px; font-weight: 600; text-transform: uppercase; }
.novelty-map__score { font-size: 11px; color: var(--text-secondary); }
.novelty-map__claim-text { font-size: 12px; font-weight: 500; color: var(--text-primary); margin: 0 0 4px; line-height: 1.4; }
.novelty-map__explanation { font-size: 11px; color: var(--text-tertiary); margin: 0; line-height: 1.4; }
</style>

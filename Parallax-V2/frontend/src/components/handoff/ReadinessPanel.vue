<script setup lang="ts">
/**
 * ReadinessPanel — Platform readiness scoring and handoff (Sprint 22).
 */

import { ref, onMounted } from 'vue'

const props = defineProps<{ runId: string }>()

const data = ref<Record<string, unknown> | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function fetchReadiness() {
  if (!props.runId) return
  loading.value = true
  try {
    const { default: service } = await import('@/api/client')
    const res = await service.get(`/api/research/ais/${props.runId}/readiness`)
    data.value = res.data?.data ?? null
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load readiness'
  } finally {
    loading.value = false
  }
}

onMounted(fetchReadiness)

function statusColor(status: string): string {
  return status === 'ready' ? 'var(--success, #22c55e)' : status === 'partial' ? 'var(--warning, #f59e0b)' : 'var(--text-tertiary)'
}
</script>

<template>
  <div class="readiness-panel">
    <h5 class="detail-heading">Platform Readiness</h5>

    <div v-if="loading" class="readiness-panel__loading">Loading...</div>
    <div v-else-if="error" class="readiness-panel__error">{{ error }}</div>

    <template v-if="data">
      <div class="readiness-panel__overall">
        Overall: <strong>{{ data.overall_readiness }}%</strong>
        <span v-if="data.recommended" class="readiness-panel__rec">
          Recommended: {{ (data.platforms as Record<string, Record<string, unknown>>)?.[data.recommended as string]?.name }}
        </span>
      </div>

      <div class="readiness-panel__grid">
        <div
          v-for="(platform, key) in (data.platforms as Record<string, Record<string, unknown>>)"
          :key="key"
          class="platform-card"
        >
          <div class="platform-card__header">
            <span class="platform-card__name">{{ platform.name }}</span>
            <span class="platform-card__score font-mono" :style="{ color: statusColor(platform.status as string) }">
              {{ platform.readiness_score }}%
            </span>
          </div>
          <p class="platform-card__desc">{{ platform.description }}</p>
          <div class="platform-card__reqs">
            <span
              v-for="req in (platform.met_requirements as string[])"
              :key="req"
              class="platform-card__req platform-card__req--met"
            >{{ req.replace(/_/g, ' ') }}</span>
            <span
              v-for="req in (platform.missing_requirements as string[])"
              :key="req"
              class="platform-card__req platform-card__req--missing"
            >{{ req.replace(/_/g, ' ') }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.readiness-panel { display: flex; flex-direction: column; gap: 12px; }
.detail-heading { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); margin: 0; }
.readiness-panel__loading, .readiness-panel__error { font-size: 12px; color: var(--text-tertiary); }
.readiness-panel__error { color: var(--danger, #ef4444); }
.readiness-panel__overall { font-size: 12px; color: var(--text-secondary); }
.readiness-panel__rec { margin-left: 8px; color: var(--os-brand); font-weight: 500; }

.readiness-panel__grid { display: flex; flex-direction: column; gap: 8px; }
.platform-card { padding: 10px 12px; background: var(--bg-secondary); border: 1px solid var(--border-secondary); border-radius: var(--radius-md); }
.platform-card__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.platform-card__name { font-size: 12px; font-weight: 500; color: var(--text-primary); }
.platform-card__score { font-size: 12px; }
.platform-card__desc { font-size: 11px; color: var(--text-tertiary); margin: 0 0 6px; }
.platform-card__reqs { display: flex; flex-wrap: wrap; gap: 4px; }
.platform-card__req {
  font-size: 9px; font-weight: 600; text-transform: uppercase; padding: 2px 6px;
  border-radius: var(--radius-pill, 999px);
}
.platform-card__req--met { color: var(--success, #22c55e); background: color-mix(in srgb, var(--success, #22c55e) 12%, transparent); }
.platform-card__req--missing { color: var(--text-tertiary); background: var(--bg-primary); border: 1px dashed var(--border-secondary); }
</style>

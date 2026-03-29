<script setup lang="ts">
/**
 * ConsistencyReport — Text-vs-figure contradiction display (Sprint 14).
 */
import { ref } from 'vue'

const props = defineProps<{ data: Record<string, unknown> | null }>()

const contradictions = ref(
  (props.data?.contradictions as Array<Record<string, unknown>>) ?? []
)
const score = ref((props.data?.consistency_score as number) ?? 0)
const summary = ref((props.data?.summary as string) ?? '')
</script>

<template>
  <div class="consistency-report">
    <div class="consistency-report__header">
      <h5 class="detail-heading">Consistency Report</h5>
      <span class="consistency-report__score font-mono">{{ score }}/10</span>
    </div>
    <p v-if="summary" class="consistency-report__summary">{{ summary }}</p>
    <div v-if="contradictions.length" class="consistency-report__list">
      <div v-for="(c, i) in contradictions" :key="i" class="contradiction-card">
        <div class="contradiction-card__header">
          <span class="contradiction-card__type">{{ (c.type as string || '').replace(/_/g, ' ') }}</span>
          <span class="contradiction-card__severity" :data-severity="c.severity">{{ c.severity }}</span>
        </div>
        <p class="contradiction-card__desc">{{ c.description }}</p>
        <p v-if="c.recommendation" class="contradiction-card__rec">{{ c.recommendation }}</p>
      </div>
    </div>
    <div v-else class="consistency-report__empty">No contradictions detected.</div>
  </div>
</template>

<style scoped>
.consistency-report { display: flex; flex-direction: column; gap: 10px; }
.consistency-report__header { display: flex; justify-content: space-between; align-items: center; }
.detail-heading { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); margin: 0; }
.consistency-report__score { font-size: 12px; color: var(--text-secondary); }
.consistency-report__summary { font-size: 12px; color: var(--text-primary); margin: 0; line-height: 1.4; }
.consistency-report__list { display: flex; flex-direction: column; gap: 6px; }
.contradiction-card { padding: 10px 12px; background: var(--bg-secondary); border: 1px solid var(--border-secondary); border-radius: var(--radius-md); }
.contradiction-card__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.contradiction-card__type { font-size: 10px; font-weight: 600; text-transform: capitalize; color: var(--text-secondary); }
.contradiction-card__severity { font-size: 9px; font-weight: 700; text-transform: uppercase; }
.contradiction-card__severity[data-severity="critical"] { color: var(--danger, #ef4444); }
.contradiction-card__severity[data-severity="major"] { color: var(--warning, #f59e0b); }
.contradiction-card__desc { font-size: 12px; color: var(--text-primary); margin: 0 0 4px; line-height: 1.4; }
.contradiction-card__rec { font-size: 11px; color: var(--text-tertiary); margin: 0; font-style: italic; }
.consistency-report__empty { font-size: 12px; color: var(--text-tertiary); text-align: center; padding: 16px; }
</style>

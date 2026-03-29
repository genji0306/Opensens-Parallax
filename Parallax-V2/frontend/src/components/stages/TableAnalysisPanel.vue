<script setup lang="ts">
/**
 * TableAnalysisPanel — Table quality and anomaly display (Sprint 15).
 */

const props = defineProps<{ data: Record<string, unknown> | null }>()

const tables = ((props.data?.tables as Array<Record<string, unknown>>) ?? [])
const stats = (props.data?.stats as Record<string, unknown>) ?? {}
</script>

<template>
  <div class="table-analysis">
    <div class="table-analysis__header">
      <h5 class="detail-heading">Table Analysis</h5>
      <span v-if="stats.total_tables" class="table-analysis__stat font-mono">
        {{ stats.total_tables }} tables, avg {{ stats.avg_quality }}/10
      </span>
    </div>

    <div v-if="tables.length" class="table-analysis__list">
      <div v-for="(t, i) in tables" :key="i" class="table-card">
        <div class="table-card__header">
          <span class="table-card__label">{{ (t as Record<string, unknown>).label || `Table ${i + 1}` }}</span>
          <span class="table-card__score font-mono">{{ (t as Record<string, unknown>).quality_score }}/10</span>
        </div>
        <p class="table-card__summary">{{ (t as Record<string, unknown>).summary }}</p>
        <div v-for="(a, j) in ((t as Record<string, unknown>).anomalies as Array<Record<string, unknown>> || [])" :key="j" class="table-card__anomaly">
          <span class="table-card__anomaly-type">{{ (a.type as string || '').replace(/_/g, ' ') }}</span>
          <span>{{ a.description }}</span>
        </div>
      </div>
    </div>
    <div v-else class="table-analysis__empty">No table analysis data.</div>
  </div>
</template>

<style scoped>
.table-analysis { display: flex; flex-direction: column; gap: 10px; }
.table-analysis__header { display: flex; justify-content: space-between; align-items: center; }
.detail-heading { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); margin: 0; }
.table-analysis__stat { font-size: 11px; color: var(--text-tertiary); }
.table-analysis__list { display: flex; flex-direction: column; gap: 8px; }
.table-card { padding: 10px 12px; background: var(--bg-secondary); border: 1px solid var(--border-secondary); border-radius: var(--radius-md); }
.table-card__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.table-card__label { font-size: 12px; font-weight: 500; color: var(--text-primary); }
.table-card__score { font-size: 11px; color: var(--text-secondary); }
.table-card__summary { font-size: 12px; color: var(--text-secondary); margin: 0 0 6px; line-height: 1.4; }
.table-card__anomaly { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--text-secondary); padding: 2px 0; }
.table-card__anomaly-type { font-size: 9px; font-weight: 600; text-transform: uppercase; color: var(--warning, #f59e0b); }
.table-analysis__empty { font-size: 12px; color: var(--text-tertiary); text-align: center; padding: 16px; }
</style>

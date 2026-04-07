<script setup lang="ts">
/**
 * FigureCritiquePanel — Automated figure critique display (Sprint 13).
 */
import { ref } from 'vue'

const props = defineProps<{ runId?: string; result: Record<string, unknown> }>()

// Display critique results from the result prop
const critiqueData = ref<Record<string, unknown> | null>(
  props.result?.figure_critique as Record<string, unknown> | null
)
</script>

<template>
  <div class="figure-critique">
    <h5 class="detail-heading">Figure Critique</h5>
    <div v-if="critiqueData" class="figure-critique__results">
      <div
        v-for="(fig, i) in (critiqueData.figures as Array<Record<string, unknown>> || [])"
        :key="i"
        class="figure-critique__card"
      >
        <div class="figure-critique__header">
          <span class="figure-critique__type">{{ fig.figure_type }}</span>
          <span class="figure-critique__score font-mono">{{ fig.overall_quality }}/10</span>
        </div>
        <p class="figure-critique__summary">{{ fig.summary }}</p>
        <div v-for="issue in (fig.issues as Array<Record<string, unknown>> || [])" :key="(issue as Record<string, unknown>).description as string" class="figure-critique__issue">
          <span class="figure-critique__severity" :data-severity="issue.severity">{{ issue.severity }}</span>
          <span>{{ issue.description }}</span>
        </div>
      </div>
    </div>
    <div v-else class="figure-critique__empty">No figure critique data available.</div>
  </div>
</template>

<style scoped>
.figure-critique { display: flex; flex-direction: column; gap: 10px; }
.detail-heading { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); margin: 0; }
.figure-critique__results { display: flex; flex-direction: column; gap: 8px; }
.figure-critique__card { padding: 10px 12px; background: var(--bg-secondary); border: 1px solid var(--border-secondary); border-radius: var(--radius-md); }
.figure-critique__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.figure-critique__type { font-size: 10px; font-weight: 600; text-transform: uppercase; color: var(--os-brand); }
.figure-critique__score { font-size: 12px; color: var(--text-secondary); }
.figure-critique__summary { font-size: 12px; color: var(--text-primary); margin: 0 0 6px; line-height: 1.4; }
.figure-critique__issue { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--text-secondary); padding: 2px 0; }
.figure-critique__severity { font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 1px 5px; border-radius: var(--radius-pill, 999px); }
.figure-critique__severity[data-severity="critical"] { color: var(--danger, #ef4444); background: color-mix(in srgb, var(--danger, #ef4444) 12%, transparent); }
.figure-critique__severity[data-severity="major"] { color: var(--warning, #f59e0b); background: color-mix(in srgb, var(--warning, #f59e0b) 12%, transparent); }
.figure-critique__severity[data-severity="minor"] { color: var(--text-tertiary); background: var(--bg-primary); }
.figure-critique__empty { font-size: 12px; color: var(--text-tertiary); text-align: center; padding: 16px; }
</style>

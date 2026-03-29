<script setup lang="ts">
/**
 * GrantPreview — Grant concept note preview (Sprint 17-18).
 */

const props = defineProps<{ data: Record<string, unknown> | null }>()

const title = (props.data?.title as string) ?? ''
const summary = (props.data?.executive_summary as string) ?? ''
const trl = (props.data?.innovation_trl as Record<string, unknown>) ?? {}
const outcomes = (props.data?.expected_outcomes as string[]) ?? []
const timeline = (props.data?.timeline_months as number) ?? 0
</script>

<template>
  <div v-if="data" class="grant-preview">
    <h5 class="grant-preview__title">{{ title }}</h5>
    <p class="grant-preview__summary">{{ summary }}</p>

    <div v-if="trl.current_trl" class="grant-preview__trl">
      <span class="grant-preview__label">TRL</span>
      <span class="font-mono">{{ trl.current_trl }} → {{ trl.target_trl }}</span>
      <span class="grant-preview__hint">{{ trl.trl_justification }}</span>
    </div>

    <div v-if="outcomes.length" class="grant-preview__outcomes">
      <span class="grant-preview__label">Expected Outcomes</span>
      <ul><li v-for="(o, i) in outcomes" :key="i">{{ o }}</li></ul>
    </div>

    <div v-if="timeline" class="grant-preview__meta">
      Timeline: {{ timeline }} months
    </div>
  </div>
</template>

<style scoped>
.grant-preview { display: flex; flex-direction: column; gap: 10px; padding: 12px; background: var(--bg-secondary); border: 1px solid var(--border-secondary); border-radius: var(--radius-md); }
.grant-preview__title { font-size: 14px; font-weight: 600; color: var(--text-primary); margin: 0; }
.grant-preview__summary { font-size: 12px; color: var(--text-secondary); margin: 0; line-height: 1.5; }
.grant-preview__trl { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.grant-preview__label { font-size: 10px; font-weight: 600; text-transform: uppercase; color: var(--text-tertiary); }
.grant-preview__hint { font-size: 11px; color: var(--text-tertiary); }
.grant-preview__outcomes ul { margin: 4px 0 0; padding-left: 16px; font-size: 12px; color: var(--text-primary); line-height: 1.5; }
.grant-preview__meta { font-size: 11px; color: var(--text-tertiary); }
</style>

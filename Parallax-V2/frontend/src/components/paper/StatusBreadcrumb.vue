<script setup lang="ts">
// Maps upload status strings → pipeline breadcrumb step index
// Steps: uploaded → reviewing → revised → specialist → complete

const props = defineProps<{
  status: string
}>()

interface Step {
  key: string
  label: string
  icon: string
}

const steps: Step[] = [
  { key: 'uploaded', label: 'Uploaded', icon: 'upload_file' },
  { key: 'reviewing', label: 'Review', icon: 'rate_review' },
  { key: 'revised', label: 'Revised', icon: 'edit_document' },
  { key: 'specialist', label: 'Specialist', icon: 'lab_research' },
  { key: 'complete', label: 'Complete', icon: 'check_circle' },
]

function activeIndex(): number {
  const s = props.status
  if (['completed', 'gap_filled', 'specialist_complete'].includes(s)) return 4
  if (s === 'specialist_running') return 3
  if (['review_complete', 'revised'].includes(s)) return 2
  if (['reviewing', 'review_failed'].includes(s)) return 1
  return 0 // pending, uploaded, parsed, etc.
}

function stepState(idx: number): 'done' | 'active' | 'pending' | 'error' {
  const active = activeIndex()
  const s = props.status
  if (idx < active) return 'done'
  if (idx === active) {
    if (s === 'review_failed') return 'error'
    return 'active'
  }
  return 'pending'
}
</script>

<template>
  <div class="status-bc">
    <template v-for="(step, idx) in steps" :key="step.key">
      <!-- Step node -->
      <div class="sbc-step" :class="`sbc-step--${stepState(idx)}`">
        <div class="sbc-node">
          <span class="material-symbols-outlined sbc-icon">{{ step.icon }}</span>
        </div>
        <span class="sbc-label">{{ step.label }}</span>
      </div>
      <!-- Connector (not after last step) -->
      <div v-if="idx < steps.length - 1" class="sbc-connector" :class="{ 'sbc-connector--done': stepState(idx) === 'done' }" />
    </template>
  </div>
</template>

<style scoped>
.status-bc {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 10px 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  overflow-x: auto;
}

/* Step */
.sbc-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

/* Node circle */
.sbc-node {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--border-secondary);
  background: var(--bg-tertiary);
  transition: all var(--transition-fast);
}

.sbc-icon {
  font-size: 14px;
  color: var(--text-tertiary);
}

/* States */
.sbc-step--done .sbc-node {
  border-color: var(--success);
  background: rgba(34, 197, 94, 0.1);
}
.sbc-step--done .sbc-icon {
  color: var(--success);
}

.sbc-step--active .sbc-node {
  border-color: var(--os-brand);
  background: var(--os-brand-light);
  box-shadow: 0 0 0 3px var(--os-brand-subtle);
}
.sbc-step--active .sbc-icon {
  color: var(--os-brand);
}

.sbc-step--error .sbc-node {
  border-color: var(--error);
  background: rgba(239, 68, 68, 0.1);
}
.sbc-step--error .sbc-icon {
  color: var(--error);
}

/* Label */
.sbc-label {
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.sbc-step--done .sbc-label {
  color: var(--success);
}

.sbc-step--active .sbc-label {
  color: var(--os-brand);
}

.sbc-step--error .sbc-label {
  color: var(--error);
}

/* Connector line */
.sbc-connector {
  flex: 1;
  height: 2px;
  min-width: 20px;
  background: var(--border-secondary);
  margin: 0 4px;
  margin-bottom: 14px; /* align with icon row, above label */
  border-radius: 1px;
  transition: background var(--transition-fast);
}

.sbc-connector--done {
  background: var(--success);
}
</style>

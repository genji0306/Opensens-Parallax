<script setup lang="ts">
withDefaults(defineProps<{
  status: 'online' | 'degraded' | 'offline' | 'done' | 'active' | 'pending' | 'failed' | 'skipped' | 'invalidated'
  label?: string
  size?: 'sm' | 'md'
}>(), {
  label: undefined,
  size: 'md',
})

const dotColorMap: Record<string, string> = {
  online: 'var(--success)',
  done: 'var(--success)',
  active: 'var(--os-brand)',
  degraded: 'var(--warning)',
  pending: 'var(--text-tertiary)',
  skipped: 'var(--text-tertiary)',
  invalidated: 'var(--warning)',
  offline: 'var(--error)',
  failed: 'var(--error)',
}

const pulseStatuses = new Set(['online', 'active'])
</script>

<template>
  <span
    class="status-badge"
    :class="[`status-badge--${size}`, `status-badge--${status}`]"
  >
    <span
      class="status-badge__dot"
      :class="{ 'status-badge__dot--pulse': pulseStatuses.has(status) }"
      :style="{ backgroundColor: dotColorMap[status] }"
    />
    <span v-if="label" class="status-badge__label">{{ label }}</span>
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.status-badge__dot {
  flex-shrink: 0;
  border-radius: 50%;
  transition: background-color var(--transition-normal);
}

.status-badge--sm .status-badge__dot {
  width: 6px;
  height: 6px;
}

.status-badge--md .status-badge__dot {
  width: 8px;
  height: 8px;
}

.status-badge__dot--pulse {
  animation: badge-pulse 2s ease-in-out infinite;
}

.status-badge__label {
  font-size: 12px;
  font-family: var(--font-sans);
  font-weight: 500;
  color: var(--text-secondary);
  letter-spacing: 0.01em;
}

.status-badge--sm .status-badge__label {
  font-size: 11px;
}

/* Semantic coloring for labels */
.status-badge--done .status-badge__label,
.status-badge--online .status-badge__label { color: var(--success); }
.status-badge--active .status-badge__label { color: var(--os-brand); }
.status-badge--invalidated .status-badge__label,
.status-badge--degraded .status-badge__label { color: var(--warning); }
.status-badge--failed .status-badge__label,
.status-badge--offline .status-badge__label { color: var(--error); }

@keyframes badge-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>

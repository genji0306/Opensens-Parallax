<script setup lang="ts">
withDefaults(defineProps<{
  label: string
  value: string | number
  icon?: string
  trend?: 'up' | 'down' | 'neutral'
}>(), {
  icon: undefined,
  trend: undefined,
})

const trendIcons: Record<string, string> = {
  up: 'trending_up',
  down: 'trending_down',
  neutral: 'trending_flat',
}

const trendColors: Record<string, string> = {
  up: 'var(--success)',
  down: 'var(--error)',
  neutral: 'var(--text-tertiary)',
}
</script>

<template>
  <div class="metric-card">
    <div class="metric-card__body">
      <span
        v-if="icon"
        class="material-symbols-outlined metric-card__icon"
      >
        {{ icon }}
      </span>
      <div class="metric-card__content">
        <span class="metric-card__value font-mono">{{ value }}</span>
        <span class="metric-card__label">{{ label }}</span>
      </div>
      <span
        v-if="trend"
        class="material-symbols-outlined metric-card__trend"
        :style="{ color: trendColors[trend] }"
      >
        {{ trendIcons[trend] }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.metric-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  transition:
    background var(--transition-normal),
    border-color var(--transition-normal),
    box-shadow var(--transition-normal);
}

.metric-card:hover {
  border-color: var(--border-primary);
  box-shadow: var(--shadow-sm);
}

.metric-card__body {
  display: flex;
  align-items: center;
  gap: 10px;
}

.metric-card__icon {
  font-size: 20px;
  color: var(--os-brand);
  flex-shrink: 0;
}

.metric-card__content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.metric-card__value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.metric-card__label {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.metric-card__trend {
  font-size: 18px;
  margin-left: auto;
  flex-shrink: 0;
}
</style>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  progress: number
  color?: string
  height?: string
  showLabel?: boolean
}>(), {
  color: 'var(--os-brand)',
  height: '4px',
  showLabel: false,
})

const clampedProgress = computed(() =>
  Math.min(100, Math.max(0, props.progress))
)
</script>

<template>
  <div class="progress-bar" :style="{ height }">
    <div class="progress-bar__track">
      <div
        class="progress-bar__fill"
        :style="{
          width: `${clampedProgress}%`,
          '--bar-color': color,
        }"
      />
    </div>
    <span
      v-if="showLabel"
      class="progress-bar__label font-mono"
    >
      {{ clampedProgress }}%
    </span>
  </div>
</template>

<style scoped>
.progress-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.progress-bar__track {
  flex: 1;
  height: 100%;
  background: var(--bg-tertiary);
  border-radius: var(--radius-pill);
  overflow: hidden;
}

.progress-bar__fill {
  height: 100%;
  border-radius: var(--radius-pill);
  background: linear-gradient(
    90deg,
    var(--bar-color),
    color-mix(in srgb, var(--bar-color) 70%, white)
  );
  transition: width 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  min-width: 0;
}

.progress-bar__label {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  flex-shrink: 0;
  min-width: 36px;
  text-align: right;
}
</style>

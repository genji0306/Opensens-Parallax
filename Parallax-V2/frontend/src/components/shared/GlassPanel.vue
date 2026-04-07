<script setup lang="ts">
withDefaults(defineProps<{
  elevated?: boolean
  padding?: string
  title?: string
  icon?: string
}>(), {
  elevated: false,
  padding: '16px',
  title: '',
  icon: '',
})
</script>

<template>
  <div
    class="glass-panel"
    :class="{ 'glass-panel--elevated': elevated }"
    :style="{ padding }"
  >
    <header v-if="title || icon || $slots.header" class="glass-panel__header">
      <slot name="header">
        <span v-if="icon" class="material-icons glass-panel__icon">{{ icon }}</span>
        <h3 v-if="title" class="glass-panel__title">{{ title }}</h3>
      </slot>
    </header>
    <slot />
  </div>
</template>

<style scoped>
.glass-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-lg);
}

.glass-panel--elevated {
  background: var(--bg-elevated);
  border-color: var(--border-primary);
  box-shadow: var(--shadow-md);
}

.glass-panel__header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-secondary, rgba(255, 255, 255, 0.06));
}

.glass-panel__icon {
  font-size: 1.1rem;
  color: var(--color-accent, #7aa2ff);
}

.glass-panel__title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
}
</style>

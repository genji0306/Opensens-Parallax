<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  type?: 'button' | 'submit' | 'reset'
  icon?: string
  loading?: boolean
  disabled?: boolean
}>(), {
  variant: 'primary',
  size: 'md',
  type: 'button',
  icon: undefined,
  loading: false,
  disabled: false,
})

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

function handleClick(e: MouseEvent) {
  emit('click', e)
}
</script>

<template>
  <button
    :type="type"
    class="action-btn"
    :class="[
      `action-btn--${variant}`,
      `action-btn--${size}`,
      { 'action-btn--loading': loading },
    ]"
    :disabled="disabled || loading"
    @click="handleClick"
  >
    <span v-if="loading" class="action-btn__spinner" />
    <span
      v-else-if="icon"
      class="material-symbols-outlined action-btn__icon"
    >
      {{ icon }}
    </span>
    <span v-if="$slots.default" class="action-btn__label">
      <slot />
    </span>
  </button>
</template>

<style scoped>
.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-family: var(--font-sans);
  font-weight: 500;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  white-space: nowrap;
}

.action-btn:active:not(:disabled) {
  transform: scale(0.97);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── Sizes ── */
.action-btn--sm { height: 30px; padding: 0 10px; font-size: 12px; }
.action-btn--sm .action-btn__icon { font-size: 16px; }

.action-btn--md { height: 36px; padding: 0 14px; font-size: 13px; }
.action-btn--md .action-btn__icon { font-size: 18px; }

.action-btn--lg { height: 42px; padding: 0 20px; font-size: 14px; }
.action-btn--lg .action-btn__icon { font-size: 20px; }

/* ── Variants ── */
.action-btn--primary {
  background: var(--os-brand);
  color: var(--text-on-brand);
  border-color: var(--os-brand);
}
.action-btn--primary:hover:not(:disabled) {
  background: var(--os-brand-hover);
  border-color: var(--os-brand-hover);
}

.action-btn--secondary {
  background: transparent;
  color: var(--os-brand);
  border-color: var(--os-brand);
}
.action-btn--secondary:hover:not(:disabled) {
  background: var(--os-brand-light);
}

.action-btn--ghost {
  background: transparent;
  color: var(--os-brand);
  border-color: transparent;
}
.action-btn--ghost:hover:not(:disabled) {
  background: var(--bg-hover);
}

/* ── Spinner ── */
.action-btn__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: btn-spin 0.6s linear infinite;
}

.action-btn--loading {
  pointer-events: none;
}

@keyframes btn-spin {
  to { transform: rotate(360deg); }
}
</style>

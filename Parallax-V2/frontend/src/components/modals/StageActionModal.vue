<script setup lang="ts">
import ActionButton from '@/components/shared/ActionButton.vue'

withDefaults(defineProps<{
  open: boolean
  title: string
  description: string
  costEstimate?: string
  confirmLabel?: string
}>(), {
  costEstimate: undefined,
  confirmLabel: 'Confirm',
})

const emit = defineEmits<{
  close: []
  confirm: []
}>()
</script>

<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="open" class="modal-overlay" @click.self="emit('close')">
        <div class="modal-card">
          <!-- Header -->
          <div class="modal-card__header">
            <span class="material-symbols-outlined modal-card__header-icon">info</span>
            <span class="modal-card__title">{{ title }}</span>
            <button class="modal-card__close" @click="emit('close')">
              <span class="material-symbols-outlined">close</span>
            </button>
          </div>

          <!-- Body -->
          <div class="modal-card__body">
            <p class="modal-card__desc">{{ description }}</p>

            <div v-if="costEstimate" class="modal-card__cost">
              <span class="material-symbols-outlined modal-card__cost-icon">payments</span>
              <span class="modal-card__cost-label">Estimated cost:</span>
              <span class="modal-card__cost-value">{{ costEstimate }}</span>
            </div>
          </div>

          <!-- Footer -->
          <div class="modal-card__footer">
            <ActionButton variant="ghost" size="sm" @click="emit('close')">
              Cancel
            </ActionButton>
            <ActionButton variant="primary" size="sm" @click="emit('confirm')">
              {{ confirmLabel }}
            </ActionButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* ── Overlay ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  padding: 16px;
}

/* ── Card ── */
.modal-card {
  width: 100%;
  max-width: 420px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Header ── */
.modal-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border-secondary);
}

.modal-card__header-icon {
  font-size: 20px;
  color: var(--os-brand);
}

.modal-card__title {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.modal-card__close {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  transition: color var(--transition-fast), background var(--transition-fast);
}

.modal-card__close:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.modal-card__close .material-symbols-outlined {
  font-size: 20px;
}

/* ── Body ── */
.modal-card__body {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.modal-card__desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.modal-card__cost {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
}

.modal-card__cost-icon {
  font-size: 16px;
  color: var(--os-tertiary);
}

.modal-card__cost-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.modal-card__cost-value {
  font-size: 13px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--os-tertiary);
  margin-left: auto;
}

/* ── Footer ── */
.modal-card__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px 16px;
  border-top: 1px solid var(--border-secondary);
}

/* ── Transition ── */
.modal-fade-enter-active {
  transition: opacity 0.2s ease;
}
.modal-fade-leave-active {
  transition: opacity 0.15s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-active .modal-card {
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease;
}
.modal-fade-leave-active .modal-card {
  transition: transform 0.15s ease, opacity 0.15s ease;
}
.modal-fade-enter-from .modal-card {
  transform: translateY(16px) scale(0.97);
  opacity: 0;
}
.modal-fade-leave-to .modal-card {
  transform: translateY(8px) scale(0.98);
  opacity: 0;
}
</style>

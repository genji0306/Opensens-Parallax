<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { StageId, StageStatus } from '@/types/pipeline'
import GlassPanel from '@/components/shared/GlassPanel.vue'
import StatusBadge from '@/components/shared/StatusBadge.vue'
import ActionButton from '@/components/shared/ActionButton.vue'
import StageSettingsForm from '@/components/pipeline/StageSettingsForm.vue'
import { updateNodeModel, updateNodeSettings } from '@/api/ais'

const props = withDefaults(defineProps<{
  stageId: StageId
  title: string
  status: StageStatus
  icon: string
  metrics?: Array<{ label: string; value: string | number; icon?: string }>
  actions?: Array<{ label: string; action: string; primary?: boolean }>
  expandable?: boolean
  expanded?: boolean
  nodeId?: string
  runId?: string
  modelUsed?: string
  nodeConfig?: Record<string, unknown>
}>(), {
  metrics: () => [],
  actions: () => [],
  expandable: true,
  expanded: false,
})

const emit = defineEmits<{
  action: [actionName: string]
  'toggle-expand': []
  'model-changed': [model: string]
  restart: [nodeId: string]
}>()

const innerExpanded = ref(props.expanded)

watch(() => props.expanded, (v) => { innerExpanded.value = v })

function toggle() {
  if (!props.expandable) return
  innerExpanded.value = !innerExpanded.value
  emit('toggle-expand')
}

// ── Model Selector ──────────────────────────────────────────────────────

interface ModelOption {
  label: string
  value: string
}

const MODEL_OPTIONS: ModelOption[] = [
  { label: 'Claude Haiku', value: 'claude-haiku-4-5-20251001' },
  { label: 'Claude Sonnet', value: 'claude-sonnet-4-20250514' },
  { label: 'Claude Opus', value: 'claude-opus-4-20250514' },
  { label: 'GPT-4o-mini', value: 'aiclient-proxy:gpt-4o-mini' },
  { label: 'GPT-4o', value: 'aiclient-proxy:gpt-4o' },
]

const modelDropdownOpen = ref(false)
const selectedModel = ref(props.modelUsed ?? '')
const modelSaving = ref(false)

watch(() => props.modelUsed, (v) => { selectedModel.value = v ?? '' })

const modelShortLabel = computed(() => {
  if (!selectedModel.value) return 'auto'
  const found = MODEL_OPTIONS.find(o => o.value === selectedModel.value)
  if (found && found.value) return found.label
  // Fallback: extract a short name from the raw model string
  const raw = selectedModel.value
  if (raw.includes('haiku')) return 'haiku'
  if (raw.includes('sonnet')) return 'sonnet'
  if (raw.includes('opus')) return 'opus'
  if (raw.includes('gpt-4o-mini')) return '4o-mini'
  if (raw.includes('gpt-4o')) return '4o'
  return raw.split('/').pop()?.split('-').slice(0, 2).join('-') ?? raw
})

function toggleModelDropdown(e: Event) {
  e.stopPropagation()
  modelDropdownOpen.value = !modelDropdownOpen.value
}

async function selectModel(option: ModelOption) {
  modelDropdownOpen.value = false
  if (option.value === selectedModel.value) return

  if (props.runId && props.nodeId) {
    modelSaving.value = true
    try {
      await updateNodeModel(props.runId, props.nodeId, option.value)
      selectedModel.value = option.value
      emit('model-changed', option.value)
    } catch (err) {
      console.error('Failed to update node model:', err)
    } finally {
      modelSaving.value = false
    }
    return
  }

  selectedModel.value = option.value
  emit('model-changed', option.value)
}

// Close dropdown on outside click
function onDocClick() {
  modelDropdownOpen.value = false
}

// ── Advanced Settings (typed per-stage schemas) ─────────────────────────

const settingsOpen = ref(false)
const settingsSaving = ref(false)

function getInitialSettings(): Record<string, unknown> {
  const src = (props.nodeConfig?.step_settings ?? props.nodeConfig ?? {}) as Record<string, unknown>
  return { ...src }
}

const typedSettings = ref<Record<string, unknown>>(getInitialSettings())

watch(() => props.nodeConfig, () => {
  typedSettings.value = getInitialSettings()
}, { deep: true })

function onSettingsUpdate(updated: Record<string, unknown>) {
  typedSettings.value = updated
}

async function saveSettings() {
  if (!props.runId || !props.nodeId) return
  settingsSaving.value = true
  try {
    await updateNodeSettings(props.runId, props.nodeId, { ...typedSettings.value })
  } catch (err) {
    console.error('Failed to save node settings:', err)
  } finally {
    settingsSaving.value = false
  }
}

// ── Restart ─────────────────────────────────────────────────────────────

function handleRestart(e: Event) {
  e.stopPropagation()
  if (props.nodeId) {
    emit('restart', props.nodeId)
  }
}
</script>

<template>
  <GlassPanel elevated class="stage-card" :class="[`stage-card--${status}`]" @click="onDocClick">
    <!-- Header -->
    <button
      class="stage-card__header"
      :class="{ 'stage-card__header--clickable': expandable }"
      @click="toggle"
    >
      <span class="stage-card__icon-wrap" :class="[`stage-card__icon-wrap--${status}`]">
        <span class="material-symbols-outlined stage-card__icon">{{ icon }}</span>
      </span>

      <span class="stage-card__title">{{ title }}</span>

      <StatusBadge :status="status" :label="status" size="sm" />

      <!-- Model chip -->
      <span
        v-if="nodeId"
        class="stage-card__model-chip"
        :class="{ 'stage-card__model-chip--saving': modelSaving }"
        @click="toggleModelDropdown"
      >
        <span class="material-symbols-outlined stage-card__model-chip-icon">smart_toy</span>
        <span class="stage-card__model-chip-label">{{ modelShortLabel }}</span>
        <span class="material-symbols-outlined stage-card__model-chip-arrow">arrow_drop_down</span>

        <!-- Dropdown -->
        <Transition name="stage-card-dropdown">
          <div v-if="modelDropdownOpen" class="stage-card__model-dropdown">
            <button
              v-for="opt in MODEL_OPTIONS"
              :key="opt.value"
              class="stage-card__model-option"
              :class="{ 'stage-card__model-option--active': opt.value === selectedModel }"
              @click.stop="selectModel(opt)"
            >
              <span class="stage-card__model-option-label">{{ opt.label }}</span>
              <span
                v-if="opt.value === selectedModel"
                class="material-symbols-outlined stage-card__model-option-check"
              >check</span>
            </button>
          </div>
        </Transition>
      </span>

      <span
        v-if="expandable"
        class="material-symbols-outlined stage-card__chevron"
        :class="{ 'stage-card__chevron--open': innerExpanded }"
      >
        expand_more
      </span>
    </button>

    <!-- Metrics grid -->
    <div v-if="metrics.length" class="stage-card__metrics">
      <div
        v-for="m in metrics"
        :key="m.label"
        class="stage-card__metric"
      >
        <span
          v-if="m.icon"
          class="material-symbols-outlined stage-card__metric-icon"
        >
          {{ m.icon }}
        </span>
        <span class="stage-card__metric-value">{{ m.value }}</span>
        <span class="stage-card__metric-label">{{ m.label }}</span>
      </div>
    </div>

    <!-- Actions -->
    <div v-if="actions.length || nodeId" class="stage-card__actions">
      <ActionButton
        v-for="a in actions"
        :key="a.action"
        :variant="a.primary ? 'primary' : 'secondary'"
        size="sm"
        @click="emit('action', a.action)"
      >
        {{ a.label }}
      </ActionButton>

      <!-- Restart button -->
      <ActionButton
        v-if="nodeId"
        variant="ghost"
        size="sm"
        @click="handleRestart"
      >
        <span class="material-symbols-outlined stage-card__restart-icon">replay</span>
        Restart
      </ActionButton>
    </div>

    <!-- Expandable detail slot -->
    <Transition name="stage-card-expand">
      <div v-if="expandable && innerExpanded" class="stage-card__detail">
        <!-- Advanced Settings toggle -->
        <div v-if="nodeId" class="stage-card__settings-section">
          <button
            class="stage-card__settings-toggle"
            @click="settingsOpen = !settingsOpen"
          >
            <span class="material-symbols-outlined stage-card__settings-toggle-icon">tune</span>
            <span>Settings</span>
            <span
              class="material-symbols-outlined stage-card__settings-toggle-chevron"
              :class="{ 'stage-card__settings-toggle-chevron--open': settingsOpen }"
            >expand_more</span>
          </button>

          <Transition name="stage-card-expand">
            <div v-if="settingsOpen" class="stage-card__settings-form">
              <StageSettingsForm
                :stage-id="stageId"
                :model-value="typedSettings"
                @update:model-value="onSettingsUpdate"
              />

              <!-- Save button -->
              <ActionButton
                variant="primary"
                size="sm"
                :disabled="settingsSaving"
                @click="saveSettings"
              >
                <span v-if="settingsSaving" class="material-symbols-outlined stage-card__spin">progress_activity</span>
                {{ settingsSaving ? 'Saving...' : 'Save Settings' }}
              </ActionButton>
            </div>
          </Transition>
        </div>

        <slot />
      </div>
    </Transition>
  </GlassPanel>
</template>

<style scoped>
.stage-card {
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow: hidden;
}

/* ── Header ── */
.stage-card__header {
  display: flex;
  align-items: center;
  gap: 10px;
  background: none;
  border: none;
  padding: 0;
  width: 100%;
  text-align: left;
  font-family: var(--font-sans);
}

.stage-card__header--clickable {
  cursor: pointer;
}

.stage-card__header--clickable:hover .stage-card__title {
  color: var(--os-brand);
}

.stage-card__icon-wrap {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--bg-tertiary);
  transition: background var(--transition-normal);
}

.stage-card__icon-wrap--done {
  background: var(--os-brand-light);
}

.stage-card__icon-wrap--active {
  background: var(--os-brand-light);
}

.stage-card__icon-wrap--failed {
  background: rgba(239, 68, 68, 0.1);
}

.stage-card__icon {
  font-size: 18px;
  color: var(--text-secondary);
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 20;
}

.stage-card__icon-wrap--done .stage-card__icon,
.stage-card__icon-wrap--active .stage-card__icon {
  color: var(--os-brand);
}

.stage-card__icon-wrap--failed .stage-card__icon {
  color: var(--error);
}

.stage-card__title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  transition: color var(--transition-fast);
}

.stage-card__chevron {
  font-size: 20px;
  color: var(--text-tertiary);
  transition: transform var(--transition-normal);
  flex-shrink: 0;
}

.stage-card__chevron--open {
  transform: rotate(180deg);
}

/* ── Model Chip ── */
.stage-card__model-chip {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px 2px 6px;
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-secondary);
  cursor: pointer;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
  white-space: nowrap;
  flex-shrink: 0;
}

.stage-card__model-chip:hover {
  background: var(--bg-secondary);
  border-color: var(--os-brand);
  color: var(--text-primary);
}

.stage-card__model-chip--saving {
  opacity: 0.6;
  pointer-events: none;
}

.stage-card__model-chip-icon {
  font-size: 14px;
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 20;
}

.stage-card__model-chip-label {
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stage-card__model-chip-arrow {
  font-size: 16px;
  margin-left: -2px;
}

/* ── Model Dropdown ── */
.stage-card__model-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 50;
  min-width: 180px;
  background: var(--bg-primary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  padding: 4px;
  display: flex;
  flex-direction: column;
}

.stage-card__model-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 10px;
  border: none;
  background: none;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  text-align: left;
  transition: all var(--transition-fast);
  font-family: var(--font-sans);
}

.stage-card__model-option:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.stage-card__model-option--active {
  color: var(--os-brand);
  background: var(--os-brand-light);
}

.stage-card__model-option-label {
  flex: 1;
}

.stage-card__model-option-check {
  font-size: 16px;
  color: var(--os-brand);
  font-variation-settings: 'FILL' 0, 'wght' 600, 'GRAD' 0, 'opsz' 20;
}

/* Dropdown transition */
.stage-card-dropdown-enter-active,
.stage-card-dropdown-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.stage-card-dropdown-enter-from,
.stage-card-dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ── Restart button icon ── */
.stage-card__restart-icon {
  font-size: 16px;
  margin-right: 2px;
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 20;
}

/* ── Metrics ── */
.stage-card__metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-secondary);
}

.stage-card__metric {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 4px;
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
}

.stage-card__metric-icon {
  font-size: 14px;
  color: var(--text-tertiary);
}

.stage-card__metric-value {
  font-size: 16px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--text-primary);
  line-height: 1.2;
}

.stage-card__metric-label {
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
}

/* ── Actions ── */
.stage-card__actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-secondary);
  flex-wrap: wrap;
}

/* ── Expandable detail ── */
.stage-card__detail {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-secondary);
}

/* ── Advanced Settings ── */
.stage-card__settings-section {
  margin-bottom: 12px;
}

.stage-card__settings-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
  font-family: var(--font-sans);
}

.stage-card__settings-toggle:hover {
  border-color: var(--os-brand);
  color: var(--text-primary);
}

.stage-card__settings-toggle-icon {
  font-size: 16px;
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 20;
}

.stage-card__settings-toggle-chevron {
  font-size: 18px;
  transition: transform var(--transition-normal);
  margin-left: auto;
}

.stage-card__settings-toggle-chevron--open {
  transform: rotate(180deg);
}

.stage-card__settings-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  margin-top: 8px;
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
}

.stage-card__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stage-card__field--checkbox {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}

.stage-card__field-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
}

.stage-card__field-value {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  color: var(--os-brand);
}

.stage-card__field-input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 13px;
  font-family: var(--font-mono);
  transition: border-color var(--transition-fast);
  outline: none;
}

.stage-card__field-input:focus {
  border-color: var(--os-brand);
}

.stage-card__field-range {
  width: 100%;
  height: 4px;
  appearance: none;
  -webkit-appearance: none;
  background: var(--bg-tertiary);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}

.stage-card__field-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--os-brand);
  border: 2px solid var(--bg-primary);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
  cursor: pointer;
  transition: transform var(--transition-fast);
}

.stage-card__field-range::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

.stage-card__field-range::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--os-brand);
  border: 2px solid var(--bg-primary);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
  cursor: pointer;
}

.stage-card__field-checkbox {
  width: 16px;
  height: 16px;
  accent-color: var(--os-brand);
  cursor: pointer;
  flex-shrink: 0;
}

.stage-card__field--checkbox .stage-card__field-label {
  text-transform: none;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

/* Spinning loader */
@keyframes stage-card-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.stage-card__spin {
  font-size: 14px;
  animation: stage-card-spin 0.8s linear infinite;
  margin-right: 4px;
}

/* Expand transition */
.stage-card-expand-enter-active,
.stage-card-expand-leave-active {
  transition:
    max-height 0.3s cubic-bezier(0.16, 1, 0.3, 1),
    opacity 0.25s ease;
  overflow: hidden;
  max-height: 500px;
}

.stage-card-expand-enter-from,
.stage-card-expand-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>

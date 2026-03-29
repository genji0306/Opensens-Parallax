<script setup lang="ts">
/**
 * StageSettingsForm — Dynamic settings renderer for pipeline stages (Sprint 4, Task 4.1).
 *
 * Renders typed controls based on the stage's SettingsSchema: number sliders,
 * booleans, selects, multi-selects. Emits updated settings on change.
 */

import { ref, watch, computed } from 'vue'
import type { StageId } from '@/types/pipeline'
import { STAGE_SETTINGS_SCHEMAS, getDefaultSettings } from '@/types/stage-settings'
import type { SettingField, StageSettingsSchema } from '@/types/stage-settings'

const props = defineProps<{
  stageId: StageId
  /** Current settings from the node config (merged with defaults). */
  modelValue: Record<string, unknown>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown>]
}>()

const schema = computed<StageSettingsSchema>(() => STAGE_SETTINGS_SCHEMAS[props.stageId])

// Local copy of settings for two-way binding
const local = ref<Record<string, unknown>>({})

watch(
  () => props.modelValue,
  (val) => {
    const defaults = getDefaultSettings(props.stageId)
    local.value = { ...defaults, ...val }
  },
  { immediate: true, deep: true },
)

function updateField(key: string, value: unknown) {
  local.value[key] = value
  emit('update:modelValue', { ...local.value })
}

function toggleMultiSelect(key: string, optionValue: string) {
  const current = (local.value[key] as string[]) ?? []
  const idx = current.indexOf(optionValue)
  const next = idx >= 0
    ? current.filter((v) => v !== optionValue)
    : [...current, optionValue]
  updateField(key, next)
}

function isMultiSelected(key: string, optionValue: string): boolean {
  const current = (local.value[key] as string[]) ?? []
  return current.includes(optionValue)
}

function getFieldComponent(field: SettingField) {
  return field.type
}
</script>

<template>
  <div v-if="schema.fields.length > 0" class="stage-settings">
    <h5 class="stage-settings__title">{{ schema.label }}</h5>

    <div
      v-for="field in schema.fields"
      :key="field.key"
      class="stage-settings__field"
    >
      <label class="stage-settings__label">
        {{ field.label }}
        <span v-if="field.description" class="stage-settings__hint">{{ field.description }}</span>
      </label>

      <!-- Number input with range -->
      <div v-if="getFieldComponent(field) === 'number'" class="stage-settings__number">
        <input
          type="range"
          :min="field.min ?? 0"
          :max="field.max ?? 100"
          :step="field.step ?? 1"
          :value="local[field.key] as number"
          class="stage-settings__slider"
          @input="updateField(field.key, Number(($event.target as HTMLInputElement).value))"
        />
        <span class="stage-settings__number-value font-mono">{{ local[field.key] }}</span>
      </div>

      <!-- Boolean toggle -->
      <label v-else-if="getFieldComponent(field) === 'boolean'" class="stage-settings__toggle">
        <input
          type="checkbox"
          :checked="local[field.key] as boolean"
          @change="updateField(field.key, ($event.target as HTMLInputElement).checked)"
        />
        <span class="stage-settings__toggle-label">{{ (local[field.key] as boolean) ? 'Enabled' : 'Disabled' }}</span>
      </label>

      <!-- Select dropdown -->
      <select
        v-else-if="getFieldComponent(field) === 'select'"
        class="stage-settings__select"
        :value="local[field.key] as string"
        @change="updateField(field.key, ($event.target as HTMLSelectElement).value)"
      >
        <option
          v-for="opt in field.options"
          :key="opt.value"
          :value="opt.value"
        >
          {{ opt.label }}
        </option>
      </select>

      <!-- Multi-select chips -->
      <div v-else-if="getFieldComponent(field) === 'multi-select'" class="stage-settings__chips">
        <button
          v-for="opt in field.options"
          :key="opt.value"
          class="stage-settings__chip"
          :class="{ 'stage-settings__chip--active': isMultiSelected(field.key, opt.value) }"
          @click="toggleMultiSelect(field.key, opt.value)"
        >
          {{ opt.label }}
        </button>
      </div>

      <!-- Text input -->
      <input
        v-else-if="getFieldComponent(field) === 'text'"
        type="text"
        class="stage-settings__text-input"
        :value="local[field.key] as string"
        @input="updateField(field.key, ($event.target as HTMLInputElement).value)"
      />
    </div>
  </div>
</template>

<style scoped>
.stage-settings {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
}

.stage-settings__title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin: 0;
}

.stage-settings__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stage-settings__label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stage-settings__hint {
  font-size: 10px;
  font-weight: 400;
  color: var(--text-tertiary);
}

.stage-settings__number {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stage-settings__slider {
  flex: 1;
  accent-color: var(--os-brand);
  cursor: pointer;
}

.stage-settings__number-value {
  font-size: 12px;
  min-width: 36px;
  text-align: right;
  color: var(--text-secondary);
}

.stage-settings__toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 12px;
}

.stage-settings__toggle input[type="checkbox"] {
  accent-color: var(--os-brand);
  cursor: pointer;
}

.stage-settings__toggle-label {
  font-size: 11px;
  color: var(--text-secondary);
}

.stage-settings__select {
  padding: 5px 8px;
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-sm);
  outline: none;
  cursor: pointer;
}

.stage-settings__select:focus {
  border-color: var(--os-brand);
}

.stage-settings__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.stage-settings__chip {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--bg-primary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-pill, 999px);
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease;
}

.stage-settings__chip:hover {
  border-color: var(--text-tertiary);
  color: var(--text-primary);
}

.stage-settings__chip--active {
  background: color-mix(in srgb, var(--os-brand) 12%, transparent);
  border-color: var(--os-brand);
  color: var(--os-brand);
}

.stage-settings__text-input {
  padding: 5px 8px;
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-sm);
  outline: none;
}

.stage-settings__text-input:focus {
  border-color: var(--os-brand);
}
</style>

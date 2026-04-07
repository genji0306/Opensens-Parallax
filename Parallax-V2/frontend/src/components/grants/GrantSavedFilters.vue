<script setup lang="ts">
import { onMounted, ref } from 'vue'

import type { GrantFilter } from '@/types/grants'

interface SavedFilter {
  id: string
  name: string
  region_codes: string[]
  applicant_scopes: string[]
  theme_tags: string[]
  deadline_states: string[]
}

const STORAGE_KEY = 'grant_hunt_saved_filters'

const DEFAULT_OPENSENS_FILTER: SavedFilter = {
  id: 'opensens-default',
  name: 'Opensens — SEA Startup/Research',
  region_codes: ['VN', 'TH', 'ID', 'MY', 'SG', 'PH', 'KH', 'LA', 'MM', 'BN', 'TL', 'ASEAN', 'APAC', 'GLOBAL'],
  applicant_scopes: ['startup', 'researcher'],
  theme_tags: [
    'innovation_entrepreneurship',
    'climate_tech',
    'physical_ai',
    'ai_sensing',
    'ai_education',
  ],
  deadline_states: ['open', 'closing_soon'],
}

const emit = defineEmits<{
  (e: 'apply-filters', filter: GrantFilter): void
}>()

// ── State ───────────────────────────────────────────────────────────────
const savedFilters = ref<SavedFilter[]>([])
const showSaveDialog = ref(false)
const newFilterName = ref('')
const expandedId = ref<string | null>(null)

// ── Current applied filter (reflected back from parent via v-model or manual) ──
// We track what's "current" simply so the save dialog can capture it.
// The parent is the source of truth for the active filter.
const currentFilter = ref<GrantFilter>({})

// ── Persistence ─────────────────────────────────────────────────────────
function loadFromStorage(): void {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed: SavedFilter[] = raw ? (JSON.parse(raw) as SavedFilter[]) : []
    // Ensure the default Opensens filter always exists
    const hasDefault = parsed.some(f => f.id === DEFAULT_OPENSENS_FILTER.id)
    savedFilters.value = hasDefault ? parsed : [DEFAULT_OPENSENS_FILTER, ...parsed]
  } catch {
    savedFilters.value = [DEFAULT_OPENSENS_FILTER]
  }
}

function saveToStorage(): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(savedFilters.value))
  } catch {
    // localStorage unavailable — silently ignore
  }
}

// ── Actions ─────────────────────────────────────────────────────────────
function applyFilter(saved: SavedFilter): void {
  const filter: GrantFilter = {
    region_codes: saved.region_codes.length ? saved.region_codes : undefined,
    applicant_scopes: saved.applicant_scopes.length ? saved.applicant_scopes : undefined,
    theme_tags: saved.theme_tags.length ? saved.theme_tags : undefined,
  }
  currentFilter.value = filter
  emit('apply-filters', filter)
}

function openSaveDialog(): void {
  newFilterName.value = ''
  showSaveDialog.value = true
}

function closeSaveDialog(): void {
  showSaveDialog.value = false
  newFilterName.value = ''
}

function saveCurrentFilter(): void {
  const name = newFilterName.value.trim()
  if (!name) return
  const newFilter: SavedFilter = {
    id: `user-${Date.now()}`,
    name,
    region_codes: currentFilter.value.region_codes ?? [],
    applicant_scopes: currentFilter.value.applicant_scopes ?? [],
    theme_tags: currentFilter.value.theme_tags ?? [],
    deadline_states: currentFilter.value.deadline_state ? [currentFilter.value.deadline_state] : [],
  }
  savedFilters.value = [...savedFilters.value, newFilter]
  saveToStorage()
  closeSaveDialog()
}

function deleteFilter(id: string): void {
  savedFilters.value = savedFilters.value.filter(f => f.id !== id)
  saveToStorage()
}

function toggleExpand(id: string): void {
  expandedId.value = expandedId.value === id ? null : id
}

// ── Chip summary ─────────────────────────────────────────────────────────
function chipSummary(f: SavedFilter): string[] {
  const chips: string[] = []
  if (f.region_codes.length) chips.push(`${f.region_codes.length} regions`)
  if (f.applicant_scopes.length) chips.push(f.applicant_scopes.join(' / '))
  if (f.theme_tags.length) chips.push(`${f.theme_tags.length} themes`)
  if (f.deadline_states.length) chips.push(f.deadline_states.join(', '))
  return chips
}

// ── Expose setCurrentFilter so parent can push its active filter state ──
function setCurrentFilter(f: GrantFilter): void {
  currentFilter.value = { ...f }
}

defineExpose({ setCurrentFilter })

onMounted(loadFromStorage)
</script>

<template>
  <div class="saved-filters">
    <header class="saved-filters__header">
      <span class="material-icons saved-filters__icon">bookmarks</span>
      <span class="saved-filters__title">Saved views</span>
      <button class="btn-ghost-sm" @click="openSaveDialog" title="Save current filters">
        <span class="material-icons">add</span>
        Save current
      </button>
    </header>

    <ul class="filter-list" role="list">
      <li
        v-for="f in savedFilters"
        :key="f.id"
        class="filter-item"
        :class="{ 'filter-item--expanded': expandedId === f.id }"
      >
        <div class="filter-item__row">
          <button class="filter-item__name" @click="applyFilter(f)">
            <span class="material-icons filter-item__apply-icon">filter_alt</span>
            <span>{{ f.name }}</span>
          </button>

          <div class="filter-item__actions">
            <button
              class="icon-btn"
              @click="toggleExpand(f.id)"
              :title="expandedId === f.id ? 'Collapse' : 'Expand'"
            >
              <span class="material-icons">{{ expandedId === f.id ? 'expand_less' : 'expand_more' }}</span>
            </button>
            <button
              v-if="f.id !== DEFAULT_OPENSENS_FILTER.id"
              class="icon-btn icon-btn--danger"
              @click="deleteFilter(f.id)"
              title="Delete saved view"
            >
              <span class="material-icons">delete_outline</span>
            </button>
          </div>
        </div>

        <!-- Chip summary row -->
        <div class="filter-item__chips">
          <span v-for="chip in chipSummary(f)" :key="chip" class="chip">{{ chip }}</span>
        </div>

        <!-- Expanded detail -->
        <div v-if="expandedId === f.id" class="filter-item__detail">
          <div v-if="f.region_codes.length" class="detail-row">
            <span class="detail-row__label">Regions</span>
            <span class="detail-row__value">{{ f.region_codes.join(', ') }}</span>
          </div>
          <div v-if="f.applicant_scopes.length" class="detail-row">
            <span class="detail-row__label">Scopes</span>
            <span class="detail-row__value">{{ f.applicant_scopes.join(', ') }}</span>
          </div>
          <div v-if="f.theme_tags.length" class="detail-row">
            <span class="detail-row__label">Themes</span>
            <span class="detail-row__value">{{ f.theme_tags.join(', ') }}</span>
          </div>
          <div v-if="f.deadline_states.length" class="detail-row">
            <span class="detail-row__label">Status</span>
            <span class="detail-row__value">{{ f.deadline_states.join(', ') }}</span>
          </div>
          <button class="btn-apply" @click="applyFilter(f)">
            <span class="material-icons">check</span>
            Apply this view
          </button>
        </div>
      </li>

      <li v-if="savedFilters.length === 0" class="filter-empty">
        No saved views yet. Save your current filters to reuse them.
      </li>
    </ul>

    <!-- Save dialog -->
    <div v-if="showSaveDialog" class="dialog-backdrop" @click.self="closeSaveDialog">
      <div class="dialog">
        <h4 class="dialog__title">Save current filters</h4>
        <label class="dialog__label">
          View name
          <input
            v-model="newFilterName"
            class="dialog__input"
            placeholder="e.g. SEA Climate Grants"
            autofocus
            @keyup.enter="saveCurrentFilter"
          />
        </label>
        <div class="dialog__actions">
          <button class="btn-ghost-sm" @click="closeSaveDialog">Cancel</button>
          <button class="btn-primary-sm" :disabled="!newFilterName.trim()" @click="saveCurrentFilter">
            <span class="material-icons">save</span>
            Save
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.saved-filters {
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 12px;
  overflow: hidden;
}

.saved-filters__header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.65rem 0.875rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.02);
}

.saved-filters__icon {
  font-size: 1rem;
  color: #7aa2ff;
}

.saved-filters__title {
  font-size: 0.82rem;
  font-weight: 600;
  color: #d1d5db;
  flex: 1;
}

/* ── Filter list ─────────────────────────────────────────────────── */
.filter-list {
  list-style: none;
  margin: 0;
  padding: 0.35rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  max-height: 340px;
  overflow-y: auto;
}

.filter-item {
  border: 1px solid transparent;
  border-radius: 8px;
  transition: border-color 100ms;
}

.filter-item:hover,
.filter-item--expanded {
  border-color: rgba(255, 255, 255, 0.07);
  background: rgba(255, 255, 255, 0.025);
}

.filter-item__row {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.35rem 0.5rem;
}

.filter-item__name {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  background: transparent;
  border: none;
  cursor: pointer;
  color: #d1d5db;
  font: inherit;
  font-size: 0.82rem;
  text-align: left;
  transition: color 100ms;
  padding: 0;
}

.filter-item__name:hover {
  color: #7aa2ff;
}

.filter-item__apply-icon {
  font-size: 0.95rem;
  color: #6b7280;
}

.filter-item__actions {
  display: flex;
  gap: 0.15rem;
}

.icon-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  color: #6b7280;
  display: grid;
  place-items: center;
  border-radius: 6px;
  padding: 2px;
  transition: color 100ms, background 100ms;
}

.icon-btn:hover {
  color: #d1d5db;
  background: rgba(255, 255, 255, 0.06);
}

.icon-btn--danger:hover {
  color: #ef4444;
}

.icon-btn .material-icons {
  font-size: 1rem;
}

.filter-item__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  padding: 0 0.5rem 0.35rem;
}

.chip {
  padding: 0.1rem 0.45rem;
  border-radius: 100px;
  font-size: 0.68rem;
  background: rgba(122, 162, 255, 0.1);
  color: #7aa2ff;
  border: 1px solid rgba(122, 162, 255, 0.2);
}

.filter-item__detail {
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  padding: 0.5rem 0.75rem 0.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.detail-row {
  display: flex;
  gap: 0.5rem;
  align-items: baseline;
}

.detail-row__label {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #6b7280;
  min-width: 56px;
  flex-shrink: 0;
}

.detail-row__value {
  font-size: 0.78rem;
  color: #9ca3af;
  word-break: break-all;
}

.btn-apply {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  margin-top: 0.25rem;
  background: rgba(122, 162, 255, 0.12);
  color: #7aa2ff;
  border: 1px solid rgba(122, 162, 255, 0.3);
  border-radius: 7px;
  padding: 0.35rem 0.75rem;
  font: inherit;
  font-size: 0.78rem;
  cursor: pointer;
  align-self: flex-start;
  transition: background 100ms;
}

.btn-apply:hover {
  background: rgba(122, 162, 255, 0.2);
}

.btn-apply .material-icons {
  font-size: 0.88rem;
}

.filter-empty {
  padding: 0.75rem;
  font-size: 0.78rem;
  color: #6b7280;
  text-align: center;
}

/* ── Buttons ─────────────────────────────────────────────────────── */
.btn-ghost-sm,
.btn-primary-sm {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.3rem 0.65rem;
  border-radius: 6px;
  font: inherit;
  font-size: 0.78rem;
  border: 1px solid transparent;
  cursor: pointer;
}

.btn-ghost-sm {
  background: transparent;
  color: #9ca3af;
  border-color: rgba(255, 255, 255, 0.1);
}

.btn-ghost-sm:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #d1d5db;
}

.btn-ghost-sm .material-icons {
  font-size: 0.9rem;
}

.btn-primary-sm {
  background: #7aa2ff;
  color: #0b0f18;
  font-weight: 600;
}

.btn-primary-sm:hover:not(:disabled) {
  filter: brightness(1.08);
}

.btn-primary-sm:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn-primary-sm .material-icons {
  font-size: 0.9rem;
}

/* ── Dialog ──────────────────────────────────────────────────────── */
.dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(8, 10, 18, 0.7);
  display: grid;
  place-items: center;
  z-index: 200;
  backdrop-filter: blur(4px);
}

.dialog {
  background: #0d1117;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 1.25rem;
  width: min(400px, calc(100vw - 2rem));
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.dialog__title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: #f9fafb;
}

.dialog__label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #6b7280;
}

.dialog__input {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 7px;
  padding: 0.5rem 0.75rem;
  color: #f9fafb;
  font: inherit;
  font-size: 0.88rem;
  text-transform: none;
  letter-spacing: normal;
}

.dialog__input:focus {
  outline: none;
  border-color: rgba(122, 162, 255, 0.5);
}

.dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>

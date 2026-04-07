<script setup lang="ts">
import { computed, ref } from 'vue'

import type { DeadlineState, GrantOpportunity } from '@/types/grants'

const props = defineProps<{
  opportunities: GrantOpportunity[]
  profileId?: string
}>()

const emit = defineEmits<{
  (e: 'select-opportunity', id: string): void
  (e: 'start-proposal', opportunityId: string): void
}>()

const SEA_REGION_CODES = [
  'VN', 'TH', 'ID', 'MY', 'SG', 'PH', 'KH', 'LA', 'MM', 'BN', 'TL',
  'ASEAN', 'APAC', 'GLOBAL',
]

const DEADLINE_COLORS: Record<DeadlineState, { bar: string; text: string; label: string }> = {
  open: { bar: '#22c55e', text: 'text-green-400', label: 'Open' },
  closing_soon: { bar: '#f59e0b', text: 'text-amber-400', label: 'Closing soon' },
  closed: { bar: '#6b7280', text: 'text-gray-400', label: 'Closed' },
  unknown: { bar: '#3b82f6', text: 'text-blue-400', label: 'Unknown' },
  rolling: { bar: '#3b82f6', text: 'text-blue-400', label: 'Rolling' },
}

// ── Filters ────────────────────────────────────────────────────────────
const selectedRegions = ref<string[]>(['VN', 'TH', 'ID', 'MY', 'SG', 'PH', 'KH', 'LA', 'MM', 'BN', 'TL', 'ASEAN', 'APAC', 'GLOBAL'])
const selectedScopes = ref<string[]>([])
const selectedTags = ref<string[]>([])
const selectedDeadlineStates = ref<DeadlineState[]>(['open', 'closing_soon', 'unknown', 'rolling'])

// Derived filter options from opportunity data
const allScopes = computed<string[]>(() => {
  const set = new Set<string>()
  props.opportunities.forEach(o => (o.applicant_scopes ?? []).forEach(s => set.add(s)))
  return Array.from(set).sort()
})

const allTags = computed<string[]>(() => {
  const set = new Set<string>()
  props.opportunities.forEach(o => (o.theme_tags ?? []).forEach(t => set.add(t)))
  return Array.from(set).sort()
})

const allDeadlineStates: DeadlineState[] = ['open', 'closing_soon', 'closed', 'unknown', 'rolling']

function toggleRegion(code: string): void {
  selectedRegions.value = selectedRegions.value.includes(code)
    ? selectedRegions.value.filter(r => r !== code)
    : [...selectedRegions.value, code]
}

function toggleScope(scope: string): void {
  selectedScopes.value = selectedScopes.value.includes(scope)
    ? selectedScopes.value.filter(s => s !== scope)
    : [...selectedScopes.value, scope]
}

function toggleTag(tag: string): void {
  selectedTags.value = selectedTags.value.includes(tag)
    ? selectedTags.value.filter(t => t !== tag)
    : [...selectedTags.value, tag]
}

function toggleDeadlineState(state: DeadlineState): void {
  selectedDeadlineStates.value = selectedDeadlineStates.value.includes(state)
    ? selectedDeadlineStates.value.filter(s => s !== state)
    : [...selectedDeadlineStates.value, state]
}

// ── Filtered opportunities ─────────────────────────────────────────────
const filteredOpportunities = computed<GrantOpportunity[]>(() => {
  return props.opportunities.filter(o => {
    const regionOk = selectedRegions.value.length === 0
      || (o.region_codes ?? o.regions ?? []).some(r => selectedRegions.value.includes(r))
    const scopeOk = selectedScopes.value.length === 0
      || (o.applicant_scopes ?? o.applicant_types ?? []).some(s => selectedScopes.value.includes(s))
    const tagOk = selectedTags.value.length === 0
      || (o.theme_tags ?? o.themes ?? []).some(t => selectedTags.value.includes(t))
    const stateOk = selectedDeadlineStates.value.length === 0
      || selectedDeadlineStates.value.includes((o.deadline_state ?? 'unknown') as DeadlineState)
    return regionOk && scopeOk && tagOk && stateOk
  })
})

// ── Calendar math ──────────────────────────────────────────────────────
const today = new Date()
today.setHours(0, 0, 0, 0)

function parseDate(str: string | null | undefined): Date | null {
  if (!str) return null
  const d = new Date(str)
  return isNaN(d.getTime()) ? null : d
}

interface TimelineEntry {
  opp: GrantOpportunity
  start: Date
  end: Date
  state: DeadlineState
}

const entries = computed<TimelineEntry[]>(() => {
  return filteredOpportunities.value
    .map(o => {
      const end = parseDate(o.deadline_date ?? o.deadline)
      const start = parseDate(o.open_date) ?? (end ? new Date(end.getTime() - 14 * 86400000) : today)
      if (!end) return null
      return {
        opp: o,
        start,
        end,
        state: (o.deadline_state ?? 'unknown') as DeadlineState,
      }
    })
    .filter((e): e is TimelineEntry => e !== null)
    .sort((a, b) => a.end.getTime() - b.end.getTime())
})

// Calendar span: from earliest start or today-7d, to latest end or today+60d
const calStart = computed<Date>(() => {
  const earliest = entries.value.reduce<Date | null>(
    (acc, e) => (!acc || e.start < acc ? e.start : acc),
    null,
  )
  const base = earliest ?? today
  const d = new Date(base)
  d.setDate(1) // align to month start
  return d
})

const calEnd = computed<Date>(() => {
  const latest = entries.value.reduce<Date | null>(
    (acc, e) => (!acc || e.end > acc ? e.end : acc),
    null,
  )
  const base = latest ?? new Date(today.getTime() + 60 * 86400000)
  const d = new Date(base)
  d.setMonth(d.getMonth() + 1)
  d.setDate(0) // last day of that month
  return d
})

const totalDays = computed<number>(() =>
  Math.max(1, Math.floor((calEnd.value.getTime() - calStart.value.getTime()) / 86400000)),
)

interface MonthHeader {
  label: string
  left: number
  width: number
}

const monthHeaders = computed<MonthHeader[]>(() => {
  const headers: MonthHeader[] = []
  const cursor = new Date(calStart.value)
  cursor.setDate(1)
  while (cursor <= calEnd.value) {
    const monthStart = new Date(cursor)
    const monthEnd = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0)
    const startPx = dayOffset(monthStart)
    const endPx = dayOffset(monthEnd) + dayWidth.value
    headers.push({
      label: monthStart.toLocaleDateString('en-US', { month: 'short', year: 'numeric' }),
      left: startPx,
      width: endPx - startPx,
    })
    cursor.setMonth(cursor.getMonth() + 1)
  }
  return headers
})

const TIMELINE_WIDTH = 900 // px virtual width
const dayWidth = computed<number>(() => TIMELINE_WIDTH / totalDays.value)

function dayOffset(date: Date): number {
  const diff = Math.floor((date.getTime() - calStart.value.getTime()) / 86400000)
  return Math.max(0, diff * dayWidth.value)
}

function barStyle(entry: TimelineEntry): Record<string, string> {
  const left = dayOffset(entry.start)
  const right = dayOffset(entry.end) + dayWidth.value
  const width = Math.max(8, right - left)
  const color = DEADLINE_COLORS[entry.state]?.bar ?? '#3b82f6'
  return {
    left: `${left}px`,
    width: `${width}px`,
    background: color,
  }
}

const todayOffset = computed<number>(() => dayOffset(today))

// ── Detail panel ───────────────────────────────────────────────────────
const selectedId = ref<string | null>(null)
const selectedEntry = computed<TimelineEntry | null>(() =>
  entries.value.find(e => e.opp.opportunity_id === selectedId.value) ?? null,
)

function selectBar(entry: TimelineEntry): void {
  selectedId.value = entry.opp.opportunity_id
  emit('select-opportunity', entry.opp.opportunity_id)
}

function closeDetail(): void {
  selectedId.value = null
}

function startProposal(id: string): void {
  emit('start-proposal', id)
  closeDetail()
}

function formatDate(d: Date | null | undefined): string {
  if (!d) return '—'
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}
</script>

<template>
  <div class="timeline-root">
    <!-- Filters bar -->
    <div class="timeline-filters">
      <!-- Region filter -->
      <div class="filter-group">
        <span class="filter-group__label">Region</span>
        <div class="filter-chips">
          <button
            v-for="code in SEA_REGION_CODES"
            :key="code"
            class="chip"
            :class="{ 'chip--active': selectedRegions.includes(code) }"
            @click="toggleRegion(code)"
          >
            {{ code }}
          </button>
        </div>
      </div>

      <!-- Deadline state filter -->
      <div class="filter-group">
        <span class="filter-group__label">Status</span>
        <div class="filter-chips">
          <button
            v-for="state in allDeadlineStates"
            :key="state"
            class="chip"
            :class="{ 'chip--active': selectedDeadlineStates.includes(state as DeadlineState) }"
            :style="selectedDeadlineStates.includes(state as DeadlineState) ? { borderColor: DEADLINE_COLORS[state as DeadlineState].bar, color: DEADLINE_COLORS[state as DeadlineState].bar } : {}"
            @click="toggleDeadlineState(state as DeadlineState)"
          >
            {{ DEADLINE_COLORS[state as DeadlineState].label }}
          </button>
        </div>
      </div>

      <!-- Scope filter -->
      <div v-if="allScopes.length" class="filter-group">
        <span class="filter-group__label">Applicant type</span>
        <div class="filter-chips">
          <button
            v-for="scope in allScopes"
            :key="scope"
            class="chip"
            :class="{ 'chip--active': selectedScopes.includes(scope) }"
            @click="toggleScope(scope)"
          >
            {{ scope }}
          </button>
        </div>
      </div>

      <!-- Tags filter -->
      <div v-if="allTags.length" class="filter-group">
        <span class="filter-group__label">Theme</span>
        <div class="filter-chips">
          <button
            v-for="tag in allTags"
            :key="tag"
            class="chip"
            :class="{ 'chip--active': selectedTags.includes(tag) }"
            @click="toggleTag(tag)"
          >
            {{ tag }}
          </button>
        </div>
      </div>

      <div class="filter-count">
        {{ filteredOpportunities.length }} opportunities
      </div>
    </div>

    <!-- Timeline canvas + detail panel -->
    <div class="timeline-body" :class="{ 'timeline-body--split': selectedId }">
      <div class="timeline-canvas-wrap">
        <!-- Month headers -->
        <div class="timeline-months" :style="{ width: TIMELINE_WIDTH + 'px' }">
          <div
            v-for="(month, i) in monthHeaders"
            :key="i"
            class="timeline-month"
            :style="{ left: month.left + 'px', width: month.width + 'px' }"
          >
            {{ month.label }}
          </div>
        </div>

        <!-- Scrollable rows -->
        <div class="timeline-rows-wrap">
          <div class="timeline-rows" :style="{ width: TIMELINE_WIDTH + 'px' }">
            <!-- Today line -->
            <div
              class="timeline-today"
              :style="{ left: todayOffset + 'px' }"
              aria-label="Today"
            />

            <!-- Empty state -->
            <div v-if="entries.length === 0" class="timeline-empty">
              No opportunities with known deadlines match your filters.
            </div>

            <!-- Row per entry -->
            <div
              v-for="entry in entries"
              :key="entry.opp.opportunity_id"
              class="timeline-row"
              :class="{ 'timeline-row--selected': selectedId === entry.opp.opportunity_id }"
            >
              <button
                class="timeline-bar"
                :style="barStyle(entry)"
                :title="`${entry.opp.title} — ${entry.opp.funder}`"
                @click="selectBar(entry)"
              >
                <span class="timeline-bar__label">{{ entry.opp.title }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Detail panel -->
      <aside v-if="selectedEntry" class="timeline-detail">
        <button class="detail-close" @click="closeDetail" aria-label="Close detail">
          <span class="material-icons">close</span>
        </button>

        <header class="detail-header">
          <span
            class="detail-state-badge"
            :style="{ background: DEADLINE_COLORS[selectedEntry.state].bar + '22', color: DEADLINE_COLORS[selectedEntry.state].bar }"
          >
            {{ DEADLINE_COLORS[selectedEntry.state].label }}
          </span>
          <h3 class="detail-title">{{ selectedEntry.opp.title }}</h3>
          <p class="detail-funder">{{ selectedEntry.opp.funder }}</p>
        </header>

        <dl class="detail-meta">
          <div class="detail-meta__row">
            <dt>Open date</dt>
            <dd>{{ formatDate(selectedEntry.start) }}</dd>
          </div>
          <div class="detail-meta__row">
            <dt>Deadline</dt>
            <dd>{{ formatDate(selectedEntry.end) }}</dd>
          </div>
          <div v-if="selectedEntry.opp.amount" class="detail-meta__row">
            <dt>Amount</dt>
            <dd>{{ selectedEntry.opp.amount }} {{ selectedEntry.opp.currency }}</dd>
          </div>
          <div v-if="(selectedEntry.opp.theme_tags ?? selectedEntry.opp.themes ?? []).length" class="detail-meta__row">
            <dt>Themes</dt>
            <dd class="tag-list">
              <span
                v-for="tag in (selectedEntry.opp.theme_tags ?? selectedEntry.opp.themes ?? [])"
                :key="tag"
                class="tag"
              >{{ tag }}</span>
            </dd>
          </div>
          <div v-if="(selectedEntry.opp.region_codes ?? selectedEntry.opp.regions ?? []).length" class="detail-meta__row">
            <dt>Regions</dt>
            <dd class="tag-list">
              <span
                v-for="r in (selectedEntry.opp.region_codes ?? selectedEntry.opp.regions ?? [])"
                :key="r"
                class="tag"
              >{{ r }}</span>
            </dd>
          </div>
        </dl>

        <p v-if="selectedEntry.opp.summary" class="detail-summary">
          {{ selectedEntry.opp.summary }}
        </p>

        <div class="detail-actions">
          <a
            v-if="selectedEntry.opp.call_url || selectedEntry.opp.source_url"
            :href="selectedEntry.opp.call_url || selectedEntry.opp.source_url"
            target="_blank"
            rel="noopener noreferrer"
            class="btn-ghost"
          >
            <span class="material-icons">open_in_new</span>
            Open call
          </a>
          <button
            class="btn-primary"
            @click="startProposal(selectedEntry.opp.opportunity_id)"
          >
            <span class="material-icons">edit_note</span>
            Start proposal
          </button>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.timeline-root {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  background: #030712;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 14px;
  overflow: hidden;
}

/* ── Filters ───────────────────────────────────────────────────────── */
.timeline-filters {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.875rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.015);
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.filter-group__label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: #6b7280;
  min-width: 90px;
  flex-shrink: 0;
}

.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.chip {
  padding: 0.2rem 0.55rem;
  border-radius: 100px;
  font-size: 0.72rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  transition: background 100ms, color 100ms, border-color 100ms;
}

.chip:hover {
  background: rgba(255, 255, 255, 0.05);
}

.chip--active {
  background: rgba(122, 162, 255, 0.12);
  border-color: rgba(122, 162, 255, 0.45);
  color: #7aa2ff;
}

.filter-count {
  font-size: 0.75rem;
  color: #6b7280;
  margin-top: 0.15rem;
}

/* ── Body layout ───────────────────────────────────────────────────── */
.timeline-body {
  display: flex;
  min-height: 320px;
  overflow: hidden;
}

.timeline-body--split .timeline-canvas-wrap {
  flex: 1;
  min-width: 0;
}

/* ── Canvas ────────────────────────────────────────────────────────── */
.timeline-canvas-wrap {
  flex: 1;
  min-width: 0;
  overflow-x: auto;
  display: flex;
  flex-direction: column;
}

.timeline-months {
  position: relative;
  height: 28px;
  flex-shrink: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.02);
}

.timeline-month {
  position: absolute;
  top: 0;
  height: 100%;
  display: flex;
  align-items: center;
  padding: 0 8px;
  font-size: 0.7rem;
  color: #6b7280;
  border-right: 1px solid rgba(255, 255, 255, 0.05);
  white-space: nowrap;
  overflow: hidden;
}

.timeline-rows-wrap {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

.timeline-rows {
  position: relative;
  min-height: 100%;
  padding: 0.5rem 0;
}

.timeline-today {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1.5px;
  background: #ef4444;
  opacity: 0.7;
  z-index: 2;
  pointer-events: none;
}

.timeline-today::after {
  content: 'today';
  position: absolute;
  top: 2px;
  left: 3px;
  font-size: 0.6rem;
  color: #ef4444;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
}

.timeline-empty {
  padding: 2rem 1rem;
  color: #6b7280;
  font-size: 0.85rem;
  text-align: center;
}

.timeline-row {
  position: relative;
  height: 32px;
  display: flex;
  align-items: center;
  transition: background 80ms;
}

.timeline-row:hover,
.timeline-row--selected {
  background: rgba(255, 255, 255, 0.03);
}

.timeline-bar {
  position: absolute;
  height: 18px;
  border-radius: 100px;
  cursor: pointer;
  border: none;
  padding: 0 8px;
  min-width: 8px;
  overflow: hidden;
  white-space: nowrap;
  display: flex;
  align-items: center;
  transition: filter 120ms, transform 80ms;
  z-index: 1;
}

.timeline-bar:hover {
  filter: brightness(1.15);
  transform: scaleY(1.12);
}

.timeline-bar__label {
  font-size: 0.66rem;
  color: rgba(0, 0, 0, 0.85);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  pointer-events: none;
}

/* ── Detail panel ──────────────────────────────────────────────────── */
.timeline-detail {
  width: 320px;
  flex-shrink: 0;
  border-left: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.02);
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  overflow-y: auto;
  position: relative;
}

.detail-close {
  position: absolute;
  top: 0.6rem;
  right: 0.6rem;
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

.detail-close:hover {
  color: #e5e7eb;
  background: rgba(255, 255, 255, 0.06);
}

.detail-close .material-icons {
  font-size: 1.1rem;
}

.detail-header {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding-right: 1.4rem;
}

.detail-state-badge {
  display: inline-flex;
  align-self: flex-start;
  padding: 0.15rem 0.55rem;
  border-radius: 100px;
  font-size: 0.7rem;
  font-weight: 600;
}

.detail-title {
  margin: 0;
  font-size: 0.92rem;
  font-weight: 600;
  line-height: 1.35;
  color: #f9fafb;
}

.detail-funder {
  margin: 0;
  font-size: 0.78rem;
  color: #9ca3af;
}

.detail-meta {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin: 0;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  padding: 0.6rem 0.75rem;
}

.detail-meta__row {
  display: flex;
  gap: 0.5rem;
  align-items: baseline;
}

.detail-meta__row dt {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #6b7280;
  min-width: 70px;
  flex-shrink: 0;
}

.detail-meta__row dd {
  margin: 0;
  font-size: 0.8rem;
  color: #d1d5db;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.tag {
  background: rgba(122, 162, 255, 0.1);
  color: #7aa2ff;
  border-radius: 4px;
  padding: 0.1rem 0.4rem;
  font-size: 0.68rem;
}

.detail-summary {
  margin: 0;
  font-size: 0.8rem;
  color: #9ca3af;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 5;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.detail-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: auto;
  flex-wrap: wrap;
}

.btn-primary,
.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.45rem 0.85rem;
  border-radius: 7px;
  font: inherit;
  font-size: 0.82rem;
  border: 1px solid transparent;
  cursor: pointer;
  text-decoration: none;
}

.btn-primary {
  background: #7aa2ff;
  color: #0b0f18;
  font-weight: 600;
  border-color: #7aa2ff;
}

.btn-primary:hover {
  filter: brightness(1.08);
}

.btn-ghost {
  background: transparent;
  color: #d1d5db;
  border-color: rgba(255, 255, 255, 0.1);
}

.btn-ghost:hover {
  background: rgba(255, 255, 255, 0.05);
}

.btn-primary .material-icons,
.btn-ghost .material-icons {
  font-size: 0.95rem;
}
</style>

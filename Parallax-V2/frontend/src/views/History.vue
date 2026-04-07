<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { HistoryRun } from '@/types/api'
import { getHistoryRuns, getProjectArtifactDownloadUrl } from '@/api/ais'
import ActionButton from '@/components/shared/ActionButton.vue'
import StatusBadge from '@/components/shared/StatusBadge.vue'
import { STAGE_LABELS, STAGE_ICONS, normalizeStageId, statusToBadgeStatus } from '@/types/pipeline'
import type { StageId } from '@/types/pipeline'
import { resolveRunDestination } from '@/utils/runDestination'

const router = useRouter()

// ── State ───────────────────────────────────────────────────────────────

const runs = ref<HistoryRun[]>([])
const totalCount = ref(0)
const loading = ref(false)
const error = ref<string | null>(null)
const activeFilter = ref<string>('all')
const page = ref(1)
const perPage = 20

const filters = [
  { id: 'all', label: 'All', icon: 'list' },
  { id: 'debate', label: 'Debates', icon: 'forum' },
  { id: 'ais', label: 'Pipeline', icon: 'science' },
  { id: 'paper', label: 'Papers', icon: 'description' },
  { id: 'report', label: 'Reports', icon: 'summarize' },
]

// ── Computed ────────────────────────────────────────────────────────────

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / perPage)))

const canPrev = computed(() => page.value > 1)
const canNext = computed(() => page.value < totalPages.value)

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function normalizeRun(item: HistoryRun): HistoryRun {
  const raw = item as HistoryRun & { query?: string; summary?: Record<string, unknown> }
  const summary = isRecord(raw.summary) ? raw.summary : null

  return {
    ...raw,
    title: raw.title || raw.query || raw.run_id,
    topic: raw.topic || raw.query || '',
    current_stage: normalizeStageId(raw.current_stage ?? summary?.current_stage),
    updated_at: raw.updated_at ?? raw.created_at,
  }
}

// ── Lifecycle ───────────────────────────────────────────────────────────

onMounted(() => {
  fetchRuns()
})

watch([activeFilter, page], () => {
  fetchRuns()
})

// ── Actions ─────────────────────────────────────────────────────────────

async function fetchRuns() {
  loading.value = true
  error.value = null
  try {
    const params: Record<string, unknown> = {
      page: page.value,
      per_page: perPage,
    }
    if (activeFilter.value !== 'all') {
      params.type = activeFilter.value
    }

    const res = await getHistoryRuns(params as { type?: string; page?: number; per_page?: number })
    const data = res.data?.data as { runs?: HistoryRun[]; items?: HistoryRun[]; total?: number } | undefined
    const nextRuns = data?.runs ?? data?.items ?? []
    runs.value = nextRuns.map(normalizeRun)
    totalCount.value = data?.total ?? nextRuns.length
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Failed to load history'
    if (msg.includes('Network Error') || msg.includes('timeout')) {
      error.value = 'Backend unreachable — start the Flask server on :5002'
    } else {
      error.value = msg
    }
    runs.value = []
  } finally {
    loading.value = false
  }
}

function setFilter(filterId: string) {
  activeFilter.value = filterId
  page.value = 1
}

function navigateToProject(run: HistoryRun) {
  const destination = resolveRunDestination({
    runId: run.run_id,
    type: run.type,
    source: run.source,
    uploadId: run.upload_id,
    reportBaseUrl: import.meta.env.VITE_API_BASE_URL || '',
  })

  if (destination.kind === 'external') {
    window.open(destination.href, '_blank')
    return
  }

  router.push(destination.to)
}

function canExportFullArtifact(run: HistoryRun): boolean {
  return run.type === 'ais' || run.run_id.startsWith('ais_run_')
}

function downloadFullArtifact(run: HistoryRun, format: 'html' | 'pdf') {
  if (!canExportFullArtifact(run)) return
  try {
    const url = getProjectArtifactDownloadUrl(run.run_id, format)
    const a = document.createElement('a')
    a.href = url
    a.style.display = 'none'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  } catch (err) {
    console.error('Full artifact export failed:', err)
  }
}

function prevPage() {
  if (canPrev.value) page.value--
}

function nextPage() {
  if (canNext.value) page.value++
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function typeColor(type: string): string {
  const map: Record<string, string> = {
    ais: 'var(--os-brand)',
    debate: 'var(--info)',
    paper: 'var(--warning)',
    paper_rehab: 'var(--warning)',
    report: 'var(--role-phd)',
  }
  return map[type] ?? 'var(--text-tertiary)'
}

function statusForBadge(status: string): 'done' | 'active' | 'pending' | 'failed' {
  return statusToBadgeStatus(status)
}
</script>

<template>
  <div class="history">
    <div class="history__header">
      <h1 class="history__title">History</h1>
      <span class="history__count font-mono">{{ totalCount }} runs</span>
    </div>

    <!-- ── Filter Tabs ── -->
    <div class="filter-tabs">
      <button
        v-for="filter in filters"
        :key="filter.id"
        class="filter-tab"
        :class="{ 'filter-tab--active': activeFilter === filter.id }"
        @click="setFilter(filter.id)"
      >
        <span class="material-symbols-outlined" style="font-size: 16px">{{ filter.icon }}</span>
        <span>{{ filter.label }}</span>
      </button>
    </div>

    <!-- ── Loading ── -->
    <div v-if="loading" class="loading-container">
      <span class="material-symbols-outlined spin">progress_activity</span>
      <span>Loading history...</span>
    </div>

    <!-- ── Error ── -->
    <div v-else-if="error" class="error-state">
      <span class="material-symbols-outlined" style="font-size: 36px; color: var(--error)">cloud_off</span>
      <p style="font-size: 14px; font-weight: 600; color: var(--text-primary); margin: 0">{{ error }}</p>
      <button class="retry-btn" @click="fetchRuns">
        <span class="material-symbols-outlined" style="font-size: 16px">refresh</span>
        Retry
      </button>
    </div>

    <!-- ── Empty ── -->
    <div v-else-if="runs.length === 0" class="empty-state">
      <span class="material-symbols-outlined" style="font-size: 40px">history</span>
      <p>No runs found{{ activeFilter !== 'all' ? ` for "${activeFilter}"` : '' }}</p>
    </div>

    <!-- ── Run List ── -->
    <div v-else class="runs-list">
      <div
        v-for="run in runs"
        :key="run.run_id"
        class="run-item"
        role="button"
        tabindex="0"
        @click="navigateToProject(run)"
        @keydown.enter="navigateToProject(run)"
        @keydown.space.prevent="navigateToProject(run)"
      >
        <div class="run-item__left">
          <span
            class="run-item__type"
            :style="{ color: typeColor(run.type), borderColor: typeColor(run.type) }"
          >
            {{ run.type.replace('_', ' ') }}
          </span>
          <div class="run-item__info">
            <span class="run-item__title">{{ run.title || run.topic || run.run_id }}</span>
            <span class="run-item__topic">{{ run.topic }}</span>
          </div>
        </div>

        <div class="run-item__right">
          <!-- Stage indicator -->
          <span
            v-if="run.current_stage"
            class="run-item__stage"
          >
            <span class="material-symbols-outlined" style="font-size: 14px">
              {{ STAGE_ICONS[run.current_stage as StageId] || 'circle' }}
            </span>
            {{ STAGE_LABELS[run.current_stage as StageId] || run.current_stage }}
          </span>

          <StatusBadge
            :status="statusForBadge(run.status)"
            :label="run.status"
            size="sm"
          />

          <div v-if="canExportFullArtifact(run)" class="run-item__actions">
            <button
              type="button"
              class="run-item__download"
              @click.stop="downloadFullArtifact(run, 'html')"
            >
              Full HTML
            </button>
            <button
              type="button"
              class="run-item__download"
              @click.stop="downloadFullArtifact(run, 'pdf')"
            >
              Full PDF
            </button>
          </div>

          <span class="run-item__date font-mono">{{ formatDate(run.created_at) }}</span>

          <span class="material-symbols-outlined run-item__arrow">chevron_right</span>
        </div>
      </div>
    </div>

    <!-- ── Pagination ── -->
    <div v-if="totalPages > 1" class="pagination">
      <ActionButton
        variant="ghost"
        size="sm"
        icon="chevron_left"
        :disabled="!canPrev"
        @click="prevPage"
      />
      <span class="pagination__info font-mono">
        {{ page }} / {{ totalPages }}
      </span>
      <ActionButton
        variant="ghost"
        size="sm"
        icon="chevron_right"
        :disabled="!canNext"
        @click="nextPage"
      />
    </div>
  </div>
</template>

<style scoped>
.history {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px;
  max-width: 1000px;
  margin: 0 auto;
  width: 100%;
}

.history__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.history__title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.02em;
}

.history__count {
  font-size: 12px;
  color: var(--text-tertiary);
  padding: 3px 10px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-pill);
}

/* ── Filter Tabs ── */
.filter-tabs {
  display: flex;
  gap: 4px;
  padding: 3px;
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-secondary);
  overflow-x: auto;
}

.filter-tab {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 14px;
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background: none;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--transition-fast);
}

.filter-tab:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.filter-tab--active {
  color: var(--text-on-brand);
  background: var(--os-brand);
}

.filter-tab--active:hover {
  color: var(--text-on-brand);
  background: var(--os-brand-hover);
}

/* ── Run List ── */
.runs-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.run-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-family: var(--font-sans);
  text-align: left;
  width: 100%;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.run-item:hover {
  border-color: var(--border-primary);
  background: var(--bg-hover);
  box-shadow: var(--shadow-sm);
  transform: translateX(2px);
}

.run-item__left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  flex: 1;
}

.run-item__type {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 2px 8px;
  border: 1px solid;
  border-radius: var(--radius-pill);
  white-space: nowrap;
  flex-shrink: 0;
}

.run-item__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.run-item__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-item__topic {
  font-size: 11px;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-item__right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.run-item__actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.run-item__download {
  border: 1px solid var(--border-primary);
  background: var(--bg-elevated);
  color: var(--text-secondary);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  border-radius: var(--radius-pill);
  padding: 3px 8px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.run-item__download:hover {
  border-color: var(--os-brand);
  color: var(--os-brand);
  background: var(--os-brand-light);
}

.run-item__stage {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.run-item__date {
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.run-item__arrow {
  font-size: 18px;
  color: var(--text-tertiary);
  transition: transform var(--transition-fast);
}

.run-item:hover .run-item__arrow {
  transform: translateX(2px);
  color: var(--os-brand);
}

/* ── Pagination ── */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding-top: 8px;
}

.pagination__info {
  font-size: 12px;
  color: var(--text-secondary);
}

/* ── States ── */
.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 60px 24px;
  color: var(--text-secondary);
  font-size: 14px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 60px 24px;
  color: var(--text-tertiary);
  text-align: center;
}

.empty-state p {
  font-size: 13px;
  margin: 0;
}

.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 40px 24px;
  background: rgba(239, 68, 68, 0.04);
  border: 1px solid rgba(239, 68, 68, 0.15);
  border-radius: var(--radius-lg);
  text-align: center;
}

.retry-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 500;
  padding: 6px 14px;
  color: var(--os-brand);
  background: none;
  border: 1px solid var(--os-brand);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.retry-btn:hover {
  background: var(--os-brand-light);
}

.spin {
  animation: btn-spin 1s linear infinite;
}

@keyframes btn-spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 768px) {
  .run-item {
    flex-direction: column;
    align-items: flex-start;
  }

  .run-item__right {
    flex-wrap: wrap;
    gap: 8px;
  }
}
</style>

<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import ProgressBar from '@/components/shared/ProgressBar.vue'
import MetricCard from '@/components/shared/MetricCard.vue'
import { getRunPapers } from '@/api/ais'
import type { RunPaper, PaperSortBy } from '@/api/ais'

const props = defineProps<{
  result: Record<string, unknown>
  runId?: string
}>()

// ── Paper Browser State ────────────────────────────────────────────────
const papers = ref<RunPaper[]>([])
const papersTotal = ref(0)
const papersPage = ref(1)
const papersTotalPages = ref(1)
const papersPerPage = 10
const papersSearch = ref('')
const papersLoading = ref(false)
const papersError = ref<string | null>(null)
const expandedPaperId = ref<string | null>(null)

// Sorting + filtering
const sortBy = ref<PaperSortBy>('citations')
const sourceFilter = ref('')
const availableSources = ref<string[]>([])

function formatAuthors(authors: string[]): string {
  if (!authors || authors.length === 0) return 'Unknown'
  if (authors.length === 1) return authors[0] ?? 'Unknown'
  const firstAuthor = authors[0] ?? 'Unknown'
  const first = firstAuthor.split(' ').pop() ?? firstAuthor
  return `${first} et al.`
}

function toggleAbstract(paperId: string) {
  expandedPaperId.value = expandedPaperId.value === paperId ? null : paperId
}

async function fetchPapers() {
  if (!props.runId) return
  papersLoading.value = true
  papersError.value = null
  try {
    const res = await getRunPapers(props.runId, {
      page: papersPage.value,
      per_page: papersPerPage,
      search: papersSearch.value || undefined,
      sort_by: sortBy.value,
      source: sourceFilter.value || undefined,
    })
    const data = res.data.data
    papers.value = data.papers
    papersTotal.value = data.total
    papersPage.value = data.page
    papersTotalPages.value = data.pages
    if (data.available_sources) {
      availableSources.value = data.available_sources
    }
  } catch (err: unknown) {
    papersError.value = err instanceof Error ? err.message : 'Failed to load papers'
    papers.value = []
  } finally {
    papersLoading.value = false
  }
}

function setSortBy(col: PaperSortBy) {
  sortBy.value = col
  papersPage.value = 1
  fetchPapers()
}

function setSourceFilter(source: string) {
  sourceFilter.value = sourceFilter.value === source ? '' : source
  papersPage.value = 1
  fetchPapers()
}

function prevPage() {
  if (papersPage.value > 1) {
    papersPage.value--
    fetchPapers()
  }
}

function nextPage() {
  if (papersPage.value < papersTotalPages.value) {
    papersPage.value++
    fetchPapers()
  }
}

let searchTimeout: ReturnType<typeof setTimeout> | null = null
function onSearchInput() {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    papersPage.value = 1
    fetchPapers()
  }, 300)
}

onUnmounted(() => {
  if (searchTimeout) clearTimeout(searchTimeout)
})

watch(() => props.runId, (id) => {
  if (id) {
    papersPage.value = 1
    papersSearch.value = ''
    fetchPapers()
  }
}, { immediate: true })

interface SourceProgress {
  name: string
  found: number
  total: number
  percent: number
}

const crawlConfig = computed(() => {
  const raw = props.result.config as Record<string, unknown> | undefined
  return raw && typeof raw === 'object' ? raw : {}
})

const totalPapers = computed(() => {
  return (
    (props.result.total_papers as number)
    ?? (props.result.papers_found as number)
    ?? (crawlConfig.value.max_papers as number)
    ?? 0
  )
})

const estimatedTime = computed(() => {
  return (props.result.estimated_time as string) ?? null
})

const taskProgress = computed(() => {
  return (props.result.task_progress as number) ?? 0
})

const taskMessage = computed(() => {
  return (props.result.task_message as string) ?? ''
})

const configuredSources = computed<string[]>(() => {
  const explicit = props.result.configured_sources
  if (Array.isArray(explicit)) {
    return explicit.map((source) => String(source))
  }

  const configSources = crawlConfig.value.sources
  if (Array.isArray(configSources)) {
    return configSources.map((source) => String(source))
  }

  return []
})

const sources = computed<SourceProgress[]>(() => {
  const raw = props.result.sources as Record<string, unknown> | undefined
  if (!raw || typeof raw !== 'object') {
    // Build from known source keys
    const fallback: SourceProgress[] = []
    const sourceNames = ['arxiv', 'semantic_scholar', 'crossref', 'pubmed']
    for (const name of sourceNames) {
      if (props.result[name] !== undefined) {
        const count = (props.result[name] as number) ?? 0
        fallback.push({
          name: name.replace('_', ' '),
          found: count,
          total: totalPapers.value || count,
          percent: totalPapers.value ? Math.round((count / totalPapers.value) * 100) : 100,
        })
      }
    }
    return fallback
  }

  return Object.entries(raw).map(([name, value]) => {
    const count = typeof value === 'number' ? value : ((value as Record<string, unknown>)?.count as number) ?? 0
    const total = typeof value === 'number' ? totalPapers.value : ((value as Record<string, unknown>)?.total as number) ?? totalPapers.value
    return {
      name: name.replace('_', ' '),
      found: count,
      total: total || 1,
      percent: total ? Math.round((count / total) * 100) : 0,
    }
  })
})

const sourceColors: Record<string, string> = {
  arxiv: 'var(--info)',
  'semantic scholar': 'var(--os-brand)',
  crossref: 'var(--warning)',
  pubmed: 'var(--role-phd)',
}

const sourceCount = computed(() => sources.value.length || configuredSources.value.length)
</script>

<template>
  <div class="crawl-detail">
    <div class="crawl-detail__metrics">
      <MetricCard
        label="Total Papers"
        :value="totalPapers"
        icon="article"
      />
      <MetricCard
        v-if="estimatedTime"
        label="Est. Time"
        :value="estimatedTime"
        icon="schedule"
      />
      <MetricCard
        label="Sources"
        :value="sourceCount"
        icon="dns"
      />
    </div>

    <div v-if="taskMessage || taskProgress > 0" class="crawl-detail__live">
      <div class="crawl-detail__live-header">
        <span class="detail-heading">Crawl Progress</span>
        <span v-if="taskProgress > 0" class="crawl-detail__progress font-mono">{{ taskProgress }}%</span>
      </div>
      <p v-if="taskMessage" class="crawl-detail__message">{{ taskMessage }}</p>
      <ProgressBar v-if="taskProgress > 0" :progress="taskProgress" height="6px" />
    </div>

    <div v-if="sources.length > 0" class="crawl-detail__sources">
      <h5 class="detail-heading">Source Progress</h5>
      <div
        v-for="source in sources"
        :key="source.name"
        class="source-row"
      >
        <div class="source-row__header">
          <span class="source-row__name">{{ source.name }}</span>
          <span class="source-row__count font-mono">{{ source.found }}</span>
        </div>
        <ProgressBar
          :progress="source.percent"
          :color="sourceColors[source.name.toLowerCase()] || 'var(--os-brand)'"
          height="5px"
        />
      </div>
    </div>

    <div v-else-if="configuredSources.length > 0" class="crawl-detail__configured">
      <h5 class="detail-heading">Configured Sources</h5>
      <div class="crawl-detail__chips">
        <span
          v-for="source in configuredSources"
          :key="source"
          class="crawl-detail__chip"
        >
          {{ source.replace(/_/g, ' ') }}
        </span>
      </div>
    </div>

    <div v-else class="crawl-detail__empty">
      <span class="material-symbols-outlined" style="font-size: 24px; color: var(--text-tertiary)">search_off</span>
      <span>No crawl data available yet</span>
    </div>

    <!-- Paper Browser -->
    <div v-if="runId" class="paper-browser">
      <div class="paper-browser__header">
        <h5 class="detail-heading">Papers</h5>
        <span class="paper-browser__total font-mono">{{ papersTotal }}</span>
      </div>

      <div class="paper-browser__controls">
        <div class="paper-browser__search">
          <span class="material-symbols-outlined paper-browser__search-icon">search</span>
          <input
            v-model="papersSearch"
            class="paper-browser__search-input"
            type="text"
            placeholder="Search papers..."
            @input="onSearchInput"
          />
        </div>

        <div class="paper-browser__sort">
          <span class="paper-browser__sort-label">Sort:</span>
          <button
            v-for="col in (['citations', 'year', 'title'] as const)"
            :key="col"
            class="paper-browser__sort-btn"
            :class="{ 'paper-browser__sort-btn--active': sortBy === col }"
            @click="setSortBy(col)"
          >
            {{ col === 'citations' ? 'Citations' : col === 'year' ? 'Year' : 'Title' }}
          </button>
        </div>

        <div v-if="availableSources.length > 1" class="paper-browser__source-filter">
          <span class="paper-browser__sort-label">Source:</span>
          <button
            v-for="src in availableSources"
            :key="src"
            class="paper-browser__source-chip"
            :class="{ 'paper-browser__source-chip--active': sourceFilter === src }"
            @click="setSourceFilter(src)"
          >
            {{ src.replace(/_/g, ' ') }}
          </button>
        </div>
      </div>

      <div v-if="papersLoading" class="paper-browser__loading">
        <span class="material-symbols-outlined paper-browser__spinner">progress_activity</span>
        <span>Loading papers...</span>
      </div>

      <div v-else-if="papersError" class="paper-browser__error">
        <span class="material-symbols-outlined" style="font-size: 16px">error_outline</span>
        <span>{{ papersError }}</span>
      </div>

      <div v-else-if="papers.length === 0" class="paper-browser__empty">
        <span>No papers found</span>
      </div>

      <div v-else class="paper-browser__list">
        <div
          v-for="paper in papers"
          :key="paper.paper_id"
          class="paper-card"
          @click="toggleAbstract(paper.paper_id)"
        >
          <div class="paper-card__title">{{ paper.title }}</div>
          <div class="paper-card__meta">
            <span class="paper-card__authors">{{ formatAuthors(paper.authors) }}</span>
            <span v-if="paper.year" class="paper-card__year">{{ paper.year }}</span>
            <span v-if="paper.source" class="paper-card__source-badge">{{ paper.source }}</span>
          </div>
          <div class="paper-card__stats">
            <span v-if="paper.citation_count != null" class="paper-card__citations">
              <span class="material-symbols-outlined" style="font-size: 13px">format_quote</span>
              {{ paper.citation_count }}
            </span>
            <a
              v-if="paper.doi"
              class="paper-card__doi"
              :href="`https://doi.org/${paper.doi}`"
              target="_blank"
              rel="noopener"
              @click.stop
            >
              DOI
            </a>
          </div>
          <div v-if="expandedPaperId === paper.paper_id && paper.abstract" class="paper-card__abstract">
            {{ paper.abstract }}
          </div>
        </div>
      </div>

      <div v-if="papersTotalPages > 1" class="paper-browser__pagination">
        <button
          class="paper-browser__page-btn"
          :disabled="papersPage <= 1"
          @click="prevPage"
        >
          <span class="material-symbols-outlined" style="font-size: 16px">chevron_left</span>
          Prev
        </button>
        <span class="paper-browser__page-info font-mono">{{ papersPage }} / {{ papersTotalPages }}</span>
        <button
          class="paper-browser__page-btn"
          :disabled="papersPage >= papersTotalPages"
          @click="nextPage"
        >
          Next
          <span class="material-symbols-outlined" style="font-size: 16px">chevron_right</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.crawl-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 14px;
}

.crawl-detail__metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
}

.detail-heading {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin: 0 0 8px;
}

.crawl-detail__sources {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.crawl-detail__live {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
}

.crawl-detail__live-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.crawl-detail__progress {
  font-size: 11px;
  color: var(--text-secondary);
}

.crawl-detail__message {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.source-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
}

.source-row__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.source-row__name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  text-transform: capitalize;
}

.source-row__count {
  font-size: 11px;
  color: var(--text-secondary);
}

.crawl-detail__configured {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.crawl-detail__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.crawl-detail__chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: var(--radius-pill);
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  font-size: 12px;
  color: var(--text-primary);
  text-transform: capitalize;
}

.crawl-detail__empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 20px;
  color: var(--text-tertiary);
  font-size: 13px;
  justify-content: center;
}

/* ── Paper Browser ──────────────────────────────────────────────────── */

.paper-browser {
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-top: 1px solid var(--border-secondary);
  padding-top: 16px;
}

.paper-browser__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.paper-browser__header .detail-heading {
  margin: 0;
}

.paper-browser__total {
  font-size: 11px;
  color: var(--text-secondary);
}

.paper-browser__controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.paper-browser__sort,
.paper-browser__source-filter {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.paper-browser__sort-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-tertiary);
  margin-right: 2px;
}

.paper-browser__sort-btn {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-pill, 999px);
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease;
}

.paper-browser__sort-btn:hover {
  border-color: var(--text-tertiary);
  color: var(--text-primary);
}

.paper-browser__sort-btn--active {
  background: color-mix(in srgb, var(--os-brand) 12%, transparent);
  border-color: var(--os-brand);
  color: var(--os-brand);
}

.paper-browser__source-chip {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  font-size: 10px;
  font-weight: 600;
  text-transform: capitalize;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-pill, 999px);
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease;
}

.paper-browser__source-chip:hover {
  border-color: var(--text-tertiary);
  color: var(--text-primary);
}

.paper-browser__source-chip--active {
  background: color-mix(in srgb, var(--os-brand) 12%, transparent);
  border-color: var(--os-brand);
  color: var(--os-brand);
}

.paper-browser__search {
  position: relative;
  display: flex;
  align-items: center;
}

.paper-browser__search-icon {
  position: absolute;
  left: 10px;
  font-size: 16px;
  color: var(--text-tertiary);
  pointer-events: none;
}

.paper-browser__search-input {
  width: 100%;
  padding: 7px 10px 7px 32px;
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  outline: none;
  transition: border-color 0.15s ease;
}

.paper-browser__search-input::placeholder {
  color: var(--text-tertiary);
}

.paper-browser__search-input:focus {
  border-color: var(--os-brand);
}

.paper-browser__loading,
.paper-browser__error,
.paper-browser__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 16px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.paper-browser__error {
  color: var(--danger, #ef4444);
}

.paper-browser__spinner {
  font-size: 18px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.paper-browser__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.paper-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color 0.15s ease;
}

.paper-card:hover {
  border-color: var(--text-tertiary);
}

.paper-card__title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
}

.paper-card__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.paper-card__authors {
  font-size: 11px;
  color: var(--text-secondary);
}

.paper-card__year {
  font-size: 11px;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.paper-card__source-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--os-brand);
  background: color-mix(in srgb, var(--os-brand) 12%, transparent);
  border-radius: var(--radius-pill, 999px);
}

.paper-card__stats {
  display: flex;
  align-items: center;
  gap: 10px;
}

.paper-card__citations {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.paper-card__doi {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--info, #3b82f6);
  text-decoration: none;
  transition: opacity 0.15s ease;
}

.paper-card__doi:hover {
  opacity: 0.75;
}

.paper-card__abstract {
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px solid var(--border-secondary);
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-secondary);
}

.paper-browser__pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding-top: 4px;
}

.paper-browser__page-btn {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease;
}

.paper-browser__page-btn:hover:not(:disabled) {
  border-color: var(--text-tertiary);
  color: var(--text-primary);
}

.paper-browser__page-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.paper-browser__page-info {
  font-size: 11px;
  color: var(--text-tertiary);
}
</style>

<script setup lang="ts">
import { computed, ref, onUnmounted } from 'vue'
import MetricCard from '@/components/shared/MetricCard.vue'
import ActionButton from '@/components/shared/ActionButton.vue'
import { approveDraft, runSpecialistReview, getPipelineStatus } from '@/api/ais'
import type { SpecialistReviewResult } from '@/api/ais'
import FigureCritiquePanel from '@/components/stages/FigureCritiquePanel.vue'
import ConsistencyReport from '@/components/review/ConsistencyReport.vue'
import { usePipelineStore } from '@/stores/pipeline'

const props = defineProps<{
  result: Record<string, unknown>
  runId?: string
}>()

const pipeline = usePipelineStore()
const approving = ref(false)
const approveError = ref<string | null>(null)

const debateReadyForApproval = computed(() => {
  const debate = pipeline.stageResults['debate']
  if (!debate || typeof debate !== 'object') return false
  const record = debate as Record<string, unknown>
  return typeof record.simulation_id === 'string'
    || typeof record.agent_count === 'number'
    || typeof record.rounds_completed === 'number'
})

const canApprove = computed(() => {
  if (!props.runId) return false
  return pipeline.projectStatus === 'human_review' && debateReadyForApproval.value
})

async function handleApprove() {
  if (!props.runId || approving.value) return
  approving.value = true
  approveError.value = null
  try {
    await approveDraft(props.runId)
    await pipeline.refreshStages()
  } catch (err) {
    approveError.value = err instanceof Error ? err.message : 'Failed to approve'
  } finally {
    approving.value = false
  }
}

const isNovel = computed(() => {
  const novelty = props.result.novelty as string | boolean | undefined
  if (typeof novelty === 'boolean') return novelty
  if (typeof novelty === 'string') return novelty.toLowerCase() === 'novel'
  return (props.result.is_novel as boolean) ?? null
})

const noveltyLabel = computed(() => {
  if (isNovel.value === null) return 'Unknown'
  return isNovel.value ? 'NOVEL' : 'NOT NOVEL'
})

const papersFound = computed(() => (props.result.papers_found as number) ?? (props.result.similar_papers as number) ?? 0)

interface ResearchGap {
  description: string
  score?: number
}

const gaps = computed<ResearchGap[]>(() => {
  const raw = props.result.research_gaps as ResearchGap[] | string[] | undefined
  if (!raw || !Array.isArray(raw)) return []
  return raw.map((g) =>
    typeof g === 'string' ? { description: g } : g,
  )
})

interface SotaEntry {
  method: string
  metric: string
  value: string | number
  source?: string
}

const sotaTable = computed<SotaEntry[]>(() => {
  const raw = props.result.sota_comparison as SotaEntry[] | undefined
  if (!raw || !Array.isArray(raw)) return []
  return raw
})

const hasData = computed(() =>
  isNovel.value !== null || papersFound.value > 0 || gaps.value.length > 0 || sotaTable.value.length > 0,
)

// ── Specialist Review ──
const specialistLoading = ref(false)
const specialistError = ref<string | null>(null)
interface SpecialistReviewPayload {
  reviews?: SpecialistReviewResult[]
  domain_count?: number
  total_findings?: number
}

const specialistResult = ref<SpecialistReviewPayload | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const specialistReviews = computed<SpecialistReviewResult[]>(() => {
  return specialistResult.value?.reviews ?? []
})

function clearPollTimer() {
  if (pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onUnmounted(() => clearPollTimer())

async function handleSpecialistReview() {
  if (!props.runId || specialistLoading.value) return
  specialistLoading.value = true
  specialistError.value = null
  specialistResult.value = null

  try {
    await runSpecialistReview(props.runId, { target: 'idea', strictness: 0.7 })

    // Poll for results every 3 seconds (max 60 polls = 3 min)
    clearPollTimer()
    let pollCount = 0
    pollTimer = setInterval(async () => {
      pollCount++
      if (pollCount >= 60) {
        specialistError.value = 'Specialist review timed out after 3 minutes'
        specialistLoading.value = false
        clearPollTimer()
        return
      }
      try {
        const res = await getPipelineStatus(props.runId!)
        const sr = res.data?.data?.stage_results?.specialist_review as Record<string, unknown> | undefined
        if (sr && Array.isArray(sr.reviews)) {
          specialistResult.value = sr as unknown as SpecialistReviewPayload
          specialistLoading.value = false
          clearPollTimer()
        }
      } catch {
        // keep polling on transient errors
      }
    }, 3000)
  } catch (err) {
    specialistError.value = err instanceof Error ? err.message : 'Failed to start specialist review'
    specialistLoading.value = false
  }
}

function severityColor(severity: string): string {
  switch (severity) {
    case 'critical': return 'var(--error)'
    case 'major': return 'var(--warning)'
    case 'minor': return 'var(--info)'
    default: return 'var(--text-secondary)'
  }
}

// ── Figure Analysis (P-4) ──
const figureLoading = ref(false)
const figureResult = ref<Record<string, unknown> | null>(null)
const consistencyResult = ref<Record<string, unknown> | null>(null)

async function handleAnalyzeFigures() {
  if (!props.runId || figureLoading.value) return
  figureLoading.value = true
  try {
    // Use P-4 figure critique endpoint (not the V2 multimodal analyzer)
    const { default: client } = await import('@/api/client')
    await client.post(`/api/research/ais/${props.runId}/figures/critique`, { figures: [] }, { timeout: 120000 })
      .then(res => {
        figureResult.value = res.data?.data ?? null
        figureLoading.value = false
      })
  } catch {
    figureLoading.value = false
  }
}
</script>

<template>
  <div class="validation-detail">
    <template v-if="hasData">
      <div class="validation-detail__top">
        <!-- Novelty Badge -->
        <div
          class="novelty-badge"
          :class="{
            'novelty-badge--novel': isNovel === true,
            'novelty-badge--not-novel': isNovel === false,
            'novelty-badge--unknown': isNovel === null,
          }"
        >
          <span class="material-symbols-outlined" style="font-size: 18px">
            {{ isNovel === true ? 'new_releases' : isNovel === false ? 'block' : 'help' }}
          </span>
          <span class="novelty-badge__label">{{ noveltyLabel }}</span>
        </div>

        <MetricCard
          label="Similar Papers"
          :value="papersFound"
          icon="content_copy"
        />
      </div>

      <!-- Research Gaps -->
      <div v-if="gaps.length > 0" class="validation-section">
        <h5 class="detail-heading">Research Gaps ({{ gaps.length }})</h5>
        <ul class="gap-list">
          <li
            v-for="(gap, i) in gaps"
            :key="i"
            class="gap-item"
          >
            <span class="material-symbols-outlined gap-item__icon">lightbulb</span>
            <span class="gap-item__text">{{ gap.description }}</span>
            <span v-if="gap.score" class="gap-item__score font-mono">
              {{ gap.score.toFixed(1) }}
            </span>
          </li>
        </ul>
      </div>

      <!-- SOTA Comparison -->
      <div v-if="sotaTable.length > 0" class="validation-section">
        <h5 class="detail-heading">SOTA Comparison</h5>
        <div class="sota-table-wrap">
          <table class="sota-table">
            <thead>
              <tr>
                <th>Method</th>
                <th>Metric</th>
                <th>Value</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in sotaTable" :key="i">
                <td>{{ row.method }}</td>
                <td class="font-mono">{{ row.metric }}</td>
                <td class="font-mono">{{ row.value }}</td>
                <td>{{ row.source || '--' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Specialist Review -->
      <div class="validation-section specialist-review">
        <h5 class="detail-heading">Specialist Review</h5>

        <ActionButton
          v-if="!specialistResult && !specialistLoading"
          variant="secondary"
          icon="group"
          :disabled="!runId"
          @click="handleSpecialistReview"
        >
          Run Specialist Review
        </ActionButton>

        <div v-if="specialistLoading" class="specialist-review__loading">
          <span class="specialist-review__spinner"></span>
          <span class="specialist-review__loading-text">Running specialist review&hellip;</span>
        </div>

        <div v-if="specialistError" class="specialist-review__error">{{ specialistError }}</div>

        <div v-if="specialistResult" class="specialist-review__results">
          <div
            v-for="(domain, dIdx) in specialistReviews"
            :key="dIdx"
            class="specialist-card"
          >
            <div class="specialist-card__header">
              <span class="specialist-card__badge">{{ domain.domain }}</span>
              <span v-if="domain.specialist_name" class="specialist-card__name">{{ domain.specialist_name }}</span>
              <span
                v-if="domain.overall_score != null"
                class="specialist-card__score font-mono"
                :style="{ color: domain.overall_score >= 7 ? 'var(--success)' : domain.overall_score >= 4 ? 'var(--warning)' : 'var(--error)' }"
              >
                {{ domain.overall_score }}/10
              </span>
            </div>

            <p v-if="domain.summary" class="specialist-card__summary">{{ domain.summary }}</p>

            <ul v-if="domain.findings && domain.findings.length > 0" class="findings-list">
              <li
                v-for="(finding, fIdx) in domain.findings"
                :key="fIdx"
                class="finding-item"
              >
                <span
                  class="finding-item__severity"
                  :style="{ background: severityColor(finding.severity), color: '#fff' }"
                >
                  {{ finding.severity }}
                </span>
                <span v-if="finding.category" class="finding-item__category">{{ finding.category }}</span>
                <span class="finding-item__desc">{{ finding.description }}</span>
                <span v-if="finding.recommendation" class="finding-item__rec">
                  <span class="material-symbols-outlined" style="font-size: 14px; vertical-align: middle">tips_and_updates</span>
                  {{ finding.recommendation }}
                </span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </template>

    <!-- P-4: Figure Analysis + Consistency -->
    <div v-if="runId" class="validation-section">
      <div class="validation-section__header">
        <h5 class="detail-heading">Figure & Consistency Analysis</h5>
        <ActionButton
          v-if="!figureResult"
          variant="secondary"
          size="sm"
          icon="image_search"
          :loading="figureLoading"
          @click="handleAnalyzeFigures"
        >
          Analyze Figures
        </ActionButton>
      </div>
      <FigureCritiquePanel v-if="figureResult" :result="figureResult" :run-id="runId" />
      <ConsistencyReport v-if="consistencyResult" :data="consistencyResult" />
    </div>

    <div v-if="!hasData" class="validation-detail__empty">
      <span class="material-symbols-outlined" style="font-size: 24px; color: var(--text-tertiary)">verified</span>
      <span>No validation data available yet</span>
    </div>

    <!-- Approve & proceed to drafting -->
    <div v-if="canApprove" class="validation-approve">
      <div class="validation-approve__info">
        <span class="material-symbols-outlined" style="font-size: 20px; color: var(--os-brand)">task_alt</span>
        <div>
          <strong>Debate complete — ready for paper drafting</strong>
          <span class="validation-approve__desc">Approve to proceed to Stage 5: Paper Draft generation.</span>
        </div>
      </div>
      <ActionButton
        variant="primary"
        icon="arrow_forward"
        :loading="approving"
        @click="handleApprove"
      >
        Approve &amp; Draft
      </ActionButton>
      <div v-if="approveError" class="validation-approve__error">{{ approveError }}</div>
    </div>
  </div>
</template>

<style scoped>
.validation-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 14px;
}

.validation-detail__top {
  display: flex;
  align-items: stretch;
  gap: 12px;
  flex-wrap: wrap;
}

.detail-heading {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin: 0 0 8px;
}

/* ── Novelty Badge ── */
.novelty-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px;
  border-radius: var(--radius-md);
  border: 1px solid;
}

.novelty-badge--novel {
  background: color-mix(in srgb, var(--success) 10%, transparent);
  border-color: var(--success);
  color: var(--success);
}

.novelty-badge--not-novel {
  background: color-mix(in srgb, var(--error) 10%, transparent);
  border-color: var(--error);
  color: var(--error);
}

.novelty-badge--unknown {
  background: var(--bg-tertiary);
  border-color: var(--border-primary);
  color: var(--text-tertiary);
}

.novelty-badge__label {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* ── Research Gaps ── */
.validation-section {
  display: flex;
  flex-direction: column;
}

.gap-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.gap-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
}

.gap-item__icon {
  font-size: 16px;
  color: var(--warning);
  flex-shrink: 0;
  margin-top: 1px;
}

.gap-item__text {
  font-size: 12px;
  color: var(--text-primary);
  line-height: 1.5;
  flex: 1;
}

.gap-item__score {
  font-size: 11px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

/* ── SOTA Table ── */
.sota-table-wrap {
  overflow-x: auto;
}

.sota-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.sota-table th {
  text-align: left;
  padding: 6px 10px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-tertiary);
  border-bottom: 1px solid var(--border-primary);
}

.sota-table td {
  padding: 7px 10px;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border-secondary);
}

.sota-table tr:last-child td {
  border-bottom: none;
}

.sota-table tr:hover td {
  background: var(--bg-hover);
}

.validation-section__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.validation-detail__empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 20px;
  color: var(--text-tertiary);
  font-size: 13px;
  justify-content: center;
}

/* ── Approve Section ── */
.validation-approve {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: var(--os-brand-light);
  border: 1px solid var(--os-brand-subtle);
  border-radius: var(--radius-md);
  align-items: flex-start;
}

.validation-approve__info {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.validation-approve__info strong {
  font-size: 13px;
  color: var(--text-primary);
  display: block;
}

.validation-approve__desc {
  font-size: 12px;
  color: var(--text-secondary);
  display: block;
  margin-top: 2px;
}

.validation-approve__error {
  font-size: 12px;
  color: var(--error);
}

/* ── Specialist Review ── */
.specialist-review__loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
  color: var(--text-secondary);
  font-size: 13px;
}

.specialist-review__spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border-primary);
  border-top-color: var(--text-primary);
  border-radius: 50%;
  animation: sr-spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes sr-spin {
  to { transform: rotate(360deg); }
}

.specialist-review__loading-text {
  color: var(--text-secondary);
}

.specialist-review__error {
  font-size: 12px;
  color: var(--error);
  padding: 8px 0;
}

.specialist-review__results {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.specialist-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-md);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.specialist-card__header {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.specialist-card__badge {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 3px 8px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--info) 15%, transparent);
  color: var(--info);
}

.specialist-card__name {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.specialist-card__score {
  margin-left: auto;
  font-size: 14px;
  font-weight: 700;
}

.specialist-card__summary {
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-primary);
  margin: 0;
}

.findings-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.finding-item {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 6px;
  padding: 8px 10px;
  background: var(--bg-primary);
  border-radius: var(--radius-sm);
  font-size: 12px;
  line-height: 1.5;
}

.finding-item__severity {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 2px 6px;
  border-radius: 3px;
  flex-shrink: 0;
  line-height: 1.4;
}

.finding-item__category {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.finding-item__desc {
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
}

.finding-item__rec {
  width: 100%;
  font-size: 11px;
  color: var(--text-secondary);
  padding-left: 2px;
  display: flex;
  align-items: flex-start;
  gap: 4px;
}
</style>

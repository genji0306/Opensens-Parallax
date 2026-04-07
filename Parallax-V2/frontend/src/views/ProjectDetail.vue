<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePipelineStore } from '@/stores/pipeline'
import { useNextStep } from '@/composables/useNextStep'
import type { StageId } from '@/types/pipeline'
import {
  ACTIVE_PROJECT_STATUSES,
  STAGE_ORDER,
  STAGE_LABELS,
  STAGE_SHORT_LABELS,
  STAGE_DESCRIPTIONS,
  STAGE_ICONS,
  STATUS_DISPLAY,
} from '@/types/pipeline'
import PipelineTracker from '@/components/pipeline/PipelineTracker.vue'
import StageCard from '@/components/pipeline/StageCard.vue'
import GlassPanel from '@/components/shared/GlassPanel.vue'
import ActionButton from '@/components/shared/ActionButton.vue'
import StatusBadge from '@/components/shared/StatusBadge.vue'
import { getWorkflowGraph, restartFromNode, autoAdvance, executeNode, getRunCost } from '@/api/ais'
import type { RunCost } from '@/api/ais'
import type { WorkflowNode } from '@/api/ais'
import CrawlDetail from '@/components/stages/CrawlDetail.vue'
import MapDetail from '@/components/stages/MapDetail.vue'
import DebateDetail from '@/components/stages/DebateDetail.vue'
import ValidationDetail from '@/components/stages/ValidationDetail.vue'
import IdeasDetail from '@/components/stages/IdeasDetail.vue'
import DraftDetail from '@/components/stages/DraftDetail.vue'
import ExperimentDetail from '@/components/stages/ExperimentDetail.vue'
import RehabDetail from '@/components/stages/RehabDetail.vue'
import PassDetail from '@/components/stages/PassDetail.vue'

// P-2: Knowledge Engine
import ClaimGraphView from '@/components/knowledge/ClaimGraphView.vue'
import NoveltyMap from '@/components/knowledge/NoveltyMap.vue'
import QuestionTree from '@/components/knowledge/QuestionTree.vue'
import HypothesisCard from '@/components/knowledge/HypothesisCard.vue'

// P-3: Review Board
import ReviewerBoardConfig from '@/components/review/ReviewerBoardConfig.vue'
import ReviewConflictPanel from '@/components/review/ReviewConflictPanel.vue'
import RevisionPlanView from '@/components/review/RevisionPlanView.vue'

// P-5: Translation
import GrantPreview from '@/components/knowledge/GrantPreview.vue'

// P-6: Handoff
import ReadinessPanel from '@/components/handoff/ReadinessPanel.vue'

import { buildKnowledgeArtifact, getKnowledgeArtifact, exportKnowledge, getProjectArtifactDownloadUrl } from '@/api/ais'
import type { KnowledgeArtifact as KAType } from '@/api/ais'

const route = useRoute()
const router = useRouter()
const pipeline = usePipelineStore()
const { recommendation } = useNextStep()

const runId = computed(() => route.params.runId as string)
const expandedStage = ref<StageId | null>(null)
const isAisRun = computed(() => {
  if (pipeline.projectType === 'ais') return true
  if (pipeline.projectType !== 'unknown') return false
  return runId.value.startsWith('ais_run_')
})

// V2: Workflow graph data for model selector, settings, restart
const graphNodes = ref<WorkflowNode[]>([])
const costBreakdown = ref<RunCost | null>(null)
const showCostBreakdown = ref(false)

// Intelligence tabs (P-2/P-3/P-6)
type IntelTab = 'knowledge' | 'review' | 'translation' | 'readiness'
const activeIntelTab = ref<IntelTab | null>(null)
const knowledgeArtifact = ref<KAType | null>(null)
const knowledgeLoading = ref(false)

async function fetchKnowledgeArtifact() {
  if (!runId.value || !isAisRun.value) {
    knowledgeArtifact.value = null
    return
  }
  try {
    const res = await getKnowledgeArtifact(runId.value)
    knowledgeArtifact.value = res.data?.data ?? null
  } catch {
    knowledgeArtifact.value = null
  }
}

async function handleBuildArtifact() {
  if (!runId.value || !isAisRun.value) return
  knowledgeLoading.value = true
  try {
    const res = await buildKnowledgeArtifact(runId.value)
    knowledgeArtifact.value = res.data?.data ?? null
  } catch (err) {
    console.error('Build artifact failed:', err)
  } finally {
    knowledgeLoading.value = false
  }
}

// Translation state
const translationResult = ref<Record<string, unknown> | null>(null)
const translationLoading = ref(false)
const translationMode = ref('grant')

async function handleTranslate() {
  if (!runId.value || !isAisRun.value) return
  translationLoading.value = true
  try {
    const { default: service } = await import('@/api/client')
    const res = await service.post(`/api/research/ais/${runId.value}/translate`, { mode: translationMode.value }, { timeout: 120000 })
    translationResult.value = res.data?.data ?? null
  } catch (err) {
    console.error('Translation failed:', err)
  } finally {
    translationLoading.value = false
  }
}

function getPersistedTranslationForMode(mode: string): Record<string, unknown> | null {
  const outputs = pipeline.stageResults.translation_outputs
  if (isRecord(outputs) && isRecord(outputs[mode])) {
    return outputs[mode] as Record<string, unknown>
  }

  const directStageKeys: Record<string, string> = {
    grant: 'grant_translation',
    journal: 'journal_translation',
    funding: 'funding_translation',
    patent: 'patent_analysis',
    commercial: 'commercial_analysis',
  }
  const directKey = directStageKeys[mode]
  if (directKey && isRecord(pipeline.stageResults[directKey])) {
    return pipeline.stageResults[directKey] as Record<string, unknown>
  }

  const latest = pipeline.stageResults.translation_latest
  if (isRecord(latest) && latest.mode === mode && isRecord(latest.result)) {
    return latest.result as Record<string, unknown>
  }

  return null
}

function getLatestPersistedTranslation(): { mode: string; result: Record<string, unknown> } | null {
  const latest = pipeline.stageResults.translation_latest
  if (isRecord(latest) && typeof latest.mode === 'string' && isRecord(latest.result)) {
    return {
      mode: latest.mode,
      result: latest.result as Record<string, unknown>,
    }
  }

  const fallbackModes = ['grant', 'journal', 'funding', 'patent', 'commercial']
  for (const mode of fallbackModes) {
    const result = getPersistedTranslationForMode(mode)
    if (result) return { mode, result }
  }
  return null
}

async function handleExportKnowledge() {
  if (!runId.value || !isAisRun.value) return
  try {
    const res = await exportKnowledge(runId.value)
    const data = res.data?.data
    if (data) {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `knowledge-${runId.value}.json`
      a.style.display = 'none'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    }
  } catch (err) {
    console.error('Export failed:', err)
  }
}

function handleExportProjectArtifact(format: 'html' | 'pdf') {
  if (!runId.value || !isAisRun.value) return
  try {
    const url = getProjectArtifactDownloadUrl(runId.value, format)
    const a = document.createElement('a')
    a.href = url
    a.style.display = 'none'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  } catch (err) {
    console.error('Project artifact export failed:', err)
  }
}

async function fetchGraphNodes() {
  if (!runId.value || !isAisRun.value) {
    graphNodes.value = []
    return
  }
  try {
    const res = await getWorkflowGraph(runId.value)
    graphNodes.value = res.data?.data?.nodes ?? []
  } catch {
    // Graph may not exist for very old runs — degrade gracefully
    graphNodes.value = []
  }
}

function getNodeForStage(stageId: StageId): WorkflowNode | undefined {
  const typeMap: Record<StageId, string> = {
    crawl: 'search', map: 'map', ideas: 'ideate', debate: 'debate',
    validate: 'validate', draft: 'draft', experiment: 'experiment_design', rehab: 'revise', pass: 'pass',
  }
  return graphNodes.value.find(n => n.node_type === typeMap[stageId])
}

function getConfiguredModel(stageId: StageId): string {
  const node = getNodeForStage(stageId)
  if (!node) return ''
  const configured = typeof node.model_config?.model === 'string'
    ? node.model_config.model
    : ''
  return configured || node.model_used || ''
}

function getStageMetrics(metric?: string) {
  return metric ? [{ label: 'Metric', value: metric }] : []
}

async function handleNodeRestart(nodeId: string) {
  if (!runId.value || !nodeId) return
  try {
    await restartFromNode(runId.value, nodeId)
    await pipeline.refreshStages()
    await fetchGraphNodes()
  } catch (err) {
    console.error('Restart failed:', err)
  }
}

const advancing = ref(false)

async function handleAutoAdvance() {
  if (!runId.value || advancing.value) return
  advancing.value = true
  try {
    await autoAdvance(runId.value)
    // Start polling to track progress
    await pipeline.refreshStages()
    await fetchGraphNodes()
  } catch (err) {
    console.error('Auto-advance failed:', err)
  } finally {
    advancing.value = false
  }
}

async function handleExecuteNode(stageId: StageId) {
  const node = getNodeForStage(stageId)
  if (!runId.value || !node) return
  try {
    await executeNode(runId.value, node.node_id)
    await pipeline.refreshStages()
    await fetchGraphNodes()
  } catch (err) {
    console.error('Execute node failed:', err)
  }
}

function handleNodeModelChange(stageId: StageId, model: string) {
  const node = getNodeForStage(stageId)
  if (!node) return
  graphNodes.value = graphNodes.value.map((entry) =>
    entry.node_id === node.node_id
      ? {
          ...entry,
          model_config: {
            ...entry.model_config,
            model,
          },
        }
      : entry
  )
}

// ── Computed ────────────────────────────────────────────────────────────

function mapNodeStatusToStageStatus(
  status?: WorkflowNode['status'],
): 'done' | 'active' | 'pending' | 'failed' | 'skipped' | 'invalidated' | null {
  switch (status) {
    case 'completed': return 'done'
    case 'running': return 'active'
    case 'failed': return 'failed'
    case 'skipped': return 'skipped'
    case 'invalidated': return 'invalidated'
    case 'pending': return 'pending'
    default: return null
  }
}

function getStageStatus(stageId: StageId) {
  const graphStatus = mapNodeStatusToStageStatus(getNodeForStage(stageId)?.status)
  return graphStatus ?? pipeline.stages[stageId]?.status ?? 'pending'
}

const stagesArray = computed(() =>
  STAGE_ORDER.map((id) => ({
    id,
    label: STAGE_LABELS[id],
    shortLabel: STAGE_SHORT_LABELS[id],
    description: STAGE_DESCRIPTIONS[id],
    icon: STAGE_ICONS[id],
    status: getStageStatus(id),
    metric: pipeline.stages[id]?.metric,
  }))
)

const completedStageCount = computed(() =>
  stagesArray.value.filter((stage) => stage.status === 'done').length,
)

const progressPercent = computed(() => {
  if (pipeline.taskProgress > 0 && ['crawling', 'mapping'].includes(pipeline.projectStatus)) {
    return pipeline.taskProgress
  }
  if (STAGE_ORDER.length === 0) return 0
  return Math.round((completedStageCount.value / STAGE_ORDER.length) * 100)
})

const projectTitle = computed(() => {
  // Use store's extracted title (from query/topic/title field)
  if (pipeline.projectTitle) return pipeline.projectTitle
  return runId.value
})

const syncBadge = computed(() => {
  if (pipeline.error) {
    return { status: 'failed' as const, label: 'Offline' }
  }
  if (pipeline.projectSource === 'platform' && ACTIVE_PROJECT_STATUSES.has(pipeline.projectStatus)) {
    return { status: 'active' as const, label: 'Polling' }
  }
  if (pipeline.projectSource === 'platform') {
    return { status: 'done' as const, label: 'Snapshot' }
  }
  return { status: 'pending' as const, label: 'Static' }
})

const stageDetailComponents: Record<StageId, unknown> = {
  crawl: CrawlDetail,
  map: MapDetail,
  debate: DebateDetail,
  validate: ValidationDetail,
  ideas: IdeasDetail,
  draft: DraftDetail,
  experiment: ExperimentDetail,
  rehab: RehabDetail,
  pass: PassDetail,
}

const projectBadgeStatus = computed(() => {
  if (pipeline.projectStatus === 'completed') return 'done' as const
  if (pipeline.projectStatus === 'failed') return 'failed' as const
  if (ACTIVE_PROJECT_STATUSES.has(pipeline.projectStatus)) return 'active' as const
  return 'pending' as const
})

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function estimateTranscriptWords(transcript: unknown): number {
  if (!Array.isArray(transcript)) return 0
  return transcript.reduce((total, entry) => {
    if (!isRecord(entry) || typeof entry.content !== 'string') return total
    const words = entry.content.trim().split(/\s+/).filter(Boolean).length
    return total + words
  }, 0)
}

function normalizeStageResult(stageId: StageId): Record<string, unknown> {
  let raw = pipeline.stageResults[stageId]
  const graphOutputs = getNodeForStage(stageId)?.outputs

  // Bug #12: 'map' data lives under 'crawl' (stage_1 maps to 'crawl' in store).
  // Also check the raw 'stage_1' key as a fallback.
  if (stageId === 'map' && (raw == null || (isRecord(raw) && Object.keys(raw).length === 0))) {
    raw = pipeline.stageResults['crawl'] ?? pipeline.stageResults['stage_1'] ?? raw
  }

  if (stageId === 'ideas' && Array.isArray(raw)) {
    return {
      ideas: raw,
      selected_idea_id: pipeline.stageResults['selected_idea_id'],
    }
  }

  if (stageId === 'draft' && Array.isArray(raw)) {
    return { future_discussion: raw }
  }

  if (stageId === 'experiment' && typeof raw === 'string') {
    return {
      status: raw,
      template: 'AI Scientist',
    }
  }

  if (stageId === 'draft' && typeof raw === 'string') {
    return {
      export_path: raw,
    }
  }

  const normalized = {
    ...(isRecord(graphOutputs) ? graphOutputs : {}),
    ...(isRecord(raw) ? raw : {}),
  }

  if (stageId === 'ideas') {
    return {
      ...normalized,
      selected_idea_id: normalized.selected_idea_id ?? pipeline.stageResults['selected_idea_id'],
    }
  }

  if (stageId === 'debate') {
    return {
      ...normalized,
      agent_count: normalized.agent_count ?? (Array.isArray(normalized.agents) ? normalized.agents.length : 0),
      round_count: normalized.round_count ?? normalized.rounds ?? normalized.rounds_completed ?? 0,
      total_words: normalized.total_words ?? estimateTranscriptWords(normalized.transcript),
    }
  }

  if (stageId === 'crawl') {
    const config = pipeline.projectConfig
    const configuredSources = Array.isArray(config.sources)
      ? config.sources.map((source) => String(source))
      : []

    return {
      ...normalized,
      config,
      total_papers: normalized.total_papers ?? normalized.papers_found ?? config.max_papers ?? 0,
      task_progress: normalized.task_progress ?? pipeline.taskProgress,
      task_message: normalized.task_message ?? pipeline.taskMessage,
      configured_sources: normalized.configured_sources ?? configuredSources,
    }
  }

  if (stageId === 'rehab') {
    return {
      ...normalized,
      review_scores: normalized.review_scores ?? normalized.score_progression,
    }
  }

  return normalized
}

// ── Lifecycle ───────────────────────────────────────────────────────────

function syncExpandedStage() {
  const stageParam = route.query.stage as string | undefined
  expandedStage.value = stageParam && STAGE_ORDER.includes(stageParam as StageId)
    ? stageParam as StageId
    : null
}

async function loadProjectView(targetRunId: string) {
  if (!targetRunId) return
  graphNodes.value = []
  costBreakdown.value = null
  knowledgeArtifact.value = null
  pipeline.clearProject()
  await pipeline.loadProject(targetRunId)

  if (isAisRun.value) {
    await fetchGraphNodes()
    // Fetch cost breakdown + knowledge artifact (non-blocking)
    getRunCost(targetRunId).then(res => {
      const data = res.data?.data
      if (data) costBreakdown.value = data as unknown as RunCost
    }).catch(() => { /* best effort */ })
    fetchKnowledgeArtifact()
  }
}

watch(runId, (nextRunId) => {
  loadProjectView(nextRunId)
}, { immediate: true })

watch(() => route.query.stage, () => {
  syncExpandedStage()
}, { immediate: true })

watch(() => pipeline.stageResults, () => {
  const currentModeResult = getPersistedTranslationForMode(translationMode.value)
  if (currentModeResult) {
    translationResult.value = currentModeResult
    return
  }

  const latest = getLatestPersistedTranslation()
  if (latest) {
    translationMode.value = latest.mode
    translationResult.value = latest.result
    return
  }

  translationResult.value = null
}, { immediate: true, deep: true })

watch(translationMode, (mode) => {
  translationResult.value = getPersistedTranslationForMode(mode)
})

onUnmounted(() => {
  pipeline.stopPolling()
})

// ── Actions ─────────────────────────────────────────────────────────────

function goBack() {
  router.push({ name: 'command-center' })
}

function toggleStage(stageId: StageId) {
  expandedStage.value = expandedStage.value === stageId ? null : stageId
}

function handleStageClick(stageId: StageId) {
  toggleStage(stageId)
}

function handleNextAction(handler: string) {
  switch (handler) {
    case 'viewResults':
      expandedStage.value = 'draft'
      break
    case 'newProject':
      router.push({ name: 'command-center' })
      break
    case 'startRehab':
      router.push({ name: 'paper-lab', query: { run_id: runId.value } })
      break
    case 'viewDraft':
      expandedStage.value = 'draft'
      break
    case 'autoAdvance':
      handleAutoAdvance()
      break
    default:
      // For start_<stage> and retry_<stage> handlers
      if (handler.startsWith('start_') || handler.startsWith('retry_')) {
        const stageId = handler.replace(/^(start_|retry_)/, '') as StageId
        expandedStage.value = stageId
      } else if (handler.startsWith('execute_')) {
        const stageId = handler.replace('execute_', '') as StageId
        handleExecuteNode(stageId)
      }
      break
  }
}
</script>

<template>
  <div class="project-detail">
    <!-- ── Top Bar ── -->
    <div class="project-detail__topbar">
      <button class="back-btn" @click="goBack">
        <span class="material-symbols-outlined">arrow_back</span>
        <span>Command Center</span>
      </button>
      <div class="topbar-right">
        <ActionButton
          v-if="isAisRun"
          variant="secondary"
          size="sm"
          icon="description"
          @click="handleExportProjectArtifact('html')"
        >
          Full HTML
        </ActionButton>
        <ActionButton
          v-if="isAisRun"
          variant="secondary"
          size="sm"
          icon="picture_as_pdf"
          @click="handleExportProjectArtifact('pdf')"
        >
          Full PDF
        </ActionButton>
        <StatusBadge
          :status="syncBadge.status"
          :label="syncBadge.label"
          size="sm"
        />
        <span v-if="pipeline.costEstimate" class="cost-label font-mono">
          ${{ pipeline.costEstimate.total.toFixed(2) }}
        </span>
      </div>
    </div>

    <!-- ── Loading State ── -->
    <div v-if="pipeline.loading" class="loading-container">
      <span class="material-symbols-outlined spin">progress_activity</span>
      <span>Loading project...</span>
    </div>

    <!-- ── Error State ── -->
    <div v-else-if="pipeline.error" class="error-container">
      <span class="material-symbols-outlined" style="color: var(--error)">error</span>
      <span>{{ pipeline.error }}</span>
      <ActionButton variant="secondary" size="sm" @click="loadProjectView(runId)">
        Retry
      </ActionButton>
    </div>

    <!-- ── Main Content ── -->
    <template v-else>
      <!-- ══ MONITORING ZONE ══ -->
      <GlassPanel elevated padding="20px 24px" class="monitor-panel">
        <div class="monitor-panel__header">
          <div class="monitor-panel__title-row">
            <h1 class="project-title">{{ projectTitle }}</h1>
            <StatusBadge
              :status="projectBadgeStatus"
              :label="STATUS_DISPLAY[pipeline.projectStatus] ?? pipeline.projectStatus"
            />
          </div>
          <div class="monitor-panel__metrics">
            <div class="monitor-metric">
              <span class="monitor-metric__value font-mono">{{ completedStageCount }}<span class="monitor-metric__total">/{{ STAGE_ORDER.length }}</span></span>
              <span class="monitor-metric__label">Stages</span>
            </div>
            <div class="monitor-metric">
              <span class="monitor-metric__value font-mono">{{ progressPercent }}%</span>
              <span class="monitor-metric__label">Progress</span>
            </div>
            <div v-if="pipeline.costEstimate" class="monitor-metric monitor-metric--clickable" @click="showCostBreakdown = !showCostBreakdown">
              <span class="monitor-metric__value font-mono">${{ pipeline.costEstimate.total.toFixed(2) }}</span>
              <span class="monitor-metric__label">Cost <span class="material-symbols-outlined" style="font-size:12px;vertical-align:middle">{{ showCostBreakdown ? 'expand_less' : 'expand_more' }}</span></span>
            </div>
          </div>
        </div>

        <!-- Cost Breakdown (toggleable) -->
        <div v-if="showCostBreakdown && costBreakdown && Object.keys(costBreakdown.by_node).length > 0" class="cost-breakdown">
          <div class="cost-breakdown__header">
            <span class="detail-heading">Cost by Stage</span>
            <span class="cost-breakdown__tokens font-mono">{{ costBreakdown.total_input_tokens.toLocaleString() }} in / {{ costBreakdown.total_output_tokens.toLocaleString() }} out tokens</span>
          </div>
          <div class="cost-breakdown__rows">
            <div v-for="(info, nodeType) in costBreakdown.by_node" :key="nodeType" class="cost-breakdown__row">
              <span class="cost-breakdown__label">{{ nodeType.replace('_', ' ') }}</span>
              <span class="cost-breakdown__calls font-mono">{{ info.calls }} call{{ info.calls !== 1 ? 's' : '' }}</span>
              <span class="cost-breakdown__cost font-mono">${{ info.cost_usd.toFixed(4) }}</span>
            </div>
          </div>
        </div>

        <!-- Live task progress (AIS runs) -->
        <div v-if="pipeline.taskMessage" class="task-progress">
          <span class="material-symbols-outlined spin" style="font-size: 16px; color: var(--os-brand)">progress_activity</span>
          <span class="task-progress__msg">{{ pipeline.taskMessage }}</span>
          <div v-if="pipeline.taskProgress > 0" class="task-progress__bar">
            <div class="task-progress__fill" :style="{ width: pipeline.taskProgress + '%' }" />
          </div>
          <span class="task-progress__pct font-mono">{{ pipeline.taskProgress }}%</span>
        </div>

        <!-- Pipeline error banner -->
        <div v-if="pipeline.projectError" class="pipeline-error">
          <span class="material-symbols-outlined" style="font-size: 18px; color: var(--error)">error</span>
          <div class="pipeline-error__body">
            <span class="pipeline-error__label">Pipeline Failed</span>
            <span class="pipeline-error__msg">{{ pipeline.projectError }}</span>
          </div>
          <ActionButton variant="secondary" size="sm" icon="refresh" @click="loadProjectView(runId)">
            Retry
          </ActionButton>
        </div>

        <!-- Overall progress bar -->
        <div class="overall-progress">
          <div class="overall-progress__bar">
            <div
              class="overall-progress__fill"
              :style="{ width: progressPercent + '%' }"
              :class="{ 'overall-progress__fill--complete': progressPercent >= 100 }"
            />
          </div>
          <span class="overall-progress__text font-mono">
            {{ completedStageCount }} of {{ STAGE_ORDER.length }} stages complete
          </span>
        </div>

        <PipelineTracker
          :stages="stagesArray"
          :active-stage="pipeline.activeStage?.id"
          @stage-click="handleStageClick"
        />
      </GlassPanel>

      <!-- ══ STAGE DETAILS ZONE ══ -->
      <div class="stages-section-header">
        <h2 class="stages-section-title">Pipeline Stages</h2>
        <div class="stages-section-actions">
          <span class="stages-section-hint">Click a stage to inspect details</span>
          <ActionButton
            v-if="pipeline.projectSource === 'platform' && progressPercent < 100 && !pipeline.projectError"
            variant="primary"
            size="sm"
            icon="fast_forward"
            :loading="advancing"
            @click="handleAutoAdvance"
          >
            Auto-Advance
          </ActionButton>
        </div>
      </div>
      <div class="stages-grid">
        <StageCard
          v-for="stage in stagesArray"
          :key="stage.id"
          class="project-stage-card"
          :stage-id="stage.id"
          :title="stage.label"
          :status="stage.status"
          :icon="stage.icon"
          :metrics="getStageMetrics(stage.metric)"
          :expanded="expandedStage === stage.id"
          :node-id="getNodeForStage(stage.id)?.node_id"
          :run-id="runId"
          :model-used="getConfiguredModel(stage.id)"
          :node-config="getNodeForStage(stage.id)?.config"
          @toggle-expand="toggleStage(stage.id)"
          @restart="handleNodeRestart"
          @model-changed="handleNodeModelChange(stage.id, $event)"
        >
          <component
            :is="stageDetailComponents[stage.id]"
            :result="normalizeStageResult(stage.id)"
            :run-id="isAisRun ? runId : undefined"
            :simulation-id="
              pipeline.stageResults['debate']
                ? (pipeline.stageResults['debate'] as Record<string, unknown>).simulation_id as string | undefined
                : undefined
            "
          />
        </StageCard>
      </div>

      <!-- ── Next Step Banner ── -->
      <GlassPanel
        v-if="recommendation"
        elevated
        padding="16px 20px"
        class="next-step-banner"
        :class="{ 'next-step-banner--urgent': recommendation.urgent }"
      >
        <div class="next-step-banner__content">
          <span class="material-symbols-outlined next-step-banner__icon">
            {{ recommendation.urgent ? 'priority_high' : 'arrow_forward' }}
          </span>
          <div class="next-step-banner__text">
            <strong>{{ recommendation.label }}</strong>
            <span v-if="recommendation.description">{{ recommendation.description }}</span>
          </div>
        </div>
        <div class="next-step-banner__actions">
          <ActionButton
            v-for="action in recommendation.actions"
            :key="action.label"
            :variant="action.primary ? 'primary' : 'secondary'"
            size="sm"
            @click="action.handler && handleNextAction(action.handler)"
          >
            {{ action.label }}
          </ActionButton>
        </div>
      </GlassPanel>

      <!-- ══ INTELLIGENCE ZONE ══ -->
      <GlassPanel v-if="isAisRun" elevated padding="16px 20px" class="intel-panel">
        <div class="intel-panel__tabs">
          <button
            v-for="tab in ([
              { key: 'knowledge', label: 'Knowledge', icon: 'psychology' },
              { key: 'review', label: 'Review Board', icon: 'rate_review' },
              { key: 'translation', label: 'Translation', icon: 'translate' },
              { key: 'readiness', label: 'Readiness', icon: 'rocket_launch' },
            ] as const)"
            :key="tab.key"
            class="intel-tab"
            :class="{ 'intel-tab--active': activeIntelTab === tab.key }"
            @click="activeIntelTab = activeIntelTab === tab.key ? null : tab.key"
          >
            <span class="material-symbols-outlined" style="font-size: 16px">{{ tab.icon }}</span>
            {{ tab.label }}
          </button>
        </div>

        <!-- Knowledge Tab -->
        <div v-if="activeIntelTab === 'knowledge'" class="intel-panel__content">
          <div v-if="!knowledgeArtifact" class="intel-panel__empty">
            <p>Extract structured knowledge from pipeline outputs.</p>
            <ActionButton
              variant="primary"
              size="sm"
              icon="auto_awesome"
              :loading="knowledgeLoading"
              @click="handleBuildArtifact"
            >
              Build Knowledge Artifact
            </ActionButton>
          </div>
          <template v-else>
            <div class="intel-panel__summary">
              <span class="intel-stat">{{ knowledgeArtifact.claims.length }} claims</span>
              <span class="intel-stat">{{ knowledgeArtifact.evidence.length }} evidence</span>
              <span class="intel-stat">{{ knowledgeArtifact.gaps.length }} gaps</span>
            </div>

            <div class="intel-panel__sections">
              <ClaimGraphView :run-id="runId" />
              <NoveltyMap :run-id="runId" />
              <QuestionTree :run-id="runId" />
              <HypothesisCard :run-id="runId" />
            </div>
          </template>
        </div>

        <!-- Review Tab -->
        <div v-if="activeIntelTab === 'review'" class="intel-panel__content">
          <ReviewerBoardConfig :run-id="runId" @review-complete="fetchKnowledgeArtifact" />
          <ReviewConflictPanel :run-id="runId" />
          <RevisionPlanView :run-id="runId" />
        </div>

        <!-- Translation Tab -->
        <div v-if="activeIntelTab === 'translation'" class="intel-panel__content">
          <div class="translation-controls">
            <div class="translation-controls__row">
              <select v-model="translationMode" class="translation-controls__select">
                <option value="journal">Journal Paper</option>
                <option value="grant">Grant Concept Note</option>
                <option value="funding">Funding Brief</option>
                <option value="patent">Patent Assessment</option>
                <option value="commercial">Commercialization Brief</option>
              </select>
              <ActionButton
                variant="primary"
                size="sm"
                icon="translate"
                :loading="translationLoading"
                @click="handleTranslate"
              >
                Translate
              </ActionButton>
              <ActionButton
                v-if="knowledgeArtifact"
                variant="secondary"
                size="sm"
                icon="download"
                @click="handleExportKnowledge"
              >
                Export JSON
              </ActionButton>
            </div>
          </div>

          <GrantPreview v-if="translationResult" :data="translationResult" />
        </div>

        <!-- Readiness Tab -->
        <div v-if="activeIntelTab === 'readiness'" class="intel-panel__content">
          <ReadinessPanel :run-id="runId" />
        </div>
      </GlassPanel>
      <GlassPanel v-else elevated padding="14px 18px" class="intel-panel">
        <div class="intel-panel__empty">
          <p>
            This run is not an AIS pipeline run. Advanced knowledge/review/translation panels are available for AIS runs.
          </p>
        </div>
      </GlassPanel>
    </template>
  </div>
</template>

<style scoped>
.project-detail {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px 24px;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

/* ── Top Bar ── */
.project-detail__topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  cursor: pointer;
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  padding: 6px 10px;
  border-radius: var(--radius-md);
  transition: color var(--transition-fast), background var(--transition-fast);
}

.back-btn:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.back-btn .material-symbols-outlined {
  font-size: 18px;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.cost-label {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 3px 8px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
}

/* ── Monitor Panel ── */
.monitor-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.monitor-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.monitor-panel__title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 200px;
}

.project-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.02em;
}

.monitor-panel__metrics {
  display: flex;
  gap: 20px;
  flex-shrink: 0;
}

.monitor-metric {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.monitor-metric__value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.monitor-metric__total {
  font-size: 13px;
  font-weight: 400;
  color: var(--text-tertiary);
}

.monitor-metric__label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-tertiary);
}

.monitor-metric--clickable { cursor: pointer; border-radius: var(--radius-sm); }
.monitor-metric--clickable:hover { background: var(--bg-hover); }

/* ── Cost Breakdown ── */
.cost-breakdown {
  padding: 12px 14px; background: var(--bg-secondary);
  border: 1px solid var(--border-secondary); border-radius: var(--radius-md);
}
.cost-breakdown__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.cost-breakdown__tokens { font-size: 10px; color: var(--text-tertiary); }
.cost-breakdown__rows { display: flex; flex-direction: column; gap: 4px; }
.cost-breakdown__row {
  display: flex; align-items: center; gap: 8px; padding: 4px 6px;
  border-radius: var(--radius-sm); font-size: 12px;
}
.cost-breakdown__row:hover { background: var(--bg-hover); }
.cost-breakdown__label { flex: 1; text-transform: capitalize; color: var(--text-primary); }
.cost-breakdown__calls { font-size: 10px; color: var(--text-tertiary); }
.cost-breakdown__cost { font-weight: 600; color: var(--text-primary); min-width: 60px; text-align: right; }

.detail-heading {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--text-secondary); margin: 0;
}

/* ── Overall Progress ── */
.overall-progress {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.overall-progress__bar {
  height: 6px;
  background: var(--border-secondary);
  border-radius: 3px;
  overflow: hidden;
}

.overall-progress__fill {
  height: 100%;
  background: var(--os-brand);
  border-radius: 3px;
  transition: width 0.6s cubic-bezier(0.16, 1, 0.3, 1);
  min-width: 2px;
}

.overall-progress__fill--complete {
  background: var(--success);
}

.overall-progress__text {
  font-size: 11px;
  color: var(--text-tertiary);
}

/* ── Section Header ── */
.stages-section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.stages-section-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stages-section-title {
  font-size: 14px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-primary);
  margin: 0;
}

.stages-section-hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* ── Stages Grid ── */
.stages-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stage-card {
  overflow: hidden;
  transition: box-shadow var(--transition-normal), border-color var(--transition-normal), transform var(--transition-fast);
  border-left: 3px solid transparent;
}

.stage-card:hover {
  border-color: var(--border-primary);
  box-shadow: var(--shadow-sm);
}

.stage-card--done {
  border-left-color: var(--os-brand);
}

.stage-card--active {
  border-left-color: var(--os-brand);
  background: var(--bg-active);
  box-shadow: 0 0 0 1px var(--os-brand-subtle);
  animation: stage-pulse 2s ease-in-out infinite;
}

.stage-card--failed {
  border-left-color: var(--error);
  background: rgba(239, 68, 68, 0.03);
}

.stage-card--expanded {
  grid-column: 1 / -1;
  border-color: var(--os-brand);
  box-shadow: var(--shadow-md);
}

.stage-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  padding: 14px 16px;
  background: none;
  border: none;
  cursor: pointer;
  font-family: var(--font-sans);
  text-align: left;
  transition: background var(--transition-fast);
}

.stage-card__header:hover {
  background: var(--bg-hover);
}

.stage-card__header:active {
  background: var(--bg-tertiary);
}

.stage-card__left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stage-card__icon {
  font-size: 20px;
  color: var(--text-tertiary);
}

.stage-card__icon--done { color: var(--os-brand); }
.stage-card__icon--active { color: var(--os-brand); }
.stage-card__icon--failed { color: var(--error); }

.stage-card__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stage-card__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.stage-card__desc {
  font-size: 11px;
  color: var(--text-tertiary);
  line-height: 1.3;
  display: none;
}

/* Show description only when card is NOT expanded (avoids redundancy) */
.stage-card:not(.stage-card--expanded) .stage-card__desc {
  display: block;
}

.stage-card__metric {
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: 500;
}

.stage-card__right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stage-card__model-chip {
  font-size: 10px;
  font-family: var(--font-mono);
  padding: 2px 8px;
  border-radius: var(--radius-pill, 99px);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  white-space: nowrap;
}

.stage-card__restart-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-tertiary);
  padding: 2px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  transition: color 0.15s, background 0.15s;
}

.stage-card__restart-btn:hover {
  color: var(--warning, #f59e0b);
  background: rgba(245, 158, 11, 0.1);
}

.stage-card__chevron {
  font-size: 20px;
  color: var(--text-tertiary);
  transition: transform 0.2s ease;
}

.stage-card__chevron--open {
  transform: rotate(180deg);
}

.stage-card__body {
  padding: 0 16px 16px;
  border-top: 1px solid var(--border-secondary);
}

/* ── Next Step Banner ── */
.next-step-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.next-step-banner--urgent {
  border-color: var(--warning);
  background: color-mix(in srgb, var(--warning) 5%, var(--glass-bg));
}

.next-step-banner__content {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  flex: 1;
  min-width: 200px;
}

.next-step-banner__icon {
  font-size: 20px;
  color: var(--os-brand);
  flex-shrink: 0;
  margin-top: 1px;
}

.next-step-banner--urgent .next-step-banner__icon {
  color: var(--warning);
}

.next-step-banner__text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.next-step-banner__text strong {
  font-size: 14px;
  color: var(--text-primary);
}

.next-step-banner__text span {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.next-step-banner__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* ── Loading / Error ── */
.loading-container,
.error-container {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 60px 24px;
  color: var(--text-secondary);
  font-size: 14px;
}

.spin {
  animation: btn-spin 1s linear infinite;
}

.task-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--os-brand-light);
  border: 1px solid var(--os-brand-subtle);
  border-radius: var(--radius-md);
}

.task-progress__msg {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  flex-shrink: 0;
}

.task-progress__bar {
  flex: 1;
  height: 4px;
  background: var(--border-secondary);
  border-radius: 2px;
  overflow: hidden;
  min-width: 80px;
}

.task-progress__fill {
  height: 100%;
  background: var(--os-brand);
  border-radius: 2px;
  transition: width 0.5s ease;
}

.task-progress__pct {
  font-size: 12px;
  font-weight: 600;
  color: var(--os-brand);
  flex-shrink: 0;
}

.pipeline-error {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: var(--radius-lg);
}

.pipeline-error__body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pipeline-error__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--error);
}

.pipeline-error__msg {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
}

@keyframes btn-spin {
  to { transform: rotate(360deg); }
}

/* ── Expand Transition ── */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 800px;
}

/* ── Intelligence Panel ── */

.intel-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.intel-panel__tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--border-secondary);
  padding-bottom: 8px;
}

.intel-tab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background: none;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: color var(--transition-fast), background var(--transition-fast), border-color var(--transition-fast);
}

.intel-tab:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.intel-tab--active {
  color: var(--os-brand);
  background: color-mix(in srgb, var(--os-brand) 8%, transparent);
  border-color: var(--os-brand);
}

.intel-panel__content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.intel-panel__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 24px;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
}

.intel-panel__summary {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-secondary);
}

.intel-stat {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  background: var(--bg-secondary);
  border-radius: var(--radius-pill, 999px);
}

.intel-panel__sections {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Translation Controls ── */

.translation-controls {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.translation-controls__row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.translation-controls__select {
  padding: 6px 10px;
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  min-width: 180px;
}

.translation-controls__select:focus {
  border-color: var(--os-brand);
  outline: none;
}
</style>

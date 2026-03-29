import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type {
  StageId,
  StageInfo,
  StageResult,
  NextStepRecommendation,
  CostEstimate,
} from '@/types/pipeline'
import {
  ACTIVE_PROJECT_STATUSES,
  STAGE_ORDER as stageOrder,
  STAGE_LABELS,
  STAGE_SHORT_LABELS,
  STAGE_DESCRIPTIONS,
  STAGE_ICONS,
} from '@/types/pipeline'
import { getHistoryRunDetail, getPipelineStatus, getRunCost, getWorkflowGraph } from '@/api/ais'
import type { WorkflowNode } from '@/api/ais'

// ── Helpers ──

/** Map backend numeric AIS stage to StageId */
const NUMERIC_STAGE_MAP: Record<number, StageId> = {
  1: 'crawl', 2: 'ideas', 3: 'debate', 4: 'validate', 5: 'draft', 6: 'experiment', 7: 'rehab', 8: 'pass',
}

/** Map CLI data keys to StageId */
const DATA_KEY_MAP: Record<string, StageId> = {
  debate: 'debate',
  ideas: 'ideas',
  validation: 'validate',
  experiment: 'experiment',
  ai_scientist: 'experiment',
  draft_path: 'draft',
  future_discussion: 'draft',
  revise: 'rehab',
  pass: 'pass',
}

function resolveStageId(raw: unknown): StageId | null {
  if (typeof raw === 'string' && stageOrder.includes(raw as StageId)) return raw as StageId
  if (typeof raw === 'number') return NUMERIC_STAGE_MAP[raw] ?? null
  return null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

const STATUS_STAGE_MAP: Partial<Record<string, StageId>> = {
  crawling: 'crawl',
  mapping: 'map',
  ideating: 'ideas',
  debating: 'debate',
  human_review: 'validate',
  drafting: 'draft',
  reviewing: 'rehab',
  experimenting: 'experiment',
}

/** Map workflow graph node_type → StageId for graph-based reconstruction. */
const NODE_TYPE_TO_STAGE: Record<string, StageId> = {
  search: 'crawl',
  map: 'map',
  ideate: 'ideas',
  debate: 'debate',
  validate: 'validate',
  draft: 'draft',
  experiment_design: 'experiment',
  revise: 'rehab',
  pass: 'pass',
}

/** Map graph node status → stage display status. */
function graphStatusToStageStatus(
  nodeStatus: WorkflowNode['status'],
): StageInfo['status'] {
  switch (nodeStatus) {
    case 'completed': return 'done'
    case 'running': return 'active'
    case 'failed': return 'failed'
    case 'skipped': return 'skipped'
    case 'invalidated': return 'invalidated'
    case 'pending':
    default: return 'pending'
  }
}

export const usePipelineStore = defineStore('pipeline', () => {
  // ── State ──
  const activeRunId = ref<string | null>(null)
  const stages = ref<Record<StageId, StageInfo>>({} as Record<StageId, StageInfo>)
  const stageResults = ref<Record<string, StageResult>>({})
  const recommendation = ref<NextStepRecommendation | null>(null)
  const costEstimate = ref<CostEstimate | null>(null)
  const graphNodes = ref<WorkflowNode[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Project metadata
  const projectTitle = ref<string>('')
  const projectStatus = ref<string>('')
  const projectError = ref<string | null>(null)
  const projectSource = ref<string>('')
  const projectConfig = ref<Record<string, unknown>>({})

  // AIS live progress
  const taskMessage = ref<string>('')
  const taskProgress = ref<number>(0)

  // Polling handle for active AIS runs
  let pollHandle: ReturnType<typeof setInterval> | null = null
  let consecutivePollFailures = 0

  // ── Getters ──
  const activeStage = computed<StageInfo | null>(() =>
    Object.values(stages.value).find((s) => s.status === 'active') ?? null
  )
  const completedStageCount = computed(() =>
    Object.values(stages.value).filter((s) => s.status === 'done').length
  )
  const progressPercent = computed(() => {
    // For AIS runs with taskProgress, use that directly
    if (taskProgress.value > 0 && ['crawling', 'mapping'].includes(projectStatus.value)) {
      return taskProgress.value
    }
    const total = stageOrder.length
    if (total === 0) return 0
    return Math.round((completedStageCount.value / total) * 100)
  })

  // ── Build stages from run data ──
  function buildStagesFromRun(run: Record<string, unknown>): void {
    const builtStages = {} as Record<StageId, StageInfo>
    const rawStageResults = (run.stage_results ?? {}) as Record<string, unknown>
    const runData = (run.data ?? {}) as Record<string, unknown>
    const status = (run.status ?? '') as string
    const currentStageId = resolveStageId(run.current_stage)

    // Determine which stages have data — check both stage_results and data.*
    const completedStages = new Set<StageId>()

    // Map "stage_N" keys to StageId(s) — stage_1 covers both crawl and map
    const STAGE_NUM_TO_IDS: Record<string, StageId[]> = {
      stage_1: ['crawl', 'map'], stage_2: ['ideas'], stage_3: ['debate'],
      stage_4: ['validate'], stage_5: ['draft'], stage_6: ['experiment'],
      stage_7: ['rehab'], stage_8: ['pass'],
      // V2 workflow graph node types as keys
      specialist_review: ['validate'], experiment_design: ['experiment'],
      revise: ['rehab'], pass: ['pass'],
    }

    // From stage_results — handle both direct StageId keys and "stage_N" keys
    for (const [key, value] of Object.entries(rawStageResults)) {
      if (value == null || (isRecord(value) && Object.keys(value).length === 0)) continue

      // stage_2 (ideas): only mark done if ideas were actually generated
      if (key === 'stage_2' && isRecord(value)) {
        const count = (value.ideas_generated as number) ?? 0
        if (count === 0) continue
      }

      // Direct StageId key (e.g. "crawl", "ideas")
      if (stageOrder.includes(key as StageId)) {
        completedStages.add(key as StageId)
      }
      // Numeric "stage_N" key
      const mapped = STAGE_NUM_TO_IDS[key]
      if (mapped) {
        for (const sid of mapped) completedStages.add(sid)
      }
    }

    // From data.* keys (CLI runs)
    for (const [key, value] of Object.entries(runData)) {
      const stageId = DATA_KEY_MAP[key]
      if (stageId && value != null && value !== '' && (typeof value !== 'object' || Object.keys(value as object).length > 0)) {
        completedStages.add(stageId)
      }
    }

    // If it's a completed debate type, mark debate as done
    if (run.type === 'debate' && status === 'completed') {
      completedStages.add('debate')
      // If summary has agent_count, the debate ran
      const summary = run.summary as Record<string, unknown> | undefined
      if (summary?.agent_count) {
        completedStages.add('debate')
      }
    }

    // Resolve active stage — fall back to inferring from numeric current_stage
    let activeId: StageId | null = STATUS_STAGE_MAP[status] ?? currentStageId
    if (!activeId && run.current_stage != null) {
      const num = typeof run.current_stage === 'string' ? parseInt(run.current_stage, 10) : null
      if (num && NUMERIC_STAGE_MAP[num]) activeId = NUMERIC_STAGE_MAP[num]
    }

    // Build stage info
    for (const id of stageOrder) {
      let stageStatus: StageInfo['status'] = 'pending'

      if (completedStages.has(id)) {
        stageStatus = 'done'
      } else if (activeId === id && status !== 'failed' && status !== 'completed') {
        stageStatus = 'active'
      }

      builtStages[id] = {
        id,
        label: STAGE_LABELS[id],
        shortLabel: STAGE_SHORT_LABELS[id],
        description: STAGE_DESCRIPTIONS[id],
        icon: STAGE_ICONS[id],
        status: stageStatus,
        metric: getMetricForStage(id, run),
      }
    }

    // Mark failed stage
    if (status === 'failed') {
      const failedStage = currentStageId ?? stageOrder.find(id => builtStages[id].status === 'pending')
      if (failedStage && builtStages[failedStage]) {
        builtStages[failedStage].status = 'failed'
      }
    }

    // If completed, ensure all stages show done
    if (status === 'completed') {
      for (const id of stageOrder) {
        if (completedStages.has(id)) {
          builtStages[id].status = 'done'
        }
      }
    }

    stages.value = builtStages

    // Merge stage results from both sources
    const merged: Record<string, StageResult> = {}
    // Map "stage_N" keys to stage IDs
    const stageNumMap: Record<string, StageId> = {
      stage_1: 'crawl', stage_2: 'ideas', stage_3: 'debate',
      stage_4: 'validate', stage_5: 'draft', stage_6: 'experiment',
      stage_7: 'rehab', stage_8: 'pass',
      specialist_review: 'validate', experiment_design: 'experiment',
      revise: 'rehab', pass: 'pass',
    }
    for (const [key, value] of Object.entries(rawStageResults)) {
      if (value != null) {
        const mapped = stageNumMap[key]
        if (mapped) merged[mapped] = value as StageResult
        merged[key] = value as StageResult  // keep original key too
      }
    }
    // CLI data.* keys
    for (const [key, value] of Object.entries(runData)) {
      const stageId = DATA_KEY_MAP[key]
      if (stageId && value != null) {
        merged[stageId] = value as StageResult
      }
    }
    stageResults.value = merged
  }

  function getMetricForStage(id: StageId, run: Record<string, unknown>): string | undefined {
    const data = (run.data ?? {}) as Record<string, unknown>
    const summary = (run.summary ?? {}) as Record<string, unknown>
    const sr = (run.stage_results ?? {}) as Record<string, Record<string, unknown>>

    switch (id) {
      case 'crawl': {
        const config = run.config as Record<string, unknown> | undefined
        const s1 = sr['stage_1']
        if (s1?.papers_ingested) return `${s1.papers_ingested} papers`
        if (config?.sources) return `${(config.sources as string[]).join(', ')}`
        return undefined
      }
      case 'map': {
        const s1 = sr['stage_1']
        if (s1?.topics_found) return `${s1.topics_found} topics, ${s1.gaps_found ?? 0} gaps`
        return undefined
      }
      case 'debate': {
        const s3 = sr['stage_3']
        const debateData = data.debate as Record<string, unknown> | undefined
        const agentCount = summary.agent_count ?? debateData?.agent_count ?? s3?.agent_count
        const rounds = summary.rounds ?? debateData?.rounds ?? s3?.rounds_completed
        if (agentCount) return `${agentCount} agents, ${rounds ?? '?'} rounds`
        return undefined
      }
      case 'ideas': {
        const s2 = sr['stage_2']
        if (s2?.ideas_generated) return `${s2.ideas_generated} ideas`
        const ideas = data.ideas
        if (Array.isArray(ideas) && ideas.length > 0) return `${ideas.length} ideas`
        return undefined
      }
      case 'draft': {
        const s5 = sr['stage_5']
        if (s5?.total_word_count) return `${s5.total_word_count} words, ${s5.citation_count ?? 0} citations`
        if (s5?.section_count) return `${s5.section_count} sections`
        return undefined
      }
      case 'experiment': {
        const s6 = sr['stage_6']
        if (s6?.template) return `${s6.template}`
        const ed = sr['experiment_design']
        if (ed?.gap_count != null) return `${ed.gap_count} gaps, ${ed.experiment_count ?? 0} experiments`
        return undefined
      }
      case 'rehab': {
        const rev = sr['revise'] ?? sr['stage_7']
        if (isRecord(rev) && rev.last_score != null) return `Score: ${rev.last_score}, Rev ${rev.revision_count ?? 0}`
        return undefined
      }
      case 'pass': {
        const p = sr['pass'] ?? sr['stage_8']
        if (isRecord(p) && p.final_score != null) return `Score: ${p.final_score}`
        return p ? 'Done' : undefined
      }
      default:
        return undefined
    }
  }

  // ── Graph-based stage overlay ──
  /**
   * Fetch the V2 workflow graph and overlay node statuses onto stages.
   * This is the authoritative source for stage status when a graph exists.
   */
  async function fetchAndOverlayGraph(runId: string): Promise<void> {
    try {
      const res = await getWorkflowGraph(runId)
      const graph = res.data?.data
      if (!graph?.nodes?.length) return

      graphNodes.value = graph.nodes

      // Overlay graph node statuses onto built stages
      for (const node of graph.nodes) {
        const stageId = NODE_TYPE_TO_STAGE[node.node_type]
        if (!stageId || !stages.value[stageId]) continue

        const graphStatus = graphStatusToStageStatus(node.status)
        stages.value[stageId] = {
          ...stages.value[stageId],
          status: graphStatus,
        }
      }
    } catch {
      // Graph fetch is best-effort — fallback to run-centric status
    }
  }

  /** Get a graph node by stage ID. */
  function getGraphNodeForStage(stageId: StageId): WorkflowNode | undefined {
    const expectedType = Object.entries(NODE_TYPE_TO_STAGE)
      .find(([, sid]) => sid === stageId)?.[0]
    if (!expectedType) return undefined
    return graphNodes.value.find(n => n.node_type === expectedType)
  }

  // ── Actions ──
  async function loadProject(runId: string): Promise<void> {
    loading.value = true
    error.value = null
    activeRunId.value = runId
    stopPolling()
    taskMessage.value = ''
    taskProgress.value = 0

    try {
      const res = await getHistoryRunDetail(runId)
      const run = res.data?.data as unknown as Record<string, unknown> | undefined

      if (!run) {
        error.value = 'Project not found'
        return
      }

      // Extract metadata
      projectTitle.value = (run.title ?? run.query ?? run.topic ?? runId) as string
      projectStatus.value = (run.status ?? 'unknown') as string
      projectError.value = (run.error ?? null) as string | null
      projectSource.value = (run.source ?? 'platform') as string
      projectConfig.value = isRecord(run.config) ? run.config : {}
      taskMessage.value = (run.task_message ?? '') as string
      taskProgress.value = (run.task_progress ?? 0) as number

      buildStagesFromRun(run)

      // Overlay authoritative graph state (non-blocking — enhances run-based stages)
      fetchAndOverlayGraph(runId)

      // Fetch real cost data from backend (non-blocking)
      fetchCost(runId)

      // If it's an active AIS run, start polling for live progress
      if (run.source === 'platform' && ACTIVE_PROJECT_STATUSES.has(projectStatus.value)) {
        startPolling(runId)
      }

    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load project'
      if (msg.includes('Network Error') || msg.includes('timeout')) {
        error.value = 'Backend unreachable — start the Flask server on :5002'
      } else {
        error.value = msg
      }
    } finally {
      loading.value = false
    }
  }

  /** Poll AIS pipeline status for live progress updates */
  function startPolling(runId: string): void {
    if (pollHandle) return
    pollHandle = setInterval(async () => {
      try {
        const res = await getPipelineStatus(runId)
        const data = res.data?.data as unknown as Record<string, unknown> | undefined
        if (!data) return

        // Update live progress
        taskMessage.value = (data.task_message ?? '') as string
        taskProgress.value = (data.task_progress ?? 0) as number
        projectStatus.value = (data.status ?? projectStatus.value) as string
        projectError.value = (data.error ?? null) as string | null
        if (isRecord(data.config)) {
          projectConfig.value = data.config
        }

        // Rebuild stages whenever stage_results is present (even if empty —
        // other fields like current_stage and status still drive stage markers)
        if (data.stage_results) {
          buildStagesFromRun({
            ...data,
            config: data.config ?? projectConfig.value,
          })
        }

        // Update current stage marker
        const currentStageId = resolveStageId(data.current_stage)
        if (currentStageId) {
          for (const id of stageOrder) {
            if (stages.value[id]) {
              if (id === currentStageId && stages.value[id].status === 'pending') {
                stages.value[id] = { ...stages.value[id], status: 'active' }
              }
            }
          }
        }

        // Stop polling if terminal
        const terminalStatuses = ['completed', 'failed', 'awaiting_selection', 'waiting_for_selection']
        if (terminalStatuses.includes(projectStatus.value)) {
          if (projectStatus.value === 'failed') {
            const failedStage = currentStageId ?? stageOrder.find(id => stages.value[id]?.status === 'active')
            if (failedStage && stages.value[failedStage]) {
              stages.value[failedStage] = { ...stages.value[failedStage], status: 'failed' }
            }
          }
          stopPolling()
          // Reload full data
          loading.value = false
          try {
            const fullRes = await getHistoryRunDetail(runId)
            const fullRun = fullRes.data?.data as unknown as Record<string, unknown> | undefined
            if (fullRun) {
              projectConfig.value = isRecord(fullRun.config) ? fullRun.config : projectConfig.value
              buildStagesFromRun(fullRun)
            }
          } catch (reloadErr) {
            error.value = reloadErr instanceof Error
              ? `Final reload failed: ${reloadErr.message}`
              : 'Failed to reload project after completion'
          }
        }
        consecutivePollFailures = 0
      } catch {
        consecutivePollFailures++
        if (consecutivePollFailures >= 3) {
          error.value = `Polling failed ${consecutivePollFailures} times — backend may be unreachable`
        }
      }
    }, 3000)
  }

  function stopPolling(): void {
    if (pollHandle) {
      clearInterval(pollHandle)
      pollHandle = null
    }
    consecutivePollFailures = 0
  }

  async function refreshStages(): Promise<void> {
    if (!activeRunId.value) return
    await loadProject(activeRunId.value)
  }

  function setActiveStage(id: StageId): void {
    for (const key of Object.keys(stages.value) as StageId[]) {
      if (stages.value[key]) {
        stages.value[key] = {
          ...stages.value[key],
          status: key === id ? 'active' : stages.value[key].status === 'active' ? 'pending' : stages.value[key].status,
        }
      }
    }
  }

  async function fetchCost(runId: string): Promise<void> {
    try {
      const res = await getRunCost(runId)
      const data = res.data?.data as unknown as Record<string, unknown> | undefined
      if (data && typeof data.total_cost_usd === 'number') {
        costEstimate.value = {
          paid: data.total_cost_usd as number,
          free: 0,
          total: data.total_cost_usd as number,
          detail: `${data.total_input_tokens ?? 0} in / ${data.total_output_tokens ?? 0} out tokens`,
        }
      }
    } catch {
      // Cost fetch is best-effort — don't set error state
    }
  }

  function clearProject(): void {
    stopPolling()
    activeRunId.value = null
    stages.value = {} as Record<StageId, StageInfo>
    stageResults.value = {}
    recommendation.value = null
    costEstimate.value = null
    graphNodes.value = []
    loading.value = false
    error.value = null
    projectTitle.value = ''
    projectStatus.value = ''
    projectError.value = null
    projectSource.value = ''
    projectConfig.value = {}
    taskMessage.value = ''
    taskProgress.value = 0
  }

  return {
    activeRunId, stages, stageResults, recommendation, costEstimate, graphNodes,
    loading, error,
    projectTitle, projectStatus, projectError, projectSource, projectConfig,
    taskMessage, taskProgress,
    activeStage, completedStageCount, progressPercent,
    loadProject, refreshStages, setActiveStage, clearProject, stopPolling,
    fetchCost, fetchAndOverlayGraph, getGraphNodeForStage,
  }
})

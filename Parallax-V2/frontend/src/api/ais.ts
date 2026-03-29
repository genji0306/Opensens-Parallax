import service, { LONG_TIMEOUT, STATUS_TIMEOUT } from './client'
import type { AxiosResponse } from 'axios'
import type {
  ApiResponse,
  TaskStatus,
  ProviderInfo,
  ToolStatus,
  DebateSummary,
  ResearchIdea,
  PaperDraft,
  HistoryRun,
  SSEEvent,
} from '@/types/api'

// ── Agent AiS Pipeline ─────────────────────────────────────────────────

interface StartPipelineParams {
  research_idea: string
  sources?: string[]
  max_papers?: number
  num_ideas?: number
  num_reflections?: number
}

interface PipelineStatus extends TaskStatus {
  run_id: string
  current_stage?: string
  stage_results?: Record<string, unknown>
}

interface ExportDraftParams {
  format?: 'markdown' | 'latex' | 'json'
}

interface ListRunsParams {
  status?: string
  limit?: number
}

interface InjectThoughtParams {
  type?: string
  content: string
  paper_dois?: string[]
  rerun_debate?: boolean
}

interface TriggerReviewParams {
  num_reviewers?: number
}

interface SearchParams {
  query: string
  mode: 'survey' | 'novelty' | 'citations'
  max_papers?: number
}

interface ImportPaper {
  title: string
  doi?: string
  abstract?: string
  authors?: string[]
  year?: number
}

interface StartExperimentParams {
  template?: string
}

interface HistoryListParams {
  source?: 'platform' | 'cli'
  type?: string
  sort?: string
  page?: number
  per_page?: number
}

interface CostEstimateParams {
  action: string
}

/**
 * Start the full Agent AiS pipeline (Stages 1-2, then pauses for selection).
 */
export function startPipeline(
  data: StartPipelineParams,
): Promise<AxiosResponse<ApiResponse<{ run_id: string }>>> {
  return service.post('/api/research/ais/start', data, { timeout: LONG_TIMEOUT })
}

/**
 * Poll pipeline run status.
 */
export function getPipelineStatus(
  runId: string,
): Promise<AxiosResponse<ApiResponse<PipelineStatus>>> {
  return service.get(`/api/research/ais/${runId}/status`)
}

/**
 * Get Stage 2 ideas (ranked).
 */
export function getIdeas(
  runId: string,
): Promise<AxiosResponse<ApiResponse<ResearchIdea[]>>> {
  return service.get(`/api/research/ais/${runId}/ideas`)
}

/**
 * Human selects a winning idea for Stage 3.
 */
export function selectIdea(
  runId: string,
  ideaId: string,
): Promise<AxiosResponse<ApiResponse<{ status: string }>>> {
  return service.post(`/api/research/ais/${runId}/select-idea`, { idea_id: ideaId })
}

/**
 * Start Stage 3: agent-to-agent debate.
 */
export function startDebate(
  runId: string,
): Promise<AxiosResponse<ApiResponse<{ run_id: string; task_id: string; message: string }>>> {
  return service.post(`/api/research/ais/${runId}/debate`)
}

/**
 * Stage 4: approve debate results, proceed to drafting.
 */
export function approveDraft(
  runId: string,
  data: { feedback?: string } = {},
): Promise<AxiosResponse<ApiResponse<{ status: string }>>> {
  return service.post(`/api/research/ais/${runId}/approve`, data, { timeout: LONG_TIMEOUT })
}

/**
 * Get Stage 5 paper draft.
 */
export function getDraft(
  runId: string,
): Promise<AxiosResponse<ApiResponse<PaperDraft>>> {
  return service.get(`/api/research/ais/${runId}/draft`)
}

/**
 * Export draft as markdown, latex, or json.
 */
export function exportDraft(
  runId: string,
  format: ExportDraftParams['format'] = 'markdown',
): Promise<AxiosResponse<ApiResponse<string>>> {
  return service.get(`/api/research/ais/${runId}/export`, { params: { format } })
}

/**
 * List all pipeline runs.
 */
export function listRuns(
  params: ListRunsParams = {},
): Promise<AxiosResponse<ApiResponse<Array<{ run_id: string; status: string; topic: string }>>>> {
  return service.get('/api/research/ais/runs', { params })
}

/**
 * Poll pipeline status until it reaches a target status or fails.
 */
export async function pollPipeline(
  runId: string,
  targetStatuses: string[],
  onProgress?: (data: PipelineStatus) => void,
  interval = 3000,
): Promise<PipelineStatus> {
  const terminalStatuses = ['completed', 'failed', ...targetStatuses]
  while (true) {
    const res = await getPipelineStatus(runId)
    const data = res.data.data
    if (onProgress) onProgress(data)
    if (terminalStatuses.includes(data.status)) {
      return data
    }
    await new Promise((resolve) => setTimeout(resolve, interval))
  }
}

// ── Provider Info ──────────────────────────────────────────────────────

/**
 * Get LLM provider configuration, tier assignments, and cache stats.
 */
export function getProviderInfo(): Promise<AxiosResponse<ApiResponse<ProviderInfo>>> {
  return service.get('/api/research/ais/providers', { timeout: STATUS_TIMEOUT })
}

// ── Debate Summary ─────────────────────────────────────────────────────

/**
 * Get quick debate summary for a simulation.
 */
export function getDebateSummary(
  simulationId: string,
): Promise<AxiosResponse<ApiResponse<DebateSummary>>> {
  return service.get(`/api/research/simulate/${simulationId}/summary`)
}

// ── Direct Draft (from existing simulation) ────────────────────────────

/**
 * Generate a paper draft directly from an existing simulation's transcript.
 * Skips Stages 1-3.
 */
export function draftFromSimulation(
  data: { simulation_id: string; research_idea: string },
): Promise<AxiosResponse<ApiResponse<{ run_id: string }>>> {
  return service.post('/api/research/ais/draft-from-simulation', data)
}

// ── Stage 4: Thought Injection ─────────────────────────────────────────

/**
 * Stage 4: Inject human thought/guidance into the pipeline.
 */
export function injectThought(
  runId: string,
  data: InjectThoughtParams,
): Promise<AxiosResponse<ApiResponse<{ status: string }>>> {
  return service.post(`/api/research/ais/${runId}/inject`, data)
}

/**
 * Trigger standalone self-review on an existing draft.
 */
export function triggerReview(
  runId: string,
  data: TriggerReviewParams = {},
): Promise<AxiosResponse<ApiResponse<{ review_overall: number }>>> {
  return service.post(`/api/research/ais/${runId}/review`, data)
}

// ── SSE Stream ─────────────────────────────────────────────────────────

/**
 * Stream pipeline progress via Server-Sent Events.
 * Returns EventSource — caller can call .close() to stop.
 */
export function streamPipeline(
  runId: string,
  onEvent?: (data: SSEEvent) => void,
  onError?: (err: Event) => void,
): EventSource {
  const baseURL = service.defaults.baseURL || ''
  const url = `${baseURL}/api/research/ais/${runId}/stream`
  const es = new EventSource(url)

  es.onmessage = (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data) as SSEEvent
      if (onEvent) onEvent(data)
    } catch (e) {
      console.error('SSE parse error:', e)
    }
  }

  es.onerror = (err: Event) => {
    if (onError) onError(err)
    es.close()
  }

  return es
}

// ── Path A/B Routing ───────────────────────────────────────────────────

interface PathRecommendation {
  recommended_path: 'A' | 'B'
  confidence: number
  reasoning: string
}

/**
 * Get path recommendation (A=draft, B=experiment) for a pipeline run.
 */
export function getPathRecommendation(
  runId: string,
): Promise<AxiosResponse<ApiResponse<PathRecommendation>>> {
  return service.get(`/api/research/ais/${runId}/recommend-path`)
}

// ── ScienceClaw Search ─────────────────────────────────────────────────

/**
 * Search academic databases via ScienceClaw / OSSR fallback.
 */
export function scienceClawSearch(
  data: SearchParams,
): Promise<AxiosResponse<ApiResponse<{ papers: ImportPaper[]; total: number }>>> {
  return service.post('/api/research/ais/search', data)
}

/**
 * Import papers from ScienceClaw search results into OSSR database.
 */
export function importSearchResults(
  data: { papers: ImportPaper[] },
): Promise<AxiosResponse<ApiResponse<{ imported: number }>>> {
  return service.post('/api/research/ais/search/import', data)
}

/**
 * List available research tool integrations and their status.
 */
export function getResearchTools(): Promise<AxiosResponse<ApiResponse<ToolStatus[]>>> {
  return service.get('/api/research/ais/tools', { timeout: STATUS_TIMEOUT })
}

// ── Stage 6: Experiment ────────────────────────────────────────────────

/**
 * Start Stage 6: experiment execution via AI-Scientist.
 */
export function startExperiment(
  runId: string,
  data: StartExperimentParams = {},
): Promise<AxiosResponse<ApiResponse<{ task_id: string }>>> {
  return service.post(`/api/research/ais/${runId}/experiment`, data, { timeout: LONG_TIMEOUT })
}

/**
 * Get experiment status for a pipeline run.
 */
export function getExperimentStatus(
  runId: string,
): Promise<AxiosResponse<ApiResponse<TaskStatus>>> {
  return service.get(`/api/research/ais/${runId}/experiment/status`)
}

/**
 * Get full experiment result.
 */
export function getExperimentResult(
  runId: string,
): Promise<AxiosResponse<ApiResponse<Record<string, unknown>>>> {
  return service.get(`/api/research/ais/${runId}/experiment/result`)
}

// ── History (unified CLI + platform results) ───────────────────────────

/**
 * List all historical runs (CLI test runs + DB pipeline runs), paginated.
 */
export function getHistoryRuns(
  params: HistoryListParams = {},
): Promise<AxiosResponse<ApiResponse<{ runs: HistoryRun[]; total: number }>>> {
  return service.get('/api/research/history/runs', { params })
}

/**
 * Get full detail for a single historical run.
 */
export function getHistoryRunDetail(
  runId: string,
): Promise<AxiosResponse<ApiResponse<HistoryRun>>> {
  return service.get(`/api/research/history/runs/${runId}`)
}

/**
 * Get debate transcript for a historical run.
 */
export function getHistoryTranscript(
  runId: string,
): Promise<AxiosResponse<ApiResponse<Record<string, unknown>>>> {
  return service.get(`/api/research/history/runs/${runId}/transcript`)
}

/**
 * Get paper draft for a historical run.
 */
export function getHistoryDraft(
  runId: string,
): Promise<AxiosResponse<ApiResponse<PaperDraft>>> {
  return service.get(`/api/research/history/runs/${runId}/draft`)
}

/**
 * Import a CLI test run into the platform DB.
 */
export function importCliRun(
  runId: string,
): Promise<AxiosResponse<ApiResponse<{ imported: boolean }>>> {
  return service.post(`/api/research/history/runs/${runId}/import`)
}

/**
 * Get the URL for a run's HTML artifact (opened in new tab).
 */
export function getRunArtifactUrl(runId: string): string {
  const baseURL = service.defaults.baseURL || ''
  return `${baseURL}/api/research/history/runs/${runId}/artifact`
}

/**
 * Get recent activity across ALL types (debates, pipeline, papers, reports).
 */
export function getRecentActivity(
  limit = 10,
): Promise<AxiosResponse<ApiResponse<Array<Record<string, unknown>>>>> {
  return service.get('/api/research/history/recent', { params: { limit } })
}

// ── Cost Estimate ──────────────────────────────────────────────────────

/**
 * Get estimated cost for a pipeline action.
 */
export function getCostEstimate(
  params: CostEstimateParams,
): Promise<AxiosResponse<ApiResponse<{ estimated_cost_usd: number; breakdown: Record<string, number> }>>> {
  return service.get('/api/research/history/cost-estimate', { params })
}

// ═══════════════════════════════════════════════════════════════════════
// V2 Workflow Graph Engine
// ═══════════════════════════════════════════════════════════════════════

export interface WorkflowNode {
  node_id: string
  run_id: string
  node_type: string
  label: string
  config: Record<string, unknown>
  inputs: Record<string, unknown>
  outputs: Record<string, unknown>
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'invalidated'
  score: number | null
  model_used: string
  model_config: Record<string, unknown>
  error: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface WorkflowEdge {
  edge_id: string
  run_id: string
  source_node_id: string
  target_node_id: string
  edge_type: 'dependency' | 'optional' | 'conditional' | 'feedback'
  condition: Record<string, unknown>
}

export interface GraphState {
  run_id: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  summary: {
    total_nodes: number
    completed: number
    running: number
    failed: number
    pending: number
    progress_pct: number
  }
}

export interface ReviewFinding {
  domain: string
  severity: 'critical' | 'major' | 'minor' | 'suggestion'
  category: string
  description: string
  recommendation: string
  evidence_reference: string
}

export interface SpecialistReviewResult {
  domain: string
  specialist_name: string
  findings: ReviewFinding[]
  overall_score: number
  summary: string
  model_used: string
  finding_count: number
  critical_count: number
  major_count: number
}

export interface EvidenceGap {
  claim: string
  section: string
  gap_type: string
  severity: 'critical' | 'major' | 'minor'
  description: string
}

export interface ProposedExperiment {
  name: string
  objective: string
  addresses_gaps: string[]
  methodology: string
  equipment: string[]
  controls: string[]
  calibration: string[]
  expected_measurements: Array<{ parameter: string; unit: string; range: string }>
  procedure_steps: string[]
  estimated_duration: string
  data_template: Record<string, unknown>
}

export interface ExperimentDesignResult {
  gaps: EvidenceGap[]
  experiments: ProposedExperiment[]
  overall_readiness: number
  summary: string
  model_used: string
  gap_count: number
  critical_gaps: number
  experiment_count: number
}

export interface RunPaper {
  paper_id: string
  doi: string
  title: string
  abstract: string
  authors: string[]
  year: string
  publication_date: string
  source: string
  citation_count: number
  keywords: string[]
  full_text_url: string | null
  status: string
}

export interface RunTopic {
  topic_id: string
  name: string
  level: number
  description: string
  parent_id: string | null
  paper_count: number
  key_papers: Array<{ paper_id: string; title: string; doi: string; citations: number }>
  contradictions: string[]
  gaps: Array<string | { description: string }>
  novelty_opportunities: Array<string | { description: string }>
  cluster_summary: string
}

export interface SpecialistDomain {
  domain: string
  name: string
  expertise: string
}

/** Get the full workflow DAG state (nodes, edges, summary). Auto-migrates legacy runs. */
export function getWorkflowGraph(
  runId: string,
): Promise<AxiosResponse<ApiResponse<GraphState>>> {
  return service.get(`/api/research/ais/${runId}/graph`)
}

/** Restart pipeline from a specific workflow node. Invalidates downstream. */
export function restartFromNode(
  runId: string,
  nodeId: string,
  autoExecute = true,
): Promise<AxiosResponse<ApiResponse<{ restarted_node: string; invalidated: string[]; invalidated_count: number; task_id?: string }>>> {
  return service.post(`/api/research/ais/${runId}/restart/${nodeId}`, { auto_execute: autoExecute })
}

/** Update LLM model for a specific workflow node. */
export function updateNodeModel(
  runId: string,
  nodeId: string,
  model: string,
): Promise<AxiosResponse<ApiResponse<{ node_id: string; model: string }>>> {
  return service.put(`/api/research/ais/${runId}/node/${nodeId}/model`, { model })
}

/** Update advanced settings for a specific workflow node. */
export function updateNodeSettings(
  runId: string,
  nodeId: string,
  settings: Record<string, unknown>,
): Promise<AxiosResponse<ApiResponse<{ node_id: string; settings: Record<string, unknown> }>>> {
  return service.put(`/api/research/ais/${runId}/node/${nodeId}/settings`, settings)
}

export type PaperSortBy = 'citations' | 'year' | 'relevance' | 'title'

/** Get papers associated with a pipeline run (paginated, searchable, sortable, filterable). */
export function getRunPapers(
  runId: string,
  params: { page?: number; per_page?: number; search?: string; sort_by?: PaperSortBy; source?: string } = {},
): Promise<AxiosResponse<ApiResponse<{
  papers: RunPaper[]
  total: number
  page: number
  per_page: number
  pages: number
  sort_by: string
  source_filter: string
  available_sources: string[]
}>>> {
  return service.get(`/api/research/ais/${runId}/papers`, { params })
}

/** Get interactive topic map data for a pipeline run. */
export function getRunTopics(
  runId: string,
): Promise<AxiosResponse<ApiResponse<{ topics: RunTopic[]; count: number }>>> {
  return service.get(`/api/research/ais/${runId}/topics`)
}

/** Run specialist domain reviews. */
export function runSpecialistReview(
  runId: string,
  params: { domains?: string[]; strictness?: number; target?: 'idea' | 'debate' | 'draft'; model?: string } = {},
): Promise<AxiosResponse<ApiResponse<{ run_id: string; task_id: string }>>> {
  return service.post(`/api/research/ais/${runId}/specialist-review`, params, { timeout: LONG_TIMEOUT })
}

/** List available specialist review domains. */
export function getSpecialistDomains(): Promise<AxiosResponse<ApiResponse<{ domains: SpecialistDomain[] }>>> {
  return service.get('/api/research/ais/specialist-domains')
}

/** Run experiment design agent on a draft. */
export function runExperimentDesign(
  runId: string,
  params: { model?: string } = {},
): Promise<AxiosResponse<ApiResponse<{ run_id: string; task_id: string }>>> {
  return service.post(`/api/research/ais/${runId}/experiment-design`, params, { timeout: LONG_TIMEOUT })
}

/** Check multimodal/vision capability. */
export function getMultimodalStatus(): Promise<AxiosResponse<ApiResponse<{ vision_available: boolean; current_provider: string; current_model: string }>>> {
  return service.get('/api/research/ais/multimodal/status')
}

/** Analyze figures from a paper upload. */
export function analyzeFigures(
  runId: string,
  params: { upload_id: string; claims?: string[] },
): Promise<AxiosResponse<ApiResponse<{ run_id: string; task_id: string; vision_mode: boolean }>>> {
  return service.post(`/api/research/ais/${runId}/analyze-figures`, params, { timeout: LONG_TIMEOUT })
}

// ── Cost Tracking ─────────────────────────────────────────────────────

export interface RunCost {
  run_id: string
  total_cost_usd: number
  total_input_tokens: number
  total_output_tokens: number
  by_node: Record<string, { cost_usd: number; calls: number }>
}

/** Get aggregated cost data for a pipeline run. */
export function getRunCost(
  runId: string,
): Promise<AxiosResponse<ApiResponse<RunCost>>> {
  return service.get(`/api/research/ais/${runId}/cost`)
}

// ── V2 Node Execution ─────────────────────────────────────────────────

/** Execute a specific workflow node via StageExecutor. */
export function executeNode(
  runId: string,
  nodeId: string,
): Promise<AxiosResponse<ApiResponse<{ run_id: string; node_id: string; task_id: string }>>> {
  return service.post(`/api/research/ais/${runId}/execute/${nodeId}`, {}, { timeout: LONG_TIMEOUT })
}

/** Auto-advance pipeline through all ready nodes until human gate or completion. */
export function autoAdvance(
  runId: string,
): Promise<AxiosResponse<ApiResponse<{ run_id: string; task_id: string }>>> {
  return service.post(`/api/research/ais/${runId}/auto-advance`, {}, { timeout: LONG_TIMEOUT })
}

// ── Draft Version History ─────────────────────────────────────────────

export interface DraftVersion {
  version_id: string
  draft_id: string
  run_id: string
  version_num: number
  title: string
  word_count: number
  change_summary: string
  review_score: number | null
  created_at: string
  sections?: Array<{ name: string; content: string }>
  bibliography?: Array<Record<string, unknown>>
}

export interface VersionDiff {
  version_a: { version_id: string; version_num: number }
  version_b: { version_id: string; version_num: number }
  added_sections: string[]
  removed_sections: string[]
  changed_sections: Array<{ section: string; word_count_before: number; word_count_after: number; delta: number }>
  word_count_delta: number
  score_delta: number
}

/** List all draft versions for a run. */
export function getDraftVersions(
  runId: string,
): Promise<AxiosResponse<ApiResponse<{ versions: DraftVersion[]; count: number }>>> {
  return service.get(`/api/research/ais/${runId}/draft/versions`)
}

/** Get full draft version data. */
export function getDraftVersion(
  versionId: string,
): Promise<AxiosResponse<ApiResponse<DraftVersion>>> {
  return service.get(`/api/research/ais/draft/version/${versionId}`)
}

/** Compare two draft versions. */
export function diffDraftVersions(
  versionA: string,
  versionB: string,
): Promise<AxiosResponse<ApiResponse<VersionDiff>>> {
  return service.get(`/api/research/ais/draft/diff`, { params: { a: versionA, b: versionB } })
}

// ── LaTeX / BibTeX Export ─────────────────────────────────────────────

/** Export draft as LaTeX (.tex file download). */
export function exportLatex(runId: string): string {
  return `/api/research/ais/${runId}/export/latex`
}

/** Export bibliography as BibTeX (.bib file download). */
export function exportBibtex(runId: string): string {
  return `/api/research/ais/${runId}/export/bibtex`
}

// ── Project Templates ─────────────────────────────────────────────────

export interface ProjectTemplate {
  template_id: string
  name: string
  description: string
  config: Record<string, unknown>
  step_settings: Record<string, unknown>
  sources: string[]
  category: string
  is_builtin: boolean
  created_at: string
}

/** List all project templates. */
export function getTemplates(): Promise<AxiosResponse<ApiResponse<{ templates: ProjectTemplate[]; count: number }>>> {
  return service.get('/api/research/ais/templates')
}

/** Get a single template. */
export function getTemplate(
  templateId: string,
): Promise<AxiosResponse<ApiResponse<ProjectTemplate>>> {
  return service.get(`/api/research/ais/templates/${templateId}`)
}

/** Create a user template. */
export function createTemplate(
  data: { name: string; description?: string; config?: Record<string, unknown>; step_settings?: Record<string, unknown>; sources?: string[]; category?: string },
): Promise<AxiosResponse<ApiResponse<{ template_id: string; name: string }>>> {
  return service.post('/api/research/ais/templates', data)
}

/** Delete a user-created template. */
export function deleteTemplate(
  templateId: string,
): Promise<AxiosResponse<ApiResponse<{ deleted: string }>>> {
  return service.delete(`/api/research/ais/templates/${templateId}`)
}

// ── P-2: Knowledge Engine ────────────────────────────────────────────

export interface KnowledgeEvidence {
  evidence_id: string
  source_type: string
  source_id: string
  title: string
  excerpt: string
  confidence: number
}

export interface KnowledgeClaim {
  claim_id: string
  text: string
  category: string
  confidence: number
  supporting: string[]
  contradicting: string[]
  extending: string[]
}

export interface KnowledgeGap {
  gap_id: string
  description: string
  severity: string
  related_claims: string[]
  suggested_approach: string
  evidence_needed: string
}

export interface NoveltyAssessment {
  claim_id: string
  novelty_score: number
  explanation: string
  closest_existing: string[]
  differentiators: string[]
}

export interface SubQuestion {
  question_id: string
  text: string
  parent_id: string | null
  evidence_coverage: number
  related_claims: string[]
}

export interface KnowledgeHypothesis {
  hypothesis_id: string
  problem_statement: string
  contribution: string
  differentiators: string[]
  predicted_impact: string
  supporting_gaps: string[]
  novelty_basis: string[]
}

export interface KnowledgeArtifact {
  artifact_id: string
  run_id: string
  research_idea: string
  claims: KnowledgeClaim[]
  evidence: KnowledgeEvidence[]
  gaps: KnowledgeGap[]
  novelty_assessments: NoveltyAssessment[]
  sub_questions: SubQuestion[]
  hypothesis: KnowledgeHypothesis | null
  argument_skeleton: Array<{
    section_id: string
    heading: string
    purpose: string
    key_points: string[]
    assigned_citations: string[]
    order: number
  }>
  created_at: string
  updated_at: string
}

export interface ClaimGraphData {
  nodes: Array<{
    id: string
    type: 'claim' | 'evidence' | 'gap'
    label: string
    full_text: string
    [key: string]: unknown
  }>
  links: Array<{
    source: string
    target: string
    type: 'supports' | 'contradicts' | 'extends' | 'gap_for'
  }>
  stats: { claims: number; evidence: number; gaps: number; links: number }
}

export interface NoveltyMapData {
  assessments: NoveltyAssessment[]
  heatmap: Array<{
    claim_id: string
    text: string
    novelty_score: number
    zone: 'novel' | 'partial' | 'covered'
    explanation: string
  }>
  stats: { avg_novelty: number; novel_count: number; covered_count: number }
}

export interface QuestionTreeData {
  questions: SubQuestion[]
  tree: Array<{
    id: string
    text: string
    evidence_coverage: number
    children: Array<{ id: string; text: string; evidence_coverage: number; children: unknown[] }>
  }>
  stats: { total_questions: number; avg_coverage: number; uncovered_count: number }
}

/** Build a knowledge artifact from pipeline outputs. */
export function buildKnowledgeArtifact(
  runId: string,
  params: { model?: string } = {},
): Promise<AxiosResponse<ApiResponse<KnowledgeArtifact>>> {
  return service.post(`/api/research/ais/${runId}/knowledge/build`, params, { timeout: LONG_TIMEOUT })
}

/** Get existing knowledge artifact. */
export function getKnowledgeArtifact(
  runId: string,
): Promise<AxiosResponse<ApiResponse<KnowledgeArtifact>>> {
  return service.get(`/api/research/ais/${runId}/knowledge`)
}

/** Get the claim-evidence graph for visualization. */
export function getClaimGraph(
  runId: string,
): Promise<AxiosResponse<ApiResponse<ClaimGraphData>>> {
  return service.get(`/api/research/ais/${runId}/knowledge/claim-graph`)
}

/** Map novelty per claim against literature. */
export function mapNovelty(
  runId: string,
  params: { model?: string } = {},
): Promise<AxiosResponse<ApiResponse<NoveltyMapData>>> {
  return service.post(`/api/research/ais/${runId}/knowledge/novelty`, params, { timeout: LONG_TIMEOUT })
}

/** Decompose research idea into sub-questions. */
export function decomposeQuestions(
  runId: string,
  params: { model?: string } = {},
): Promise<AxiosResponse<ApiResponse<QuestionTreeData>>> {
  return service.post(`/api/research/ais/${runId}/knowledge/questions`, params, { timeout: LONG_TIMEOUT })
}

/** Build a structured contribution hypothesis. */
export function buildHypothesis(
  runId: string,
  params: { model?: string } = {},
): Promise<AxiosResponse<ApiResponse<{ hypothesis: KnowledgeHypothesis; supporting_context: Record<string, number> }>>> {
  return service.post(`/api/research/ais/${runId}/knowledge/hypothesis`, params, { timeout: LONG_TIMEOUT })
}

/** Generate citation-backed argument skeleton. */
export function buildArgumentSkeleton(
  runId: string,
  params: { model?: string } = {},
): Promise<AxiosResponse<ApiResponse<{
  sections: Array<{ section_id: string; heading: string; purpose: string; key_points: string[]; assigned_citations: string[]; order: number }>
  stats: { total_sections: number; total_citations: number; uncited_sections: number }
}>>> {
  return service.post(`/api/research/ais/${runId}/knowledge/argument-skeleton`, params, { timeout: LONG_TIMEOUT })
}

/** Export full knowledge artifact as JSON. */
export function exportKnowledge(
  runId: string,
): Promise<AxiosResponse<ApiResponse<KnowledgeArtifact>>> {
  return service.get(`/api/research/ais/${runId}/knowledge-export`)
}

// ── P-3: Reviewer/Author Adversarial Loop ────────────────────────────

export interface ReviewComment {
  comment_id: string
  reviewer_type: string
  section: string
  text: string
  severity: 'critical' | 'major' | 'minor' | 'suggestion'
  confidence: number
  impact: 'high' | 'medium' | 'low'
  category: string
  quote: string
}

export interface ReviewerResult {
  reviewer_type: string
  reviewer_name: string
  overall_score: number
  summary: string
  comments: ReviewComment[]
  strengths: string[]
  weaknesses: string[]
}

export interface ReviewConflict {
  conflict_id: string
  reviewer_a: string
  reviewer_b: string
  description: string
  resolution_suggestion: string
}

export interface RevisionTheme {
  theme_id: string
  title: string
  description: string
  priority: number
  impact: string
  comment_ids: string[]
  suggested_action: string
}

export interface RevisionRound {
  round_id: string
  run_id: string
  round_number: number
  rewrite_mode: string
  reviewer_types: string[]
  results: ReviewerResult[]
  themes: RevisionTheme[]
  conflicts: ReviewConflict[]
  avg_score: number
  created_at: string
}

export type RewriteMode = 'conservative' | 'novelty' | 'clarity' | 'journal'

/** Get available reviewer archetypes. */
export function getReviewerArchetypes(): Promise<AxiosResponse<ApiResponse<Record<string, { name: string; focus: string; rubric: string[] }>>>> {
  return service.get('/api/research/ais/review/archetypes')
}

/** Run a full review round with selected reviewer panel. */
export function runReviewRound(
  runId: string,
  params: { reviewer_types?: string[]; strictness?: number; rewrite_mode?: RewriteMode; model?: string } = {},
): Promise<AxiosResponse<ApiResponse<RevisionRound>>> {
  return service.post(`/api/research/ais/${runId}/review/round`, params, { timeout: LONG_TIMEOUT })
}

/** Detect conflicts and cluster into themes. */
export function detectConflicts(
  runId: string,
  params: { model?: string } = {},
): Promise<AxiosResponse<ApiResponse<{
  conflicts: ReviewConflict[]
  themes: RevisionTheme[]
  stats: { conflict_count: number; theme_count: number; critical_themes: number }
}>>> {
  return service.post(`/api/research/ais/${runId}/review/conflicts`, params, { timeout: LONG_TIMEOUT })
}

/** Create a prioritized revision plan. */
export function createRevisionPlan(
  runId: string,
  params: { model?: string } = {},
): Promise<AxiosResponse<ApiResponse<{
  plan: Array<{ priority: number; theme: string; action: string; sections_affected: string[]; estimated_effort: string; rationale: string }>
  stats: { total_actions: number; major_actions: number }
}>>> {
  return service.post(`/api/research/ais/${runId}/review/revision-plan`, params, { timeout: LONG_TIMEOUT })
}

/** Generate point-by-point response to reviewers. */
export function generateRebuttal(
  runId: string,
  params: { model?: string } = {},
): Promise<AxiosResponse<ApiResponse<{
  responses: Array<{ comment_id: string; reviewer_type: string; response: string; action_taken: string; status: string }>
  stats: { total: number; addressed: number; disagreed: number }
}>>> {
  return service.post(`/api/research/ais/${runId}/review/rebuttal`, params, { timeout: LONG_TIMEOUT })
}

/** Get full revision history with analytics. */
export function getRevisionHistory(
  runId: string,
): Promise<AxiosResponse<ApiResponse<{
  rounds: RevisionRound[]
  score_trajectory: Array<{ round: number; avg_score: number }>
  regression_warnings: Array<{ metric: string; round: number; detail: string }>
  total_rounds: number
  latest_score: number
  improving: boolean
}>>> {
  return service.get(`/api/research/ais/${runId}/review/history`)
}

/** Get available rewrite modes. */
export function getRewriteModes(): Promise<AxiosResponse<ApiResponse<Record<string, { name: string; description: string }>>>> {
  return service.get('/api/research/ais/review/rewrite-modes')
}

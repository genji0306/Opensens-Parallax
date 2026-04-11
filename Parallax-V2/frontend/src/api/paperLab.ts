import service from './client'
import type { AxiosResponse } from 'axios'
import type { ApiResponse, PaperUpload } from '@/types/api'

// ── Local Types ────────────────────────────────────────────────────────

export interface ReviewConfig {
  rounds?: number
  reviewers?: number
  authors?: number
  live?: boolean
}

export interface ReviewRound {
  round: number
  reviews: Array<{
    reviewer: string
    score: number
    comments: string
    strengths?: string[]
    weaknesses?: string[]
  }>
  revision?: {
    author: string
    changes: string[]
  }
}

interface FillGapsConfig {
  live?: boolean
}

interface SpecialistReviewConfig {
  domains?: string[]
  strictness?: number
  target?: 'draft'
  model?: string
}

export interface ProgressEvent {
  type: string
  data: unknown
}

/** Backend draft response shape */
export interface DraftPayload {
  upload_id: string
  title: string
  draft: string
  word_count: number
  status: string
}

/** Backend rounds response shape (wraps ReviewRound[]) */
export interface RoundsPayload {
  rounds: ReviewRound[]
  score_progression: number[]
  reviewers: Array<Record<string, unknown>>
  source_audit: Record<string, unknown>
}

export interface PaperUploadResponse {
  upload_id: string
  title?: string
  language?: string
  detected_field?: string
  section_count?: number
  sections?: string[]
  word_count?: number
  reference_count?: number
  parser_engine?: string
  parser_mode?: string
  parse_quality?: Record<string, unknown>
}

// ── Paper Lab (Rehabilitation Pipeline) ────────────────────────────────

/**
 * Upload a paper draft file (.pdf, .doc, .docx, .txt, or .md).
 */
export function uploadPaper(
  file: File,
): Promise<AxiosResponse<ApiResponse<PaperUploadResponse>>> {
  const formData = new FormData()
  formData.append('file', file)
  return service.post('/api/research/paper-lab/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60_000,
  })
}

/**
 * Get upload status and scores.
 */
export function getUploadStatus(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<PaperUpload>>> {
  return service.get(`/api/research/paper-lab/${uploadId}/status`)
}

/**
 * Start the adversarial review game.
 * Backend returns: { upload_id, task_id, config }
 */
export function startReview(
  uploadId: string,
  config: ReviewConfig = {},
): Promise<AxiosResponse<ApiResponse<{ upload_id: string; task_id: string; session_id: string; config: ReviewConfig }>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/start-review`, config)
}

/**
 * Get all review/revision round data.
 * Backend may return either RoundsPayload (wrapped) or ReviewRound[] (legacy).
 */
export function getRounds(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<RoundsPayload | ReviewRound[]>>> {
  return service.get(`/api/research/paper-lab/${uploadId}/rounds`)
}

/**
 * Get the current (latest revised) draft.
 * Backend returns: { upload_id, title, draft, word_count, status }
 */
export function getDraft(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<DraftPayload>>> {
  return service.get(`/api/research/paper-lab/${uploadId}/draft`)
}

/**
 * List all paper uploads.
 */
export function listUploads(): Promise<AxiosResponse<ApiResponse<PaperUpload[]>>> {
  return service.get('/api/research/paper-lab/uploads')
}

/**
 * Subscribe to SSE stream for live progress.
 * Returns an unsubscribe function that closes the EventSource.
 */
export function subscribeToProgress(
  uploadId: string,
  sessionId: string | undefined,
  onEvent: (event: ProgressEvent) => void,
): () => void {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
  const params = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''
  const url = `${baseUrl}/api/research/paper-lab/${uploadId}/stream${params}`
  const source = new EventSource(url)

  const eventTypes = [
    'status',
    'source_audit',
    'review_start',
    'review_complete',
    'revision_start',
    'revision_complete',
    'converged',
    'complete',
    'error',
  ] as const

  eventTypes.forEach((type) => {
    source.addEventListener(type, (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        onEvent({ type, data })
      } catch {
        onEvent({ type, data: e.data })
      }
    })
  })

  source.onmessage = (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data)
      onEvent({ type: data.type || 'message', data })
    } catch {
      onEvent({ type: 'message', data: e.data })
    }
  }

  source.onerror = () => {
    source.close()
    // Notify caller so UI can exit reviewing state and show actionable feedback
    onEvent({ type: 'stream_error', data: { message: 'SSE connection lost' } })
  }

  return () => source.close()
}

/**
 * Run gap-fill: search for missing references and novelty boost.
 */
export function fillGaps(
  uploadId: string,
  config: FillGapsConfig = {},
): Promise<AxiosResponse<ApiResponse<{ status: string }>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/fill-gaps`, config, {
    timeout: 120_000,
  })
}

/**
 * Run specialist domain review for a paper upload (async).
 */
export function runSpecialistReview(
  uploadId: string,
  config: SpecialistReviewConfig = {},
): Promise<AxiosResponse<ApiResponse<{ upload_id: string; task_id: string; message: string }>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/specialist-review`, config, {
    timeout: 120_000,
  })
}

/**
 * Get latest specialist review snapshot for a paper upload.
 */
export function getSpecialistReview(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<Record<string, unknown>>>> {
  return service.get(`/api/research/paper-lab/${uploadId}/specialist-review`)
}

/**
 * Download the final draft as .docx file (opens in new tab).
 */
export function exportDocx(uploadId: string): void {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
  window.open(`${baseUrl}/api/research/paper-lab/${uploadId}/export-docx`, '_blank')
}

/**
 * Get Response to Reviewers document.
 * For 'docx' or 'markdown' format, opens in a new browser tab.
 * For 'json' format, returns the data via axios.
 */
export function getResponseToReviewers(
  uploadId: string,
  format: 'json' | 'markdown' | 'docx' = 'json',
): Promise<AxiosResponse<ApiResponse<Record<string, unknown>>> | void> {
  if (format === 'docx' || format === 'markdown') {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
    window.open(
      `${baseUrl}/api/research/paper-lab/${uploadId}/response-to-reviewers?format=${format}`,
      '_blank',
    )
    return Promise.resolve()
  }
  return service.get(`/api/research/paper-lab/${uploadId}/response-to-reviewers?format=json`)
}

/**
 * Download rewrite instructions (comprehensive prompt for Claude Opus/Sonnet).
 * Opens as .md file download in new tab.
 */
export function getRewriteInstructions(uploadId: string): void {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
  window.open(
    `${baseUrl}/api/research/paper-lab/${uploadId}/rewrite-instructions?format=markdown`,
    '_blank',
  )
}

// ── Visualization Handler ──────────────────────────────────────────────────

export type DiagramType = 'flowchart' | 'mindmap' | 'sequence' | 'timeline' | 'quadrant' | 'infographic'

export interface FigureResult {
  ref: string
  caption_excerpt: string
  inferred_type: string
  reconstruction_code: string
  data_requirements: string[]
  issues: string[]
}

export interface FigureAnalysis {
  figure_count: number
  figures: FigureResult[]
  overall_notes: string
  error?: boolean
}

export interface TableIssue {
  cell: string
  severity: 'critical' | 'major' | 'minor'
  description: string
  corrected_value: string | null
}

export interface TableResult {
  ref: string
  title: string
  raw_data: { headers: string[]; rows: string[][] }
  issues: TableIssue[]
  analysis_note: string
  corrected_data: { headers: string[]; rows: string[][] }
}

export interface TableAnalysis {
  table_count: number
  tables: TableResult[]
  summary: string
  error?: boolean
}

export interface DiagramResult {
  diagram_type: DiagramType
  mermaid_code: string | null
  title: string
  description: string
  engine?: string
  error?: string
  gemini_required?: boolean
}

export interface SimulationProposal {
  name: string
  goal: string
  method: string
  tools: string[]
  expected_outcome: string
}

export interface CrossAnalysis {
  source: string
  rationale: string
  access: string
  expected_insight: string
}

export interface StatementImprovement {
  original: string
  improved: string
  rationale: string
  section_hint: string
}

export interface DeepAnalysisResult {
  simulation_proposals: SimulationProposal[]
  cross_analysis: CrossAnalysis[]
  statement_improvements: StatementImprovement[]
  overall_assessment: string
  engine?: string
  error?: string
  gemini_required?: boolean
}

export interface VisualizationCache {
  figures?: FigureAnalysis
  tables?: TableAnalysis
  deep_analysis?: DeepAnalysisResult
  [key: string]: unknown // diagram_flowchart, diagram_mindmap etc.
}

/** Trigger async figure analysis. Poll getVisualizations() for results. */
export function analyzeFigures(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<{ task_id: string }>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/analyze-figures`)
}

/** Trigger async table extraction + correction. Poll getVisualizations() for results. */
export function analyzeTables(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<{ task_id: string }>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/analyze-tables`)
}

/** Generate a Mermaid diagram synchronously via Gemini 2.0 Flash. */
export function generateDiagram(
  uploadId: string,
  diagramType: DiagramType = 'flowchart',
): Promise<AxiosResponse<ApiResponse<DiagramResult>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/generate-diagram`, {
    diagram_type: diagramType,
  })
}

/** Trigger async deep thinking analysis. Poll getVisualizations() for results. */
export function runDeepAnalysis(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<{ task_id: string }>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/deep-analysis`)
}

/** Fetch all cached visualization results for an upload. */
export function getVisualizations(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<VisualizationCache>>> {
  return service.get(`/api/research/paper-lab/${uploadId}/visualizations`)
}

// ── Scientific Visualization (Vega-Lite rendering + quality audit) ────

export interface RenderedFigure {
  ref: string
  title: string
  caption: string
  chart_type: string
  vega_lite_spec: Record<string, unknown> | null
  renderable: boolean
  reason?: string
  data_requirements: string[]
  issues: string[]
}

export interface FigureRenderResult {
  figures: RenderedFigure[]
  count: number
}

export interface RuleCheck {
  rule_id: string
  rule: string
  check: string
  status: 'pass' | 'warn' | 'fail'
  note: string
}

export interface FigureAuditEntry {
  ref: string
  chart_type: string
  score: number
  checks: RuleCheck[]
}

export interface FigureAuditResult {
  overall_score: number
  figure_count: number
  figures: FigureAuditEntry[]
  recommendations: string[]
  rules_reference: string
}

/** Render figures as Vega-Lite specs. Requires analyze-figures first. */
export function renderFigures(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<FigureRenderResult>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/render-figures`)
}

/** Audit figures against Ten Simple Rules. Requires analyze-figures first. */
export function auditFigures(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<FigureAuditResult>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/audit-figures`)
}

// ── Multi-Document Comparative Analysis ───────────────────────────────────

export interface ComparativeDifference {
  theme: string
  description: string
}

export interface ConflictingResult {
  finding: string
  paper_A_claim: string
  paper_B_claim: string
  resolution_suggestion: string
}

export interface Synergy {
  concept: string
  explanation: string
}

export interface ComparativeAnalysisResult {
  comparative_summary: string
  methodological_differences: ComparativeDifference[]
  conflicting_results: ConflictingResult[]
  synergies: Synergy[]
  engine: string
}

export function runComparativeAnalysis(
  uploadIds: string[],
): Promise<AxiosResponse<ApiResponse<ComparativeAnalysisResult>>> {
  return service.post(`/api/research/paper-lab/compare`, { upload_ids: uploadIds })
}

// ── Visualization Artifacts + Planning ────────────────────────────────────

export type VisualizationArtifactType =
  | 'chart'
  | 'diagram'
  | 'table'
  | 'graphical_abstract'
  | 'poster_panel'
  | 'slide'

export type VisualizationArtifactIntent =
  | 'reconstruct'
  | 'improve'
  | 'create_missing'
  | 'summarize'

export type VisualizationArtifactStatus = 'draft' | 'ready' | 'needs_input' | 'failed'

export interface VisualizationArtifact {
  artifact_id: string
  upload_id: string
  type: VisualizationArtifactType
  intent: VisualizationArtifactIntent
  title: string
  status: VisualizationArtifactStatus
  version: number
  payload: Record<string, unknown>
  audit: {
    confidence?: number
    issues?: string[]
    consistency_status?: 'pass' | 'warn' | 'fail'
    ready?: boolean
  }
  provenance: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface VisualizationPlanItem {
  plan_id: string
  type: VisualizationArtifactType
  intent: VisualizationArtifactIntent
  title: string
  rationale: string
  source_refs: string[]
  source_sections: string[]
  linked_review_findings: string[]
  required_data: string[]
  recommended_engine: string
  data_mode: string
  confidence: number
  content_description?: string
  priority?: string
  layout_modes?: string[]
}

export interface VisualizationPlan {
  reconstruct: VisualizationPlanItem[]
  improve: VisualizationPlanItem[]
  create_missing: VisualizationPlanItem[]
  graphical_abstract: VisualizationPlanItem[]
  communication_outputs: VisualizationPlanItem[]
}

export interface SectionRefinementResult {
  refinement_id?: string
  action: string
  section: string
  original_text: string
  revised_text: string
  applied?: boolean
  diff: {
    before_word_count: number
    after_word_count: number
    summary: string
  }
  addressed_recommendations: string[]
}

export interface ApplyRefinementResult {
  upload_id: string
  refinement_id: string
  section: string
  current_draft: string
  sections: Array<Record<string, unknown>>
}

export interface DraftHistoryPayload {
  upload_id: string
  applied_refinements: Array<{
    refinement_id: string
    action: string
    section: string
    applied_at: string
    draft_before_excerpt?: string
    draft_after_excerpt?: string
  }>
  section_refinement_history: Array<{
    refinement_id: string
    action: string
    section: string
    summary: string
    created_at: string
    applied?: boolean
    applied_at?: string
  }>
  grounded_literature_history: Array<{
    focus: string
    ready: boolean
    suggestion_count: number
    verified_count?: number
    created_at: string
  }>
  last_applied_refinement_id?: string
}

export interface RevertRefinementResult {
  upload_id: string
  reverted_refinement_id: string
  current_draft: string
  sections: Array<Record<string, unknown>>
}

export interface GroundedLiteratureReviewResult {
  focus: string
  queries: string[]
  suggestions: Array<{
    citation_id: string
    title: string
    doi: string
    year: string
    source: string
    verified: boolean
    confidence: number
    query: string
    insertion_point: string
    provenance: Record<string, unknown>
  }>
  ready: boolean
  unverified_count: number
  note: string
}

export function getVisualizationPlan(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<VisualizationPlan>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/visualization-plan`, {})
}

export function listVisualizationArtifacts(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<VisualizationArtifact[]>>> {
  return service.get(`/api/research/paper-lab/${uploadId}/visualization-artifacts`)
}

export function createVisualizationArtifact(
  uploadId: string,
  body: Partial<VisualizationArtifact> & { type: VisualizationArtifactType; intent: VisualizationArtifactIntent; title: string },
): Promise<AxiosResponse<ApiResponse<VisualizationArtifact>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/artifacts`, body)
}

export function updateVisualizationArtifact(
  uploadId: string,
  artifactId: string,
  body: Record<string, unknown>,
): Promise<AxiosResponse<ApiResponse<VisualizationArtifact>>> {
  return service.put(`/api/research/paper-lab/${uploadId}/artifacts/${artifactId}`, body)
}

export function renderVisualizationArtifact(
  uploadId: string,
  artifactId: string,
): Promise<AxiosResponse<ApiResponse<VisualizationArtifact>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/artifacts/${artifactId}/render`, {})
}

export function auditVisualizationArtifact(
  uploadId: string,
  artifactId: string,
): Promise<AxiosResponse<ApiResponse<VisualizationArtifact>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/artifacts/${artifactId}/audit`, {})
}

export function exportVisualizationArtifact(
  uploadId: string,
  artifactId: string,
): Promise<AxiosResponse<ApiResponse<Record<string, unknown>>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/artifacts/${artifactId}/export`, {})
}

export function refinePaperSection(
  uploadId: string,
  action: string,
  visualizationPlan?: VisualizationPlan | null,
): Promise<AxiosResponse<ApiResponse<SectionRefinementResult>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/refine-section`, {
    action,
    visualization_plan: visualizationPlan,
  })
}

export function groundedLiteratureReview(
  uploadId: string,
  focus: string,
): Promise<AxiosResponse<ApiResponse<GroundedLiteratureReviewResult>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/literature-review`, { focus })
}

export function applyPaperRefinement(
  uploadId: string,
  refinement: SectionRefinementResult,
): Promise<AxiosResponse<ApiResponse<ApplyRefinementResult>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/apply-refinement`, { refinement })
}

export function getDraftHistory(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<DraftHistoryPayload>>> {
  return service.get(`/api/research/paper-lab/${uploadId}/draft-history`)
}

export function revertPaperRefinement(
  uploadId: string,
  refinementId: string,
): Promise<AxiosResponse<ApiResponse<RevertRefinementResult>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/revert-refinement`, { refinement_id: refinementId })
}

export function generateGraphicalAbstract(
  uploadId: string,
  layoutMode = 'process_summary',
): Promise<AxiosResponse<ApiResponse<VisualizationArtifact>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/graphical-abstract`, { layout_mode: layoutMode })
}

export function generateSlideStarter(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<VisualizationArtifact>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/slide-starter`, {})
}

export function generatePosterStarter(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<VisualizationArtifact>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/poster-starter`, {})
}

// ── PaperBanana Agentic Illustrations ──────────────────────────────────────

export interface PaperBananaResult {
  task_type: 'diagram' | 'plot'
  planner_output: string
  stylist_output: string
  visualizer_output: string
  code?: string
  format: 'mermaid' | 'base64_jpg' | 'error'
}

export function generatePaperBananaIllustration(
  uploadId: string,
  intent: string,
  taskType: 'diagram' | 'plot' = 'diagram',
): Promise<AxiosResponse<ApiResponse<PaperBananaResult>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/illustrations`, {
    intent,
    task_type: taskType
  })
}

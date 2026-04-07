import service from './client'
import type { AxiosResponse } from 'axios'
import type { ApiResponse, PaperUpload, PaperDraft } from '@/types/api'

// ── Local Types ────────────────────────────────────────────────────────

interface ReviewConfig {
  rounds?: number
  reviewers?: number
  authors?: number
  live?: boolean
}

interface ReviewRound {
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

interface ProgressEvent {
  type: string
  data: unknown
}

// ── Paper Lab (Rehabilitation Pipeline) ────────────────────────────────

/**
 * Upload a paper draft file (.docx, .txt, or .md).
 */
export function uploadPaper(
  file: File,
): Promise<AxiosResponse<ApiResponse<{ upload_id: string }>>> {
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
 */
export function startReview(
  uploadId: string,
  config: ReviewConfig = {},
): Promise<AxiosResponse<ApiResponse<{ status: string }>>> {
  return service.post(`/api/research/paper-lab/${uploadId}/start-review`, config)
}

/**
 * Get all review/revision round data.
 */
export function getRounds(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<ReviewRound[]>>> {
  return service.get(`/api/research/paper-lab/${uploadId}/rounds`)
}

/**
 * Get the current (latest revised) draft.
 */
export function getDraft(
  uploadId: string,
): Promise<AxiosResponse<ApiResponse<PaperDraft>>> {
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
  onEvent: (event: ProgressEvent) => void,
): () => void {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
  const url = `${baseUrl}/api/research/paper-lab/${uploadId}/stream`
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


export type StageId =
  | 'crawl'
  | 'map'
  | 'debate'
  | 'validate'
  | 'ideas'
  | 'draft'
  | 'experiment'
  | 'rehab'
  | 'pass'

export type StageStatus = 'done' | 'active' | 'pending' | 'failed' | 'skipped' | 'invalidated'

export interface StageInfo {
  id: StageId
  label: string
  shortLabel?: string
  description?: string
  icon: string
  status: StageStatus
  metric?: string
}

export interface StageResult {
  /** Stage-specific data blob from backend */
  [key: string]: unknown
}

export interface NextStepRecommendation {
  action: string
  label: string
  description?: string
  route?: string
  cost?: string
  urgent?: boolean
  actions?: Array<{
    label: string
    primary?: boolean
    handler?: string
  }>
}

export interface ProjectSummary {
  id: string
  run_id: string
  title: string
  topic: string
  type: 'debate' | 'ais' | 'paper' | 'paper_rehab' | 'report'
  status: string
  current_stage?: string
  created_at: string
  updated_at: string
  stage_results?: Record<string, StageResult>
  simulation_id?: string
  upload_id?: string
}

export interface CostEstimate {
  paid: number
  free: number
  total: number
  detail?: string
}

/**
 * Pipeline stage order — two parallel tracks:
 *
 * TOP:    Search → Map → Debate → Validate ←─── (feedback)
 *                   |  /               |                |
 * BOTTOM:        Ideas → Draft → Experiment → Revise → Pass
 */
export const STAGE_ORDER: StageId[] = [
  'crawl',
  'map',
  'debate',
  'validate',
  'ideas',
  'draft',
  'experiment',
  'rehab',
  'pass',
]

export const STAGE_LABELS: Record<StageId, string> = {
  crawl: 'Literature Search',
  map: 'Topic Mapping',
  debate: 'Agent Debate',
  validate: 'Validation',
  ideas: 'Idea Ranking',
  draft: 'Paper Draft',
  experiment: 'Experiment Design',
  rehab: 'Revision & Scoring',
  pass: 'Pass / Publish',
}

/** Short labels for compact contexts (pipeline tracker nodes) */
export const STAGE_SHORT_LABELS: Record<StageId, string> = {
  crawl: 'Search',
  map: 'Map',
  debate: 'Debate',
  validate: 'Validate',
  ideas: 'Ideas',
  draft: 'Draft',
  experiment: 'Experiment',
  rehab: 'Revise',
  pass: 'Pass',
}

/** Human-readable descriptions for each stage */
export const STAGE_DESCRIPTIONS: Record<StageId, string> = {
  crawl: 'Search academic databases for relevant papers and prior art',
  map: 'Build a topic map to identify research gaps and clusters',
  debate: 'Multi-agent debate to stress-test hypotheses',
  validate: 'Cross-reference conclusions with additional evidence',
  ideas: 'Generate and rank research ideas from debate outcomes',
  draft: 'Draft a research paper from the top-ranked idea',
  experiment: 'Design experiments to fill evidence gaps (if needed)',
  rehab: 'Iterative revision cycles — loops back to Validate if score too low',
  pass: 'Publication gate — reached when revision score is high enough',
}

export const STAGE_ICONS: Record<StageId, string> = {
  crawl: 'search',
  map: 'hub',
  debate: 'forum',
  validate: 'verified',
  ideas: 'lightbulb',
  draft: 'edit_document',
  experiment: 'science',
  rehab: 'healing',
  pass: 'check_circle',
}

export const ACTIVE_PROJECT_STATUSES = new Set([
  'running',
  'crawling',
  'mapping',
  'ideating',
  'debating',
  'human_review',
  'drafting',
  'reviewing',
  'experimenting',
])

const NUMERIC_STAGE_MAP: Record<number, StageId> = {
  1: 'crawl',
  2: 'ideas',
  3: 'debate',
  4: 'validate',
  5: 'draft',
  6: 'experiment',
  7: 'rehab',
  8: 'pass',
}

const DONE_BADGE_STATUSES = new Set([
  'completed',
  'done',
  'review_complete',
  'gap_filled',
  'passed',
])

const FAILED_BADGE_STATUSES = new Set([
  'failed',
  'error',
  'review_failed',
])

const ACTIVE_BADGE_STATUSES = new Set([
  'active',
  'reviewing',
])

export function normalizeStageId(raw: unknown): StageId | undefined {
  if (typeof raw === 'string') {
    if ((STAGE_ORDER as string[]).includes(raw)) return raw as StageId
    const numeric = Number.parseInt(raw, 10)
    if (!Number.isNaN(numeric)) return NUMERIC_STAGE_MAP[numeric]
    return undefined
  }

  if (typeof raw === 'number') {
    return NUMERIC_STAGE_MAP[raw]
  }

  return undefined
}

export function statusToBadgeStatus(
  status: string | null | undefined,
): 'done' | 'active' | 'pending' | 'failed' {
  const normalized = (status ?? '').trim().toLowerCase()

  if (DONE_BADGE_STATUSES.has(normalized)) return 'done'
  if (FAILED_BADGE_STATUSES.has(normalized)) return 'failed'
  if (ACTIVE_BADGE_STATUSES.has(normalized) || ACTIVE_PROJECT_STATUSES.has(normalized)) {
    return 'active'
  }

  return 'pending'
}

/**
 * Map raw backend/internal status strings to human-readable labels.
 * Used by StatusBadge and anywhere a status is displayed to the user.
 */
export const STATUS_DISPLAY: Record<string, string> = {
  // Pipeline statuses
  completed: 'Completed',
  running: 'Running',
  failed: 'Failed',
  pending: 'Pending',
  crawling: 'Searching',
  mapping: 'Mapping Topics',
  ideating: 'Generating Ideas',
  debating: 'Debating',
  human_review: 'Human Review',
  drafting: 'Drafting Paper',
  reviewing: 'Reviewing',
  experimenting: 'Running Experiment',
  // Stage statuses
  done: 'Done',
  active: 'In Progress',
  skipped: 'Skipped',
  invalidated: 'Invalidated',
  // Selection states
  awaiting_selection: 'Awaiting Your Selection',
  waiting_for_selection: 'Awaiting Your Selection',
  // Revision loop
  revising: 'Revising',
  passed: 'Passed',
  parsed: 'Parsed',
  review_complete: 'Review Complete',
  review_failed: 'Review Failed',
  gap_filled: 'Gap Filled',
  // Fallback
  unknown: 'Unknown',
}

/** Standard OSSR API response envelope */
export interface ApiResponse<T = unknown> {
  success: boolean
  data: T
  error?: string
  message?: string
}

/** Async task status (POST → 202 → poll) */
export interface TaskStatus {
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress?: number
  message?: string
  error?: string
}

/** Provider info from GET /ais/providers */
export interface ProviderInfo {
  active_provider: string
  active_model: string
  tiers: Record<string, { provider: string; model: string }>
  cache_stats?: { hits: number; misses: number; savings_pct: number }
  proxy?: { url: string; status: string }
}

/** Tool status from GET /ais/tools */
export interface ToolStatus {
  name: string
  status: 'online' | 'degraded' | 'offline'
  detail?: string
}

/** History run item */
export interface HistoryRun {
  id: string
  run_id: string
  title: string
  topic: string
  type: string
  source: 'platform' | 'cli'
  status: string
  current_stage?: string
  created_at: string
  updated_at?: string
  stage_results?: Record<string, unknown>
  simulation_id?: string
  upload_id?: string
  metadata?: Record<string, unknown>
}

/** Research idea from Stage 2 */
export interface ResearchIdea {
  id: string
  title: string
  hypothesis: string
  methodology?: string
  composite_score: number
  scores?: {
    interestingness: number
    feasibility: number
    novelty: number
    debate_support: number
  }
}

/** Paper draft from Stage 5 */
export interface PaperDraft {
  title: string
  sections: Array<{ heading: string; content: string }>
  citations: Array<{ id: string; title: string; doi?: string }>
  metadata: Record<string, unknown>
  review_overall?: number
}

/** Debate summary from GET /simulate/:id/summary */
export interface DebateSummary {
  simulation_id?: string
  topic?: string
  format?: string
  status?: string
  consensus?: {
    round?: number
    consensus_level?: number
    consensus_trend?: string
    top_option?: string | null
    options?: Array<{
      label: string
      confidence: number
      status?: string
      supporters?: number
      opposers?: number
    }>
    top_influencers?: Array<{ name: string; score: number }>
    disagreements?: number
    coalitions?: number
  } | null
  key_arguments: Array<{ agent: string; role?: string; round: number; type?: string; content: string }>
  analyst_feed?: Array<{ round: number; narrative: string; key_events?: string[] }>
  agent_count: number
  rounds_completed: number
  max_rounds?: number
  total_turns: number
  total_citations?: number
  top_contributor?: { name: string; turns: number } | null
  turn_types?: Record<string, number>
  started_at?: string
  completed_at?: string
}

/** AutoResearch status */
export interface AutoResearchStatus {
  queue_depth: number
  active_run?: string
  daemon_status: 'running' | 'idle' | 'stopped'
}

/** Paper Lab upload */
export interface PaperUpload {
  upload_id: string
  title: string
  language: string
  field?: string
  detected_field?: string
  status: string
  round_count?: number
  rounds_completed?: number
  review_scores?: number[]
  score_progression?: number[]
  initial_score?: number | null
  final_score?: number | null
  created_at: string
  updated_at?: string
  source_filename?: string
}

/** SSE event data */
export interface SSEEvent<T = unknown> {
  event?: string
  type?: string
  payload?: T
  data?: T
}

// ── Agent upgrade: LLM-Peer annotation schema ───────────────────────────

export type AnnotationKind = 'comment' | 'insert' | 'replace' | 'delete'
export type AnnotationSeverity = 'critical' | 'major' | 'minor' | 'nit'

export interface Annotation {
  annotation_id: string
  kind: AnnotationKind
  target_id: string
  span?: [number, number] | null
  target_region?: Record<string, unknown> | null
  original_text?: string
  replacement_text?: string
  comment: string
  severity: AnnotationSeverity
  reviewer_id?: string
  confidence?: number
  metadata?: Record<string, unknown>
}

// ── Awesome-LLM-KG typed triples ────────────────────────────────────────

export type TripleRelation =
  | 'supports'
  | 'contradicts'
  | 'extends'
  | 'grounded_in'
  | 'derived_from'
  | 'cites'
  | 'gap_for'

export interface Triple {
  triple_id: string
  subject_id: string
  relation: TripleRelation
  object_id: string
  confidence: number
  evidence_ids: string[]
  source?: string
  metadata?: Record<string, unknown>
}

// ── AgentReview 3D reviewer persona ─────────────────────────────────────

export interface ReviewerPersona3D {
  persona_id: string
  name: string
  archetype: string
  commitment: number
  intention: number
  knowledgeability: number
  strictness: number
  focus_areas: string[]
}

export interface ReviewPhasePayload {
  independent: {
    results: unknown[]
    personas: Record<string, ReviewerPersona3D>
  }
  rebuttal: { text: string; present: boolean }
  discussion: {
    conflicts: unknown
    authority_bias: boolean
    anchor_reviewer: string | null
  }
  meta: { meta_score: number; weighting: string }
  decision: {
    verdict: 'accept' | 'weak_accept' | 'borderline' | 'weak_reject' | 'reject'
    meta_score: number
    authority_bias: boolean
  }
}

export interface FivePhaseReviewResult {
  round: Record<string, unknown>
  phases: ReviewPhasePayload
}

// Grant Hunt — shared types (mirror of backend dataclasses)

export interface GrantProfile {
  profile_id: string
  name: string
  markdown: string
  parsed_fields: Record<string, unknown>
  created_at: string
  updated_at: string
  summary?: string
}

export interface GrantSource {
  source_id: string
  name: string
  kind: 'fundsforngos' | 'grants_gov' | 'cordis' | 'horizon_europe' | 'generic'
  listing_url: string
  enabled: boolean
  last_crawled_at: string | null
  metadata: Record<string, unknown>
}

export interface GrantOpportunity {
  opportunity_id: string
  source_id: string
  title: string
  funder: string
  amount: string
  currency: string
  deadline: string
  eligibility: string[]
  themes: string[]
  regions: string[]
  applicant_types: string[]
  summary: string
  source_url: string
  call_url: string
  raw_text: string
  fetched_at: string
  extra: Record<string, unknown>
}

export interface MatchResult {
  opportunity_id: string
  profile_id: string
  fit_score: number
  fit_reasons: string[]
  red_flags: string[]
  suggested_angle: string
  computed_at: string
  model_used: string
}

export interface MatchedOpportunity {
  match: MatchResult
  opportunity: GrantOpportunity
}

export interface ProposalSection {
  key: string
  title: string
  word_limit: number
  guidance: string
  content: string
  status: 'pending' | 'drafting' | 'drafted' | 'approved'
  revision_notes: string[]
}

export interface ProposalPlan {
  sections: ProposalSection[]
  required_attachments: string[]
  narrative_hooks: string[]
  risks: string[]
  timeline: Array<{ phase?: string; milestone?: string }>
  budget_skeleton: Array<{ category?: string; amount_pct?: number; notes?: string }>
  notes: string
}

export interface SubmissionKit {
  cover_letter: string
  sections_markdown: string
  checklist: Array<{ item: string; status: string; notes?: string }>
  instructions: string
  budget_table: Array<Record<string, unknown>>
  assembled_at: string
}

export interface ProposalDraft {
  proposal_id: string
  opportunity_id: string
  profile_id: string
  status: 'planning' | 'drafting' | 'packaging' | 'ready'
  plan: ProposalPlan
  submission_kit: SubmissionKit | null
  created_at: string
  updated_at: string
  model_used: string
}

export interface DiscoveryResult {
  opportunity_count: number
  visited: number
  candidates: number
  errors: string[]
  opportunity_ids?: string[]
  source_id?: string
}

export interface DiscoverAllResponse {
  sources: string[]
  results: DiscoveryResult[]
  total_opportunities: number
}

export type FeedbackEventType =
  | 'match_accepted'
  | 'match_rejected'
  | 'opportunity_shortlisted'
  | 'opportunity_dismissed'
  | 'plan_edited'
  | 'section_edited'
  | 'section_approved'
  | 'section_regenerated'

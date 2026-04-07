// Grant Hunt — typed API client
//
// All endpoints live under /api/research/grants (inherits API-key auth
// from the platform middleware).

import { apiGet, apiPost, LONG_TIMEOUT } from './client'
import service from './client'
import type {
  DiscoverAllResponse,
  DiscoveryResult,
  FeedbackEventType,
  GrantAlert,
  GrantFilter,
  GrantOpportunity,
  GrantProfile,
  GrantSource,
  MatchResult,
  MatchedOpportunity,
  ProposalDraft,
} from '@/types/grants'

const BASE = '/api/research/grants'

// ── Profiles ─────────────────────────────────────────────────────────

export function getProfileTemplate(): Promise<{ template: string }> {
  return apiGet(`${BASE}/profiles/template`)
}

export function listProfiles(): Promise<GrantProfile[]> {
  return apiGet(`${BASE}/profiles`)
}

export function getProfile(profileId: string): Promise<GrantProfile> {
  return apiGet(`${BASE}/profiles/${profileId}`)
}

export function createProfile(data: { name: string; markdown: string }): Promise<GrantProfile> {
  return apiPost(`${BASE}/profiles`, data)
}

export async function updateProfile(
  profileId: string,
  data: { name?: string; markdown?: string },
): Promise<GrantProfile> {
  const res = await service.put(`${BASE}/profiles/${profileId}`, data)
  return res.data.data as GrantProfile
}

export async function deleteProfile(profileId: string): Promise<void> {
  await service.delete(`${BASE}/profiles/${profileId}`)
}

// ── Sources ──────────────────────────────────────────────────────────

export function listSources(): Promise<GrantSource[]> {
  return apiGet(`${BASE}/sources`)
}

export function createSource(data: Partial<GrantSource>): Promise<GrantSource> {
  return apiPost(`${BASE}/sources`, data)
}

export async function updateSource(
  sourceId: string,
  data: Partial<GrantSource>,
): Promise<GrantSource> {
  const res = await service.put(`${BASE}/sources/${sourceId}`, data)
  return res.data.data as GrantSource
}

export async function deleteSource(sourceId: string): Promise<void> {
  await service.delete(`${BASE}/sources/${sourceId}`)
}

// ── Discovery ────────────────────────────────────────────────────────

export function discoverAll(options: { max_pages?: number; model?: string } = {}): Promise<DiscoverAllResponse> {
  return apiPost(`${BASE}/discover`, options, { timeout: LONG_TIMEOUT })
}

export function discoverSource(
  sourceId: string,
  options: { max_pages?: number; model?: string } = {},
): Promise<DiscoveryResult> {
  return apiPost(`${BASE}/discover/${sourceId}`, options, { timeout: LONG_TIMEOUT })
}

export function listOpportunities(
  params: { source_id?: string; limit?: number } & GrantFilter = {},
): Promise<GrantOpportunity[]> {
  // Backend list_opportunities uses singular filter params (one value per
  // field). The client takes arrays for ergonomics and picks the first
  // entry; callers needing AND-semantics across multiple values should
  // fetch with the unfiltered superset and refine client-side.
  const query = new URLSearchParams()
  if (params.source_id) query.set('source_id', params.source_id)
  if (params.limit) query.set('limit', String(params.limit))
  if (params.search) query.set('search', params.search)
  if (params.deadline_state) query.set('deadline_state', params.deadline_state)
  const firstTheme = params.theme_tags?.[0]
  if (firstTheme) query.set('theme_tag', firstTheme)
  const firstRegion = params.region_codes?.[0]
  if (firstRegion) query.set('region_code', firstRegion)
  const firstScope = params.applicant_scopes?.[0]
  if (firstScope) query.set('applicant_scope', firstScope)
  const qs = query.toString()
  return apiGet(`${BASE}/opportunities${qs ? `?${qs}` : ''}`)
}

export function listTimelineOpportunities(params: {
  regions?: string[]
  deadline_state?: string
  limit?: number
} = {}): Promise<{
  count: number
  regions: string[]
  opportunities: GrantOpportunity[]
}> {
  const query = new URLSearchParams()
  if (params.regions?.length) query.set('regions', params.regions.join(','))
  if (params.deadline_state) query.set('deadline_state', params.deadline_state)
  if (params.limit) query.set('limit', String(params.limit))
  const qs = query.toString()
  return apiGet(`${BASE}/timeline${qs ? `?${qs}` : ''}`)
}

export function getOpportunity(opportunityId: string): Promise<GrantOpportunity> {
  return apiGet(`${BASE}/opportunities/${opportunityId}`)
}

// ── Matching ─────────────────────────────────────────────────────────

export function matchAll(data: {
  profile_id: string
  model?: string
  limit?: number
}): Promise<{ count: number; results: MatchedOpportunity[] }> {
  return apiPost(`${BASE}/match`, data, { timeout: LONG_TIMEOUT })
}

export function matchOne(
  opportunityId: string,
  data: { profile_id: string; model?: string },
): Promise<MatchResult> {
  return apiPost(`${BASE}/match/${opportunityId}`, data, { timeout: LONG_TIMEOUT })
}

// ── Proposals ────────────────────────────────────────────────────────

export function createProposal(data: {
  profile_id: string
  opportunity_id: string
  model?: string
}): Promise<ProposalDraft> {
  return apiPost(`${BASE}/proposals`, data)
}

export function listProposals(profileId?: string): Promise<ProposalDraft[]> {
  const qs = profileId ? `?profile_id=${encodeURIComponent(profileId)}` : ''
  return apiGet(`${BASE}/proposals${qs}`)
}

export function getProposal(proposalId: string): Promise<ProposalDraft> {
  return apiGet(`${BASE}/proposals/${proposalId}`)
}

export function planProposal(proposalId: string, model?: string): Promise<ProposalDraft> {
  return apiPost(`${BASE}/proposals/${proposalId}/plan`, { model }, { timeout: LONG_TIMEOUT })
}

export function draftProposal(
  proposalId: string,
  options: { model?: string; force?: boolean } = {},
): Promise<ProposalDraft> {
  return apiPost(`${BASE}/proposals/${proposalId}/draft`, options, { timeout: LONG_TIMEOUT })
}

export function draftSection(
  proposalId: string,
  sectionKey: string,
  options: { model?: string; instructions?: string } = {},
): Promise<{ section: unknown; proposal: ProposalDraft }> {
  return apiPost(
    `${BASE}/proposals/${proposalId}/sections/${encodeURIComponent(sectionKey)}`,
    options,
    { timeout: LONG_TIMEOUT },
  )
}

export async function editSection(
  proposalId: string,
  sectionKey: string,
  content: string,
): Promise<ProposalDraft> {
  const res = await service.put(
    `${BASE}/proposals/${proposalId}/sections/${encodeURIComponent(sectionKey)}`,
    { content },
  )
  return res.data.data as ProposalDraft
}

export function packageProposal(proposalId: string, model?: string): Promise<ProposalDraft> {
  return apiPost(`${BASE}/proposals/${proposalId}/package`, { model }, { timeout: LONG_TIMEOUT })
}

// ── Feedback ─────────────────────────────────────────────────────────

export function recordFeedback(data: {
  profile_id: string
  event_type: FeedbackEventType
  target_id: string
  payload?: Record<string, unknown>
}): Promise<unknown> {
  return apiPost(`${BASE}/feedback`, data)
}

// ── Alerts ────────────────────────────────────────────────────────────

export interface AlertListResponse {
  count: number
  alerts: GrantAlert[]
}

export function listAlerts(
  profileId: string,
  opts: { unseenOnly?: boolean; limit?: number } = {},
): Promise<AlertListResponse> {
  const q = new URLSearchParams({ profile_id: profileId })
  q.set('unseen_only', opts.unseenOnly === false ? '0' : '1')
  if (opts.limit) q.set('limit', String(opts.limit))
  return apiGet(`${BASE}/alerts?${q.toString()}`)
}

export function markAlertSeen(alertId: string): Promise<{ alert_id: string; seen: boolean }> {
  return apiPost(`${BASE}/alerts/${alertId}/seen`, {})
}

export function markAllAlertsSeen(profileId: string): Promise<{ marked: number }> {
  return apiPost(`${BASE}/alerts/mark-all-seen`, { profile_id: profileId })
}

export function evaluateAlerts(data: {
  profile_id: string
  threshold?: number
  run_matcher?: boolean
  model?: string
}): Promise<{ count: number; alerts: GrantAlert[] }> {
  return apiPost(`${BASE}/alerts/evaluate`, data, { timeout: LONG_TIMEOUT })
}

// ── Watchlist ─────────────────────────────────────────────────────────

export function getWatchlist(profileId: string): Promise<{ opportunity_ids: string[] }> {
  return apiGet(`${BASE}/watchlist?profile_id=${encodeURIComponent(profileId)}`)
}

// ── Scheduler ─────────────────────────────────────────────────────────

export interface SchedulerStatus {
  running: boolean
  inflight: string[]
  failure_counts: Record<string, number>
  tick_seconds: number
  max_concurrent: number
}

export function getSchedulerStatus(): Promise<SchedulerStatus> {
  return apiGet(`${BASE}/scheduler/status`)
}

export function startScheduler(): Promise<SchedulerStatus> {
  return apiPost(`${BASE}/scheduler/start`, {})
}

export function triggerScheduler(sourceId: string): Promise<{ source_id: string; triggered: boolean }> {
  return apiPost(`${BASE}/scheduler/trigger/${encodeURIComponent(sourceId)}`, {}, { timeout: LONG_TIMEOUT })
}

export interface CrawlRun {
  run_id: string
  source_id: string
  started_at: string
  completed_at: string | null
  new_count: number
  updated_count: number
  errors: string[]
  status: string
}

export function listSchedulerRuns(params: { source_id?: string; limit?: number } = {}): Promise<{
  count: number
  runs: CrawlRun[]
}> {
  const q = new URLSearchParams()
  if (params.source_id) q.set('source_id', params.source_id)
  if (params.limit) q.set('limit', String(params.limit))
  const qs = q.toString()
  return apiGet(`${BASE}/scheduler/runs${qs ? `?${qs}` : ''}`)
}

// ── Export ─────────────────────────────────────────────────────────────

export async function exportOpportunities(params: GrantFilter): Promise<Blob> {
  const query = new URLSearchParams()
  if (params.search) query.set('search', params.search)
  if (params.deadline_state) query.set('deadline_state', params.deadline_state)
  if (params.theme_tags?.length) query.set('theme_tags', params.theme_tags.join(','))
  if (params.region_codes?.length) query.set('region_codes', params.region_codes.join(','))
  if (params.applicant_scopes?.length) query.set('applicant_scopes', params.applicant_scopes.join(','))
  const qs = query.toString()
  const res = await service.get(`${BASE}/opportunities/export${qs ? `?${qs}` : ''}`, {
    responseType: 'blob',
  })
  return res.data as Blob
}

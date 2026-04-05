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

export function listOpportunities(params: { source_id?: string; limit?: number } = {}): Promise<GrantOpportunity[]> {
  const query = new URLSearchParams()
  if (params.source_id) query.set('source_id', params.source_id)
  if (params.limit) query.set('limit', String(params.limit))
  const qs = query.toString()
  return apiGet(`${BASE}/opportunities${qs ? `?${qs}` : ''}`)
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

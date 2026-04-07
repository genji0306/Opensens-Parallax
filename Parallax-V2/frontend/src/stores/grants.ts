import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as api from '@/api/grants'
import type {
  FeedbackEventType,
  GrantAlert,
  GrantFilter,
  GrantOpportunity,
  GrantProfile,
  GrantSource,
  MatchedOpportunity,
  ProposalDraft,
} from '@/types/grants'

type Stage = 'discover' | 'match' | 'plan' | 'draft' | 'package'

export const STAGE_ORDER: Stage[] = ['discover', 'match', 'plan', 'draft', 'package']

export const useGrantsStore = defineStore('grants', () => {
  // ── State ──────────────────────────────────────────────────────────
  const profiles = ref<GrantProfile[]>([])
  const activeProfileId = ref<string | null>(null)
  const sources = ref<GrantSource[]>([])
  const opportunities = ref<GrantOpportunity[]>([])
  const matches = ref<MatchedOpportunity[]>([])
  const proposals = ref<ProposalDraft[]>([])
  const activeProposalId = ref<string | null>(null)

  const loading = ref<Record<string, boolean>>({})
  const errors = ref<Record<string, string | null>>({})
  const discoveryStatus = ref<{
    running: boolean
    lastCount: number
    lastRun: string | null
  }>({ running: false, lastCount: 0, lastRun: null })

  const alerts = ref<GrantAlert[]>([])
  const watchlistIds = ref<string[]>([])
  const activeFilter = ref<GrantFilter>({})

  // ── Getters ────────────────────────────────────────────────────────
  const activeProfile = computed<GrantProfile | null>(() =>
    profiles.value.find(p => p.profile_id === activeProfileId.value) ?? null,
  )

  const activeProposal = computed<ProposalDraft | null>(() =>
    proposals.value.find(p => p.proposal_id === activeProposalId.value) ?? null,
  )

  const enabledSources = computed(() => sources.value.filter(s => s.enabled))

  const topMatches = computed(() => matches.value.slice(0, 50))

  const unseenAlertCount = computed(() => alerts.value.filter(a => !a.seen_at).length)

  // ── Helpers ────────────────────────────────────────────────────────
  function setLoading(key: string, value: boolean): void {
    loading.value = { ...loading.value, [key]: value }
  }
  function setError(key: string, value: string | null): void {
    errors.value = { ...errors.value, [key]: value }
  }
  async function run<T>(key: string, fn: () => Promise<T>): Promise<T | null> {
    setLoading(key, true)
    setError(key, null)
    try {
      return await fn()
    } catch (e) {
      setError(key, (e as Error).message ?? 'Request failed')
      return null
    } finally {
      setLoading(key, false)
    }
  }

  // ── Profiles ───────────────────────────────────────────────────────
  async function loadProfiles(): Promise<void> {
    const list = await run('profiles', () => api.listProfiles())
    if (list) {
      profiles.value = list
      const first = list[0]
      if (!activeProfileId.value && first) {
        activeProfileId.value = first.profile_id
      }
    }
  }

  async function createProfile(data: { name: string; markdown: string }): Promise<GrantProfile | null> {
    const profile = await run('profiles', () => api.createProfile(data))
    if (profile) {
      profiles.value = [profile, ...profiles.value]
      activeProfileId.value = profile.profile_id
    }
    return profile
  }

  async function updateProfile(
    profileId: string,
    data: { name?: string; markdown?: string },
  ): Promise<void> {
    const updated = await run('profiles', () => api.updateProfile(profileId, data))
    if (updated) {
      profiles.value = profiles.value.map(p => (p.profile_id === profileId ? updated : p))
    }
  }

  async function removeProfile(profileId: string): Promise<void> {
    await run('profiles', () => api.deleteProfile(profileId))
    profiles.value = profiles.value.filter(p => p.profile_id !== profileId)
    if (activeProfileId.value === profileId) {
      activeProfileId.value = profiles.value[0]?.profile_id ?? null
    }
  }

  function selectProfile(profileId: string): void {
    activeProfileId.value = profileId
  }

  // ── Sources ────────────────────────────────────────────────────────
  async function loadSources(): Promise<void> {
    const list = await run('sources', () => api.listSources())
    if (list) sources.value = list
  }

  async function toggleSource(sourceId: string, enabled: boolean): Promise<void> {
    const updated = await run('sources', () => api.updateSource(sourceId, { enabled }))
    if (updated) {
      sources.value = sources.value.map(s => (s.source_id === sourceId ? updated : s))
    }
  }

  async function addSource(data: Partial<GrantSource>): Promise<void> {
    const source = await run('sources', () => api.createSource(data))
    if (source) sources.value = [...sources.value, source]
  }

  async function removeSource(sourceId: string): Promise<void> {
    await run('sources', () => api.deleteSource(sourceId))
    sources.value = sources.value.filter(s => s.source_id !== sourceId)
  }

  // ── Discovery ──────────────────────────────────────────────────────
  async function runDiscovery(options: { max_pages?: number; model?: string } = {}): Promise<void> {
    discoveryStatus.value = { running: true, lastCount: 0, lastRun: null }
    const result = await run('discover', () => api.discoverAll(options))
    if (result) {
      discoveryStatus.value = {
        running: false,
        lastCount: result.total_opportunities,
        lastRun: new Date().toISOString(),
      }
      await loadOpportunities()
    } else {
      discoveryStatus.value = { ...discoveryStatus.value, running: false }
    }
  }

  async function loadOpportunities(sourceId?: string): Promise<void> {
    const list = await run('opportunities', () => api.listOpportunities({ source_id: sourceId }))
    if (list) opportunities.value = list
  }

  // ── Matching ───────────────────────────────────────────────────────
  async function runMatch(): Promise<void> {
    if (!activeProfileId.value) return
    const payload = { profile_id: activeProfileId.value }
    const res = await run('match', () => api.matchAll(payload))
    if (res) matches.value = res.results
  }

  // ── Proposals ──────────────────────────────────────────────────────
  async function loadProposals(): Promise<void> {
    const list = await run('proposals', () =>
      api.listProposals(activeProfileId.value ?? undefined),
    )
    if (list) proposals.value = list
  }

  async function startProposal(opportunityId: string): Promise<ProposalDraft | null> {
    if (!activeProfileId.value) return null
    const proposal = await run('proposals', () =>
      api.createProposal({
        profile_id: activeProfileId.value!,
        opportunity_id: opportunityId,
      }),
    )
    if (proposal) {
      proposals.value = [proposal, ...proposals.value]
      activeProposalId.value = proposal.proposal_id
    }
    return proposal
  }

  async function runPlanner(proposalId: string): Promise<void> {
    const updated = await run('plan', () => api.planProposal(proposalId))
    if (updated) replaceProposal(updated)
  }

  async function runDrafter(proposalId: string, force = false): Promise<void> {
    const updated = await run('draft', () => api.draftProposal(proposalId, { force }))
    if (updated) replaceProposal(updated)
  }

  async function regenerateSection(
    proposalId: string,
    sectionKey: string,
    instructions?: string,
  ): Promise<void> {
    const res = await run('section', () =>
      api.draftSection(proposalId, sectionKey, { instructions }),
    )
    if (res) replaceProposal(res.proposal)
  }

  async function editSectionContent(
    proposalId: string,
    sectionKey: string,
    content: string,
  ): Promise<void> {
    const updated = await run('section', () => api.editSection(proposalId, sectionKey, content))
    if (updated) replaceProposal(updated)
  }

  async function runPackager(proposalId: string): Promise<void> {
    const updated = await run('package', () => api.packageProposal(proposalId))
    if (updated) replaceProposal(updated)
  }

  function replaceProposal(updated: ProposalDraft): void {
    proposals.value = proposals.value.map(p =>
      p.proposal_id === updated.proposal_id ? updated : p,
    )
  }

  function selectProposal(proposalId: string): void {
    activeProposalId.value = proposalId
  }

  // ── Feedback ───────────────────────────────────────────────────────
  async function recordFeedback(event: {
    event_type: FeedbackEventType
    target_id: string
    payload?: Record<string, unknown>
  }): Promise<void> {
    if (!activeProfileId.value) return
    await api.recordFeedback({
      profile_id: activeProfileId.value,
      ...event,
    })
  }

  // ── Alerts ─────────────────────────────────────────────────────────
  async function fetchAlerts(profileId: string, unseenOnly = false): Promise<void> {
    const res = await run('alerts', () => api.listAlerts(profileId, { unseenOnly }))
    if (res) alerts.value = res.alerts ?? []
  }

  async function markAlertSeen(alertId: string): Promise<void> {
    await run('alerts', () => api.markAlertSeen(alertId))
    alerts.value = alerts.value.map(a =>
      a.alert_id === alertId ? { ...a, seen_at: new Date().toISOString() } : a,
    )
  }

  async function markAllAlertsSeen(): Promise<void> {
    const profileId = activeProfileId.value
    if (!profileId) return
    await run('alerts', () => api.markAllAlertsSeen(profileId))
    alerts.value = alerts.value.map(a => ({
      ...a,
      seen_at: a.seen_at ?? new Date().toISOString(),
    }))
  }

  async function evaluateAlerts(runMatcher = false): Promise<void> {
    const profileId = activeProfileId.value
    if (!profileId) return
    await run('alerts', () =>
      api.evaluateAlerts({ profile_id: profileId, run_matcher: runMatcher }),
    )
    await fetchAlerts(profileId)
  }

  // ── Watchlist ──────────────────────────────────────────────────────
  async function fetchWatchlist(profileId: string): Promise<void> {
    const res = await run('watchlist', () => api.getWatchlist(profileId))
    if (res) watchlistIds.value = res.opportunity_ids ?? []
  }

  // ── Filter ─────────────────────────────────────────────────────────
  function setFilter(filter: GrantFilter): void {
    activeFilter.value = { ...filter }
  }

  function clearFilter(): void {
    activeFilter.value = {}
  }

  // ── Bootstrap ──────────────────────────────────────────────────────
  async function bootstrap(): Promise<void> {
    await Promise.all([loadProfiles(), loadSources(), loadOpportunities()])
  }

  return {
    // state
    profiles,
    activeProfileId,
    sources,
    opportunities,
    matches,
    proposals,
    activeProposalId,
    loading,
    errors,
    discoveryStatus,
    alerts,
    watchlistIds,
    activeFilter,
    // getters
    activeProfile,
    activeProposal,
    enabledSources,
    topMatches,
    unseenAlertCount,
    // actions
    loadProfiles,
    createProfile,
    updateProfile,
    removeProfile,
    selectProfile,
    loadSources,
    toggleSource,
    addSource,
    removeSource,
    runDiscovery,
    loadOpportunities,
    runMatch,
    loadProposals,
    startProposal,
    runPlanner,
    runDrafter,
    regenerateSection,
    editSectionContent,
    runPackager,
    selectProposal,
    recordFeedback,
    fetchAlerts,
    markAlertSeen,
    markAllAlertsSeen,
    evaluateAlerts,
    fetchWatchlist,
    setFilter,
    clearFilter,
    bootstrap,
  }
})

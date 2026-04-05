/**
 * Grants store unit tests
 * Covers profile selection, source toggling, discovery lifecycle,
 * proposal bookkeeping, and feedback events.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// Mock the API module before the store imports it
vi.mock('@/api/grants', () => ({
  listProfiles: vi.fn(async () => [
    {
      profile_id: 'prof-1',
      name: 'Acme Labs',
      markdown: '# Organization\n- name: Acme\n',
      parsed_fields: { name: 'Acme' },
      created_at: '2026-04-01',
      updated_at: '2026-04-01',
    },
  ]),
  listSources: vi.fn(async () => [
    {
      source_id: 'src-1',
      name: 'FundsforNGOs',
      kind: 'fundsforngos',
      listing_url: 'https://example.org',
      enabled: true,
      last_crawled_at: null,
      metadata: {},
    },
  ]),
  listOpportunities: vi.fn(async () => []),
  createProfile: vi.fn(async (data: { name: string; markdown: string }) => ({
    profile_id: 'prof-2',
    name: data.name,
    markdown: data.markdown,
    parsed_fields: {},
    created_at: '2026-04-01',
    updated_at: '2026-04-01',
  })),
  updateSource: vi.fn(async (id: string, data: Record<string, unknown>) => ({
    source_id: id,
    name: 'FundsforNGOs',
    kind: 'fundsforngos',
    listing_url: 'https://example.org',
    enabled: Boolean(data.enabled),
    last_crawled_at: null,
    metadata: {},
  })),
  discoverAll: vi.fn(async () => ({
    sources: ['src-1'],
    results: [{ opportunity_count: 3, visited: 5, candidates: 5, errors: [] }],
    total_opportunities: 3,
  })),
  matchAll: vi.fn(async () => ({
    count: 1,
    results: [
      {
        match: {
          opportunity_id: 'opp-1',
          profile_id: 'prof-1',
          fit_score: 85,
          fit_reasons: ['theme overlap'],
          red_flags: [],
          suggested_angle: 'Emphasize pilot data',
          computed_at: '2026-04-01',
          model_used: 'mock',
        },
        opportunity: {
          opportunity_id: 'opp-1',
          source_id: 'src-1',
          title: 'Innovation Call',
          funder: 'ExampleFunder',
          amount: '',
          currency: '',
          deadline: '',
          eligibility: [],
          themes: ['innovation'],
          regions: [],
          applicant_types: [],
          summary: '',
          source_url: '',
          call_url: '',
          raw_text: '',
          fetched_at: '2026-04-01',
          extra: {},
        },
      },
    ],
  })),
  recordFeedback: vi.fn(async () => ({ event_id: 'fb-1' })),
  createProposal: vi.fn(async (data: { profile_id: string; opportunity_id: string }) => ({
    proposal_id: 'prop-1',
    opportunity_id: data.opportunity_id,
    profile_id: data.profile_id,
    status: 'planning',
    plan: {
      sections: [],
      required_attachments: [],
      narrative_hooks: [],
      risks: [],
      timeline: [],
      budget_skeleton: [],
      notes: '',
    },
    submission_kit: null,
    created_at: '2026-04-01',
    updated_at: '2026-04-01',
    model_used: '',
  })),
  listProposals: vi.fn(async () => []),
}))

describe('useGrantsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('bootstraps profiles and auto-selects the first one', async () => {
    const { useGrantsStore } = await import('@/stores/grants')
    const store = useGrantsStore()

    await store.bootstrap()

    expect(store.profiles.length).toBe(1)
    expect(store.activeProfileId).toBe('prof-1')
    expect(store.activeProfile?.name).toBe('Acme Labs')
    expect(store.enabledSources.length).toBe(1)
  })

  it('runs discovery and updates status + KPI counts', async () => {
    const { useGrantsStore } = await import('@/stores/grants')
    const store = useGrantsStore()
    await store.bootstrap()

    await store.runDiscovery({ max_pages: 10 })

    expect(store.discoveryStatus.running).toBe(false)
    expect(store.discoveryStatus.lastCount).toBe(3)
    expect(store.discoveryStatus.lastRun).not.toBeNull()
  })

  it('scores matches against active profile and orders them', async () => {
    const { useGrantsStore } = await import('@/stores/grants')
    const store = useGrantsStore()
    await store.bootstrap()

    await store.runMatch()
    expect(store.matches.length).toBe(1)
    expect(store.matches[0]!.match.fit_score).toBe(85)
    expect(store.topMatches.length).toBeLessThanOrEqual(50)
  })

  it('starts a proposal when an opportunity is accepted', async () => {
    const { useGrantsStore } = await import('@/stores/grants')
    const store = useGrantsStore()
    await store.bootstrap()

    const proposal = await store.startProposal('opp-1')
    expect(proposal).not.toBeNull()
    expect(store.proposals.length).toBe(1)
    expect(store.activeProposalId).toBe('prop-1')
  })

  it('toggles a source enabled/disabled', async () => {
    const { useGrantsStore } = await import('@/stores/grants')
    const store = useGrantsStore()
    await store.bootstrap()

    await store.toggleSource('src-1', false)
    const src = store.sources.find(s => s.source_id === 'src-1')
    expect(src?.enabled).toBe(false)
  })

  it('records feedback without requiring an active profile to be set twice', async () => {
    const { useGrantsStore } = await import('@/stores/grants')
    const api = await import('@/api/grants')
    const store = useGrantsStore()
    await store.bootstrap()

    await store.recordFeedback({
      event_type: 'opportunity_shortlisted',
      target_id: 'opp-1',
      payload: { fit_score: 85 },
    })

    expect(api.recordFeedback).toHaveBeenCalledWith(
      expect.objectContaining({
        profile_id: 'prof-1',
        event_type: 'opportunity_shortlisted',
        target_id: 'opp-1',
      }),
    )
  })
})

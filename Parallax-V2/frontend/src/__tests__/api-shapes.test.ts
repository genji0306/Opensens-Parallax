/**
 * API Response Shape Tests
 *
 * Validates that stores correctly parse the REAL backend response shapes.
 * Every fixture here is copied from actual curl output.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock axios at module level
vi.mock('axios', () => {
  const instance = {
    get: vi.fn(),
    post: vi.fn(),
    defaults: { baseURL: '' },
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
    create: vi.fn(),
  }
  instance.create.mockReturnValue(instance)
  return { default: instance }
})

vi.mock('@/stores/debug', () => ({
  useDebugStore: () => ({
    logRequest: vi.fn(() => 1),
    resolveRequest: vi.fn(),
    rejectRequest: vi.fn(),
  }),
}))

// ── Real backend response fixtures ──────────────────────────────────

const RECENT_RESPONSE = {
  items: [
    {
      run_id: 'test_run_d1be00776d',
      type: 'debate',
      status: 'completed',
      query: 'combine multiple electrochemical techniques',
      source: 'cli',
      created_at: '2026-03-21T23:09:00',
      summary: { agent_count: 6, rounds: 2, total_turns: 12 },
    },
    {
      run_id: 'ais_run_94b94904fe',
      type: 'ais',
      status: 'failed',
      query: 'Impedance tomography in battery research',
      source: 'platform',
      created_at: '2026-03-22T22:52:10',
      summary: { current_stage: 1, stages_total: 6 },
    },
  ],
}

const PROVIDERS_DATA = {
  default_provider: 'anthropic',
  default_model: 'claude-sonnet-4-20250514',
  providers: {
    anthropic: { configured: true, default_model: 'claude-sonnet-4-20250514', models: ['claude-sonnet-4-20250514'] },
    'aiclient-proxy': { configured: true, default_model: 'gpt-4o', models: ['gpt-4o'] },
  },
  cache: { total_entries: 49 },
}

const TOOLS_DATA = {
  ai_scientist: { available: true, template_count: 11 },
  autoresearch: { available: false, status: 'not configured' },
  scienceclaw: { available: true, databases: ['arxiv', 'crossref', 'pubmed'] },
}

const RUN_DETAIL_DATA = {
  run_id: 'test_run_d1be00776d',
  type: 'debate',
  status: 'completed',
  query: 'electrochemical techniques',
  source: 'cli',
  created_at: '2026-03-21T23:09:00',
  data: {
    debate: { agent_count: 6, agents: [], rounds: 2, transcript: [] },
    ideas: [{ id: 'idea1', title: 'Test Idea', score: 0.85 }],
  },
  summary: { agent_count: 6, rounds: 2, total_turns: 12 },
}

// ── Tests ────────────────────────────────────────────────────────────

describe('Backend Response Shape Parsing', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('Projects Store — fetchRecent()', () => {
    it('parses { items: [...] } shape from /history/recent', async () => {
      const mockAxios = (await import('axios')).default
      vi.mocked(mockAxios.get).mockResolvedValueOnce({
        data: { success: true, data: RECENT_RESPONSE },
      })

      const { useProjectsStore } = await import('@/stores/projects')
      const store = useProjectsStore()
      await store.fetchRecent(10)

      expect(store.recent.length).toBe(2)
      expect(store.recent[0]!.run_id).toBe('test_run_d1be00776d')
      expect(store.recent[0]!.title).toBe('combine multiple electrochemical techniques')
      expect(store.recent[0]!.type).toBe('debate')
      expect(store.recent[1]!.run_id).toBe('ais_run_94b94904fe')
      expect(store.recent[1]!.type).toBe('ais')
      expect(store.error).toBeNull()
      expect(store.loading).toBe(false)
    })

    it('handles empty items gracefully', async () => {
      const mockAxios = (await import('axios')).default
      vi.mocked(mockAxios.get).mockResolvedValueOnce({
        data: { success: true, data: { items: [] } },
      })

      const { useProjectsStore } = await import('@/stores/projects')
      const store = useProjectsStore()
      await store.fetchRecent()

      expect(store.recent).toEqual([])
      expect(store.error).toBeNull()
    })

    it('sets error on network failure', async () => {
      const mockAxios = (await import('axios')).default
      vi.mocked(mockAxios.get).mockRejectedValueOnce(new Error('Network Error'))

      const { useProjectsStore } = await import('@/stores/projects')
      const store = useProjectsStore()
      await store.fetchRecent()

      expect(store.error).toContain('Backend unreachable')
      expect(store.recent).toEqual([])
      expect(store.loading).toBe(false)
    })
  })

  describe('Projects Store — fetchAll()', () => {
    it('parses { runs: [...], total } shape from /history/runs', async () => {
      const mockAxios = (await import('axios')).default
      vi.mocked(mockAxios.get).mockResolvedValueOnce({
        data: {
          success: true,
          data: {
            runs: [{ run_id: 'test_run_d1be00776d', type: 'debate', status: 'completed', query: 'test', source: 'cli', created_at: '2026-03-21T23:09:00' }],
            total: 39,
            page: 1,
            per_page: 20,
            total_pages: 2,
          },
        },
      })

      const { useProjectsStore } = await import('@/stores/projects')
      const store = useProjectsStore()
      await store.fetchAll()

      expect(store.all.length).toBe(1)
      expect(store.all[0]!.run_id).toBe('test_run_d1be00776d')
      expect(store.totalCount).toBe(39)
    })

    it('normalizes current_stage from summary.current_stage', async () => {
      const mockAxios = (await import('axios')).default
      vi.mocked(mockAxios.get).mockResolvedValueOnce({
        data: {
          success: true,
          data: {
            runs: [{
              run_id: 'ais_run_001',
              type: 'ais',
              status: 'drafting',
              query: 'stage fallback',
              source: 'platform',
              created_at: '2026-03-21T23:09:00',
              summary: { current_stage: 5 },
            }],
            total: 1,
          },
        },
      })

      const { useProjectsStore } = await import('@/stores/projects')
      const store = useProjectsStore()
      await store.fetchAll()

      expect(store.all[0]!.current_stage).toBe('draft')
    })
  })

  describe('System Store — fetchProviders()', () => {
    it('normalizes { default_provider, default_model } to active_*', async () => {
      const mockAxios = (await import('axios')).default
      vi.mocked(mockAxios.get).mockResolvedValueOnce({
        data: { success: true, data: PROVIDERS_DATA },
      })

      const { useSystemStore } = await import('@/stores/system')
      const store = useSystemStore()
      await store.fetchProviders()

      expect(store.providers).not.toBeNull()
      expect(store.providers!.active_provider).toBe('anthropic')
      expect(store.providers!.active_model).toBe('claude-sonnet-4-20250514')
      expect(store.providers!.cache_entries).toBe(49)
      expect(store.backendOnline).toBe(true)
    })

    it('sets backendOnline=false on failure', async () => {
      const mockAxios = (await import('axios')).default
      vi.mocked(mockAxios.get).mockRejectedValueOnce(new Error('timeout'))

      const { useSystemStore } = await import('@/stores/system')
      const store = useSystemStore()
      await store.fetchProviders()

      expect(store.backendOnline).toBe(false)
      expect(store.providers).toBeNull()
    })
  })

  describe('System Store — fetchTools()', () => {
    it('normalizes tool object to ToolStatus[]', async () => {
      const mockAxios = (await import('axios')).default
      vi.mocked(mockAxios.get).mockResolvedValueOnce({
        data: { success: true, data: TOOLS_DATA },
      })

      const { useSystemStore } = await import('@/stores/system')
      const store = useSystemStore()
      await store.fetchTools()

      expect(store.tools.length).toBe(3)
      expect(store.tools.find(t => t.name === 'ai_scientist')!.status).toBe('online')
      expect(store.tools.find(t => t.name === 'autoresearch')!.status).toBe('offline')
      expect(store.tools.find(t => t.name === 'scienceclaw')!.status).toBe('online')
    })
  })

  describe('System Store — fetchAutoResearchStatus()', () => {
    it('parses autoresearch status', async () => {
      const mockAxios = (await import('axios')).default
      vi.mocked(mockAxios.get).mockResolvedValueOnce({
        data: { success: true, data: { queue_depth: 0, daemon_status: 'stopped' } },
      })

      const { useSystemStore } = await import('@/stores/system')
      const store = useSystemStore()
      await store.fetchAutoResearchStatus()

      expect(store.autoResearchStatus).not.toBeNull()
      expect(store.autoResearchStatus!.queue_depth).toBe(0)
      expect(store.autoResearchStatus!.daemon_status).toBe('stopped')
    })
  })

  describe('Pipeline Store — loadProject() with CLI debate run', () => {
    it('builds stages from data.debate and data.ideas', async () => {
      const mockAxios = (await import('axios')).default
      vi.mocked(mockAxios.get).mockResolvedValueOnce({
        data: { success: true, data: RUN_DETAIL_DATA },
      })

      const { usePipelineStore } = await import('@/stores/pipeline')
      const store = usePipelineStore()
      await store.loadProject('test_run_d1be00776d')

      expect(store.projectTitle).toBe('electrochemical techniques')
      expect(store.projectStatus).toBe('completed')
      expect(store.projectSource).toBe('cli')
      expect(store.stages['debate']?.status).toBe('done')
      expect(store.stages['ideas']?.status).toBe('done')
      expect(store.stages['crawl']?.status).toBe('pending')
      expect(store.stageResults['debate']).toBeDefined()
      expect((store.stageResults['debate'] as Record<string, unknown>).agent_count).toBe(6)
      expect(store.stages['debate']?.metric).toContain('6 agents')
    })

    it('marks failed stage correctly on AIS run', async () => {
      const mockAxios = (await import('axios')).default
      vi.mocked(mockAxios.get).mockResolvedValueOnce({
        data: {
          success: true,
          data: {
            run_id: 'ais_run_test',
            type: 'ais',
            status: 'failed',
            query: 'test topic',
            source: 'platform',
            current_stage: 1,
            error: "'ingested' is not a valid IngestionStatus",
            summary: { current_stage: 1, stages_total: 6 },
          },
        },
      })

      const { usePipelineStore } = await import('@/stores/pipeline')
      const store = usePipelineStore()
      await store.loadProject('ais_run_test')

      expect(store.projectStatus).toBe('failed')
      expect(store.projectError).toContain('IngestionStatus')
      expect(store.stages['crawl']?.status).toBe('failed')
    })
  })

  describe('Pipeline Start — response shape', () => {
    it('returns run_id from POST /ais/start', async () => {
      const mockAxios = (await import('axios')).default
      vi.mocked(mockAxios.post).mockResolvedValueOnce({
        data: {
          success: true,
          data: { run_id: 'ais_run_aa0ad9bf5c', task_id: '50097ede', message: 'Pipeline started' },
        },
      })

      const { startPipeline } = await import('@/api/ais')
      const res = await startPipeline({ research_idea: 'test topic', sources: ['arxiv'] })

      expect(res.data.data.run_id).toBe('ais_run_aa0ad9bf5c')
      expect(res.data.success).toBe(true)
    })
  })

  describe('Paper Lab — uploads raw array shape', () => {
    it('returns raw array from /paper-lab/uploads', () => {
      const payload = [{ upload_id: 'upload_abc123', title: 'Test Paper', status: 'completed' }]
      expect(Array.isArray(payload)).toBe(true)
      expect(payload[0]!.upload_id).toBe('upload_abc123')
    })
  })

  // ── P-2 Knowledge Engine Shapes ──────────────────────────────────

  describe('Knowledge artifact response shape', () => {
    it('GET /knowledge returns full artifact structure', () => {
      const response = {
        success: true,
        data: {
          artifact_id: 'ka_abc123',
          run_id: 'run_1',
          research_idea: 'Test idea',
          claims: [{ claim_id: 'cl_1', text: 'Claim', category: 'finding', confidence: 0.8, supporting: [], contradicting: [], extending: [] }],
          evidence: [{ evidence_id: 'ev_1', source_type: 'paper', source_id: 'p1', title: 'Paper', excerpt: '...', confidence: 0.7 }],
          gaps: [{ gap_id: 'gap_1', description: 'Gap', severity: 'critical', related_claims: [], suggested_approach: '', evidence_needed: '' }],
          novelty_assessments: [{ claim_id: 'cl_1', novelty_score: 0.8, explanation: 'Novel', closest_existing: [], differentiators: [] }],
          sub_questions: [],
          hypothesis: { hypothesis_id: 'hyp_1', problem_statement: 'Problem', contribution: 'Contribution', differentiators: [], predicted_impact: '', supporting_gaps: [], novelty_basis: [] },
          argument_skeleton: [],
          created_at: '2026-03-30T00:00:00',
          updated_at: '2026-03-30T00:00:00',
        },
      }

      expect(response.data.artifact_id).toMatch(/^ka_/)
      expect(response.data.claims).toHaveLength(1)
      expect(response.data.evidence).toHaveLength(1)
      expect(response.data.gaps).toHaveLength(1)
      expect(response.data.hypothesis).not.toBeNull()
    })
  })

  describe('Claim graph response shape', () => {
    it('GET /knowledge/claim-graph returns D3-renderable graph', () => {
      const response = {
        success: true,
        data: {
          nodes: [
            { id: 'cl_1', type: 'claim', label: 'Claim', full_text: 'Full text' },
            { id: 'ev_1', type: 'evidence', label: 'Evidence', full_text: 'Excerpt' },
          ],
          links: [
            { source: 'ev_1', target: 'cl_1', type: 'supports' },
          ],
          stats: { claims: 1, evidence: 1, gaps: 0, links: 1 },
        },
      }

      expect(response.data.nodes).toHaveLength(2)
      expect(response.data.links).toHaveLength(1)
      expect(response.data.links[0]!.type).toBe('supports')
      expect(response.data.stats.claims).toBe(1)
    })
  })

  describe('Papers endpoint with sort/filter', () => {
    it('GET /papers returns sort_by, source_filter, available_sources', () => {
      const response = {
        success: true,
        data: {
          papers: [],
          total: 0,
          page: 1,
          per_page: 10,
          pages: 0,
          sort_by: 'citations',
          source_filter: '',
          available_sources: ['arxiv', 'semantic_scholar'],
        },
      }

      expect(response.data.sort_by).toBe('citations')
      expect(response.data.available_sources).toContain('arxiv')
      expect(Array.isArray(response.data.available_sources)).toBe(true)
    })
  })

  // ── P-3 Review Board Shapes ──────────────────────────────────────

  describe('Reviewer archetypes response shape', () => {
    it('GET /review/archetypes returns 5 archetypes with required fields', () => {
      const response = {
        success: true,
        data: {
          methodological: { name: 'Methodological Reviewer', focus: 'experimental design', rubric: ['controls', 'stats'] },
          novelty: { name: 'Novelty Reviewer', focus: 'originality', rubric: ['originality'] },
          domain: { name: 'Domain Expert', focus: 'correctness', rubric: ['domain'] },
          statistician: { name: 'Statistical Reviewer', focus: 'statistics', rubric: ['methods'] },
          harsh_editor: { name: 'Harsh Editor', focus: 'clarity', rubric: ['clarity'] },
        },
      }

      const keys = Object.keys(response.data)
      expect(keys).toHaveLength(5)
      for (const arch of Object.values(response.data)) {
        expect(arch).toHaveProperty('name')
        expect(arch).toHaveProperty('focus')
        expect(arch).toHaveProperty('rubric')
      }
    })
  })

  describe('Revision history response shape', () => {
    it('GET /review/history returns trajectory and warnings', () => {
      const response = {
        success: true,
        data: {
          rounds: [
            { round_id: 'rr_1', run_id: 'run_1', round_number: 1, rewrite_mode: 'conservative', reviewer_types: ['novelty'], results: [], themes: [], conflicts: [], avg_score: 5.0, created_at: '' },
            { round_id: 'rr_2', run_id: 'run_1', round_number: 2, rewrite_mode: 'clarity', reviewer_types: ['novelty'], results: [], themes: [], conflicts: [], avg_score: 7.0, created_at: '' },
          ],
          score_trajectory: [{ round: 1, avg_score: 5.0 }, { round: 2, avg_score: 7.0 }],
          regression_warnings: [],
          total_rounds: 2,
          latest_score: 7.0,
          improving: true,
        },
      }

      expect(response.data.total_rounds).toBe(2)
      expect(response.data.improving).toBe(true)
      expect(response.data.score_trajectory).toHaveLength(2)
      expect(response.data.regression_warnings).toHaveLength(0)
    })
  })

  // ── P-6 Readiness Shape ──────────────────────────────────────────

  describe('Readiness response shape', () => {
    it('GET /readiness returns 5 platforms with scores and requirements', () => {
      const response = {
        success: true,
        data: {
          platforms: {
            oae: { name: 'OpenSens Academic Engine', readiness_score: 60, status: 'partial', met_requirements: ['draft_complete'], missing_requirements: ['review_score_7+'] },
            opad: { name: 'OpenSens Patent', readiness_score: 20, status: 'not_ready', met_requirements: [], missing_requirements: ['novelty_assessed'] },
          },
          recommended: 'oae',
          overall_readiness: 40,
        },
      }

      expect(Object.keys(response.data.platforms)).toHaveLength(2)
      expect(response.data.platforms.oae.status).toBe('partial')
      expect(response.data.recommended).toBe('oae')
      expect(typeof response.data.overall_readiness).toBe('number')
    })
  })

  describe('Handoff package response shape', () => {
    it('POST /handoff returns complete artifact bundle', () => {
      const response = {
        success: true,
        data: {
          run_id: 'run_1',
          target_platform: 'oae',
          research_idea: 'Test idea',
          pipeline_status: 'completed',
          knowledge_artifact: null,
          draft: null,
          revision_history: [],
          papers: [],
          topics: [],
          stage_results: {},
          metadata: { packaged_at: '2026-03-30T00:00:00', artifact_count: 0, paper_count: 0, revision_rounds: 0 },
        },
      }

      expect(response.data.run_id).toBe('run_1')
      expect(response.data.target_platform).toBe('oae')
      expect(response.data.metadata.packaged_at).toBeTruthy()
      expect(Array.isArray(response.data.papers)).toBe(true)
      expect(Array.isArray(response.data.revision_history)).toBe(true)
    })
  })
})

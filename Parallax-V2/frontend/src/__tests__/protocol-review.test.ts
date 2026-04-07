/**
 * Protocol Review Test Suite
 *
 * Comprehensive test of ALL API protocols across 6 clients:
 *   1. client.ts     — base HTTP, retry, typed helpers
 *   2. ais.ts        — AiS pipeline (30+ endpoints)
 *   3. research.ts   — ingestion, papers, topics, map, gaps
 *   4. simulation.ts — agents, simulations, chat, reports
 *   5. mirofish.ts   — debate frame, graph, scoreboard, stances
 *   6. paperLab.ts   — upload, review, rounds, gap-fill, export
 *
 * Every API function is exercised with realistic backend fixtures.
 * Tests validate: correct URL, HTTP method, params, response parsing.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// ── Mock Axios ────────────────────────────────────────────────────────────

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPatch = vi.fn()

vi.mock('axios', () => {
  const instance = {
    get: mockGet,
    post: mockPost,
    patch: mockPatch,
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

// ── Helpers ───────────────────────────────────────────────────────────────

function ok<T>(data: T) {
  return { data: { success: true, data } }
}

// ── Setup ─────────────────────────────────────────────────────────────────

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

// =========================================================================
// 1. AIS PIPELINE — ais.ts
// =========================================================================

describe('AIS Pipeline Protocol (ais.ts)', () => {
  describe('Pipeline Lifecycle', () => {
    it('startPipeline → POST /api/research/ais/start', async () => {
      mockPost.mockResolvedValueOnce(ok({ run_id: 'ais_run_001', task_id: 'task_001', message: 'Pipeline started' }))
      const { startPipeline } = await import('@/api/ais')
      const res = await startPipeline({ research_idea: 'superconductors', sources: ['arxiv'], max_papers: 30 })
      expect(mockPost).toHaveBeenCalledWith('/api/research/ais/start', expect.objectContaining({ research_idea: 'superconductors' }), expect.any(Object))
      expect(res.data.data.run_id).toBe('ais_run_001')
    })

    it('getPipelineStatus → GET /api/research/ais/:id/status', async () => {
      mockGet.mockResolvedValueOnce(ok({ run_id: 'ais_run_001', status: 'crawling', current_stage: 'crawl' }))
      const { getPipelineStatus } = await import('@/api/ais')
      const res = await getPipelineStatus('ais_run_001')
      expect(mockGet).toHaveBeenCalledWith('/api/research/ais/ais_run_001/status')
      expect(res.data.data.status).toBe('crawling')
    })

    it('getIdeas → GET /api/research/ais/:id/ideas', async () => {
      const ideas = [
        { id: 'i1', title: 'Idea A', hypothesis: 'H1', composite_score: 0.9 },
        { id: 'i2', title: 'Idea B', hypothesis: 'H2', composite_score: 0.7 },
      ]
      mockGet.mockResolvedValueOnce(ok(ideas))
      const { getIdeas } = await import('@/api/ais')
      const res = await getIdeas('ais_run_001')
      expect(res.data.data).toHaveLength(2)
      expect(res.data.data[0]?.composite_score).toBe(0.9)
    })

    it('selectIdea → POST /api/research/ais/:id/select-idea', async () => {
      mockPost.mockResolvedValueOnce(ok({ status: 'idea_selected' }))
      const { selectIdea } = await import('@/api/ais')
      const res = await selectIdea('ais_run_001', 'i1')
      expect(mockPost).toHaveBeenCalledWith('/api/research/ais/ais_run_001/select-idea', { idea_id: 'i1' })
      expect(res.data.data.status).toBe('idea_selected')
    })

    it('startDebate → POST /api/research/ais/:id/debate', async () => {
      mockPost.mockResolvedValueOnce(ok({ run_id: 'ais_run_001', task_id: 'task_debate_001', message: 'Stage 3 (debate) started.' }))
      const { startDebate } = await import('@/api/ais')
      const res = await startDebate('ais_run_001')
      expect(mockPost).toHaveBeenCalledWith('/api/research/ais/ais_run_001/debate')
      expect(res.data.data.task_id).toBe('task_debate_001')
    })

    it('approveDraft → POST /api/research/ais/:id/approve', async () => {
      mockPost.mockResolvedValueOnce(ok({ status: 'drafting' }))
      const { approveDraft } = await import('@/api/ais')
      const res = await approveDraft('ais_run_001', { feedback: 'Focus on methodology' })
      expect(mockPost).toHaveBeenCalledWith(
        '/api/research/ais/ais_run_001/approve',
        { feedback: 'Focus on methodology' },
        expect.any(Object),
      )
      expect(res.data.data.status).toBe('drafting')
    })

    it('getDraft → GET /api/research/ais/:id/draft', async () => {
      const draft = {
        title: 'Superconductor Review',
        sections: [{ heading: 'Introduction', content: 'Body text' }],
        citations: [{ id: 'c1', title: 'Ref 1' }],
        metadata: {},
      }
      mockGet.mockResolvedValueOnce(ok(draft))
      const { getDraft } = await import('@/api/ais')
      const res = await getDraft('ais_run_001')
      expect(res.data.data.title).toBe('Superconductor Review')
      expect(res.data.data.sections).toHaveLength(1)
    })

    it('exportDraft → GET /api/research/ais/:id/export?format=markdown', async () => {
      mockGet.mockResolvedValueOnce(ok('# Paper\n\nBody'))
      const { exportDraft } = await import('@/api/ais')
      await exportDraft('ais_run_001', 'markdown')
      expect(mockGet).toHaveBeenCalledWith('/api/research/ais/ais_run_001/export', { params: { format: 'markdown' } })
    })

    it('listRuns → GET /api/research/ais/runs', async () => {
      mockGet.mockResolvedValueOnce(ok([{ run_id: 'r1', status: 'completed', topic: 'test' }]))
      const { listRuns } = await import('@/api/ais')
      const res = await listRuns({ status: 'completed', limit: 5 })
      expect(mockGet).toHaveBeenCalledWith('/api/research/ais/runs', { params: { status: 'completed', limit: 5 } })
      expect(res.data.data).toHaveLength(1)
    })
  })

  describe('Thought Injection & Review', () => {
    it('injectThought → POST /api/research/ais/:id/inject', async () => {
      mockPost.mockResolvedValueOnce(ok({ status: 'injected' }))
      const { injectThought } = await import('@/api/ais')
      await injectThought('ais_run_001', { content: 'Consider thermal effects', type: 'guidance' })
      expect(mockPost).toHaveBeenCalledWith('/api/research/ais/ais_run_001/inject', expect.objectContaining({ content: 'Consider thermal effects' }))
    })

    it('triggerReview → POST /api/research/ais/:id/review', async () => {
      mockPost.mockResolvedValueOnce(ok({ review_overall: 7.5 }))
      const { triggerReview } = await import('@/api/ais')
      const res = await triggerReview('ais_run_001', { num_reviewers: 3 })
      expect(res.data.data.review_overall).toBe(7.5)
    })
  })

  describe('Provider & Tools', () => {
    it('getProviderInfo → GET /api/research/ais/providers', async () => {
      mockGet.mockResolvedValueOnce(ok({
        default_provider: 'anthropic',
        default_model: 'claude-sonnet-4-20250514',
        providers: { anthropic: { configured: true } },
        cache: { total_entries: 50 },
      }))
      const { getProviderInfo } = await import('@/api/ais')
      const res = await getProviderInfo()
      expect((res.data.data as unknown as Record<string, unknown>).default_provider).toBe('anthropic')
    })

    it('getResearchTools → GET /api/research/ais/tools', async () => {
      mockGet.mockResolvedValueOnce(ok({
        ai_scientist: { available: true },
        scienceclaw: { available: true, databases: ['arxiv'] },
      }))
      const { getResearchTools } = await import('@/api/ais')
      const res = await getResearchTools()
      expect(res.data.data).toBeDefined()
    })
  })

  describe('Path Recommendation', () => {
    it('getPathRecommendation → GET /api/research/ais/:id/recommend-path', async () => {
      mockGet.mockResolvedValueOnce(ok({ recommended_path: 'A', confidence: 0.85, reasoning: 'Strong hypothesis' }))
      const { getPathRecommendation } = await import('@/api/ais')
      const res = await getPathRecommendation('ais_run_001')
      expect(res.data.data.recommended_path).toBe('A')
      expect(res.data.data.confidence).toBe(0.85)
    })
  })

  describe('ScienceClaw Search', () => {
    it('scienceClawSearch → POST /api/research/ais/search', async () => {
      mockPost.mockResolvedValueOnce(ok({ papers: [{ title: 'Paper A', doi: '10.1234/a' }], total: 1 }))
      const { scienceClawSearch } = await import('@/api/ais')
      const res = await scienceClawSearch({ query: 'superconductors', mode: 'survey', max_papers: 10 })
      expect(mockPost).toHaveBeenCalledWith('/api/research/ais/search', expect.objectContaining({ query: 'superconductors', mode: 'survey' }))
      expect(res.data.data.total).toBe(1)
    })

    it('importSearchResults → POST /api/research/ais/search/import', async () => {
      mockPost.mockResolvedValueOnce(ok({ imported: 5 }))
      const { importSearchResults } = await import('@/api/ais')
      const res = await importSearchResults({ papers: [{ title: 'P1' }] })
      expect(res.data.data.imported).toBe(5)
    })
  })

  describe('Experiment (Stage 6)', () => {
    it('startExperiment → POST /api/research/ais/:id/experiment', async () => {
      mockPost.mockResolvedValueOnce(ok({ task_id: 'exp_task_001' }))
      const { startExperiment } = await import('@/api/ais')
      const res = await startExperiment('ais_run_001', { template: 'nanoGPT' })
      expect(mockPost).toHaveBeenCalledWith(
        '/api/research/ais/ais_run_001/experiment',
        expect.objectContaining({ template: 'nanoGPT' }),
        expect.any(Object),
      )
      expect(res.data.data.task_id).toBe('exp_task_001')
    })

    it('getExperimentStatus → GET /api/research/ais/:id/experiment/status', async () => {
      mockGet.mockResolvedValueOnce(ok({ status: 'running', progress: 0.4 }))
      const { getExperimentStatus } = await import('@/api/ais')
      const res = await getExperimentStatus('ais_run_001')
      expect(res.data.data.status).toBe('running')
    })

    it('getExperimentResult → GET /api/research/ais/:id/experiment/result', async () => {
      mockGet.mockResolvedValueOnce(ok({ metrics: { accuracy: 0.92 }, plots: [] }))
      const { getExperimentResult } = await import('@/api/ais')
      const res = await getExperimentResult('ais_run_001')
      expect(res.data.data.metrics).toBeDefined()
    })
  })

  describe('Direct Draft from Simulation', () => {
    it('draftFromSimulation → POST /api/research/ais/draft-from-simulation', async () => {
      mockPost.mockResolvedValueOnce(ok({ run_id: 'ais_run_direct' }))
      const { draftFromSimulation } = await import('@/api/ais')
      const res = await draftFromSimulation({ simulation_id: 'sim_001', research_idea: 'test' })
      expect(mockPost).toHaveBeenCalledWith('/api/research/ais/draft-from-simulation', { simulation_id: 'sim_001', research_idea: 'test' })
      expect(res.data.data.run_id).toBe('ais_run_direct')
    })
  })

  describe('Debate Summary', () => {
    it('getDebateSummary → GET /api/research/simulate/:id/summary', async () => {
      mockGet.mockResolvedValueOnce(ok({
        consensus: { consensus_level: 0.8, consensus_trend: 'converging' },
        key_arguments: [{ agent: 'Dr. A', round: 1, type: 'rebuttal', content: 'Method X' }],
        agent_count: 4,
        rounds_completed: 2,
        total_turns: 8,
      }))
      const { getDebateSummary } = await import('@/api/ais')
      const res = await getDebateSummary('sim_001')
      expect(mockGet).toHaveBeenCalledWith('/api/research/simulate/sim_001/summary')
      expect(res.data.data.consensus?.consensus_level).toBe(0.8)
    })
  })

  describe('History Endpoints', () => {
    it('getHistoryRuns → GET /api/research/history/runs with pagination', async () => {
      mockGet.mockResolvedValueOnce(ok({ runs: [{ run_id: 'r1' }], total: 42 }))
      const { getHistoryRuns } = await import('@/api/ais')
      const res = await getHistoryRuns({ page: 2, per_page: 20, type: 'debate' })
      expect(mockGet).toHaveBeenCalledWith('/api/research/history/runs', { params: { page: 2, per_page: 20, type: 'debate' } })
      expect(res.data.data.total).toBe(42)
    })

    it('getHistoryRunDetail → GET /api/research/history/runs/:id', async () => {
      mockGet.mockResolvedValueOnce(ok({ run_id: 'r1', type: 'debate', status: 'completed', query: 'test' }))
      const { getHistoryRunDetail } = await import('@/api/ais')
      const res = await getHistoryRunDetail('r1')
      expect(mockGet).toHaveBeenCalledWith('/api/research/history/runs/r1')
      expect(res.data.data.run_id).toBe('r1')
    })

    it('getHistoryTranscript → GET /api/research/history/runs/:id/transcript', async () => {
      mockGet.mockResolvedValueOnce(ok({ entries: [{ agent: 'Dr. A', content: 'hello' }] }))
      const { getHistoryTranscript } = await import('@/api/ais')
      await getHistoryTranscript('r1')
      expect(mockGet).toHaveBeenCalledWith('/api/research/history/runs/r1/transcript')
    })

    it('getHistoryDraft → GET /api/research/history/runs/:id/draft', async () => {
      mockGet.mockResolvedValueOnce(ok({ title: 'Draft', sections: [], citations: [], metadata: {} }))
      const { getHistoryDraft } = await import('@/api/ais')
      const res = await getHistoryDraft('r1')
      expect(res.data.data.title).toBe('Draft')
    })

    it('importCliRun → POST /api/research/history/runs/:id/import', async () => {
      mockPost.mockResolvedValueOnce(ok({ imported: true }))
      const { importCliRun } = await import('@/api/ais')
      const res = await importCliRun('r1')
      expect(mockPost).toHaveBeenCalledWith('/api/research/history/runs/r1/import')
      expect(res.data.data.imported).toBe(true)
    })

    it('getRunArtifactUrl returns correct URL', async () => {
      const { getRunArtifactUrl } = await import('@/api/ais')
      expect(getRunArtifactUrl('r1')).toBe('/api/research/history/runs/r1/artifact')
    })

    it('getProjectArtifactDownloadUrl returns correct URL with format', async () => {
      const { getProjectArtifactDownloadUrl } = await import('@/api/ais')
      expect(getProjectArtifactDownloadUrl('ais_run_001', 'html')).toBe('/api/research/ais/ais_run_001/artifact?format=html')
      expect(getProjectArtifactDownloadUrl('ais_run_001', 'pdf')).toBe('/api/research/ais/ais_run_001/artifact?format=pdf')
    })

    it('getRecentActivity → GET /api/research/history/recent', async () => {
      mockGet.mockResolvedValueOnce(ok([{ run_id: 'r1' }, { run_id: 'r2' }]))
      const { getRecentActivity } = await import('@/api/ais')
      const res = await getRecentActivity(5)
      expect(mockGet).toHaveBeenCalledWith('/api/research/history/recent', { params: { limit: 5 } })
      expect(res.data.data).toHaveLength(2)
    })
  })

  describe('Cost Estimate', () => {
    it('getCostEstimate → GET /api/research/history/cost-estimate', async () => {
      mockGet.mockResolvedValueOnce(ok({ estimated_cost_usd: 0.15, breakdown: { crawl: 0.05, debate: 0.10 } }))
      const { getCostEstimate } = await import('@/api/ais')
      const res = await getCostEstimate({ action: 'full_pipeline' })
      expect(res.data.data.estimated_cost_usd).toBe(0.15)
    })
  })
})

// =========================================================================
// 2. RESEARCH — research.ts
// =========================================================================

describe('Research Protocol (research.ts)', () => {
  describe('Ingestion', () => {
    it('startIngestion → POST /api/research/ingest with retry', async () => {
      mockPost.mockResolvedValueOnce(ok({ task_id: 'ingest_001' }))
      const { startIngestion } = await import('@/api/research')
      const res = await startIngestion({ query: 'battery', sources: ['arxiv', 'pubmed'], max_results: 50 })
      expect(mockPost).toHaveBeenCalledWith('/api/research/ingest', expect.objectContaining({ query: 'battery', sources: ['arxiv', 'pubmed'] }))
      expect(res.data.data.task_id).toBe('ingest_001')
    })

    it('getIngestionStatus → GET /api/research/ingest/:taskId/status', async () => {
      mockGet.mockResolvedValueOnce(ok({ status: 'running', progress: 0.6, message: '30 papers processed' }))
      const { getIngestionStatus } = await import('@/api/research')
      const res = await getIngestionStatus('ingest_001')
      expect(mockGet).toHaveBeenCalledWith('/api/research/ingest/ingest_001/status')
      expect(res.data.data.progress).toBe(0.6)
    })
  })

  describe('Papers CRUD', () => {
    it('listPapers → GET /api/research/papers', async () => {
      mockGet.mockResolvedValueOnce(ok([
        { doi: '10.1/a', title: 'Paper A', authors: ['Auth1'], source: 'arxiv' },
        { doi: '10.1/b', title: 'Paper B', authors: ['Auth2'], source: 'pubmed' },
      ]))
      const { listPapers } = await import('@/api/research')
      const res = await listPapers({ source: 'arxiv', limit: 20 })
      expect(mockGet).toHaveBeenCalledWith('/api/research/papers', { params: { source: 'arxiv', limit: 20 } })
      expect(res.data.data).toHaveLength(2)
    })

    it('getPaper → GET /api/research/papers/:doi (URL-encoded)', async () => {
      mockGet.mockResolvedValueOnce(ok({ doi: '10.1234/test', title: 'Test Paper' }))
      const { getPaper } = await import('@/api/research')
      await getPaper('10.1234/test')
      expect(mockGet).toHaveBeenCalledWith('/api/research/papers/10.1234%2Ftest')
    })
  })

  describe('Topics', () => {
    it('listTopics → GET /api/research/topics', async () => {
      mockGet.mockResolvedValueOnce(ok([
        { id: 't1', name: 'Electrochemistry', paper_count: 15 },
        { id: 't2', name: 'Superconductors', paper_count: 8 },
      ]))
      const { listTopics } = await import('@/api/research')
      const res = await listTopics({ tree: true })
      expect(mockGet).toHaveBeenCalledWith('/api/research/topics', { params: { tree: true } })
      expect(res.data.data).toHaveLength(2)
    })

    it('getTopic → GET /api/research/topics/:id', async () => {
      mockGet.mockResolvedValueOnce(ok({ id: 't1', name: 'Electrochemistry', paper_count: 15 }))
      const { getTopic } = await import('@/api/research')
      const res = await getTopic('t1')
      expect(res.data.data.name).toBe('Electrochemistry')
    })

    it('getTopicPapers → GET /api/research/topics/:id/papers', async () => {
      mockGet.mockResolvedValueOnce(ok([{ doi: '10.1/a', title: 'Paper A', authors: [], source: 'arxiv' }]))
      const { getTopicPapers } = await import('@/api/research')
      const res = await getTopicPapers('t1')
      expect(mockGet).toHaveBeenCalledWith('/api/research/topics/t1/papers')
      expect(res.data.data).toHaveLength(1)
    })
  })

  describe('Research Map & Gaps', () => {
    it('getResearchMap → GET /api/research/map', async () => {
      mockGet.mockResolvedValueOnce(ok({
        nodes: [
          { id: 'n1', label: 'Node A', type: 'topic', connections: ['n2'] },
          { id: 'n2', label: 'Node B', type: 'paper', connections: ['n1'] },
        ],
      }))
      const { getResearchMap } = await import('@/api/research')
      const res = await getResearchMap({ query: 'battery' })
      expect(mockGet).toHaveBeenCalledWith('/api/research/map', { params: { query: 'battery' }, timeout: 30_000 })
      expect(res.data.data.nodes).toHaveLength(2)
    })

    it('getResearchGaps → GET /api/research/gaps', async () => {
      mockGet.mockResolvedValueOnce(ok([
        { id: 'g1', description: 'Missing thermal analysis', score: 0.9, related_topics: ['t1'] },
      ]))
      const { getResearchGaps } = await import('@/api/research')
      const res = await getResearchGaps({ min_score: 0.5 })
      expect(mockGet).toHaveBeenCalledWith('/api/research/gaps', { params: { min_score: 0.5 } })
      expect(res.data.data[0]?.score).toBe(0.9)
    })
  })

  describe('Stats', () => {
    it('getResearchStats → GET /api/research/stats', async () => {
      mockGet.mockResolvedValueOnce(ok({
        total_papers: 120,
        total_topics: 8,
        total_agents: 24,
        total_simulations: 5,
        sources: { arxiv: 80, pubmed: 40 },
      }))
      const { getResearchStats } = await import('@/api/research')
      const res = await getResearchStats()
      expect(res.data.data.total_papers).toBe(120)
      expect(res.data.data.sources.arxiv).toBe(80)
    })
  })
})

// =========================================================================
// 3. SIMULATION — simulation.ts
// =========================================================================

describe('Simulation Protocol (simulation.ts)', () => {
  describe('Agent Generation & CRUD', () => {
    it('generateAgents → POST /api/research/agents/generate with retry', async () => {
      mockPost.mockResolvedValueOnce(ok({ task_id: 'gen_001' }))
      const { generateAgents } = await import('@/api/simulation')
      const res = await generateAgents({ topic_id: 't1', agents_per_cluster: 3 })
      expect(mockPost).toHaveBeenCalledWith('/api/research/agents/generate', expect.objectContaining({ topic_id: 't1' }))
      expect(res.data.data.task_id).toBe('gen_001')
    })

    it('getAgentGenerationStatus → GET /api/research/agents/generate/:taskId/status', async () => {
      mockGet.mockResolvedValueOnce(ok({ status: 'completed', progress: 1.0 }))
      const { getAgentGenerationStatus } = await import('@/api/simulation')
      const res = await getAgentGenerationStatus('gen_001')
      expect(res.data.data.status).toBe('completed')
    })

    it('listAgents → GET /api/research/agents', async () => {
      mockGet.mockResolvedValueOnce(ok([
        { id: 'a1', name: 'Dr. Smith', role: 'Experimentalist', expertise: ['batteries'] },
        { id: 'a2', name: 'Dr. Jones', role: 'Theoretician', expertise: ['physics'] },
      ]))
      const { listAgents } = await import('@/api/simulation')
      const res = await listAgents({ topic_id: 't1' })
      expect(mockGet).toHaveBeenCalledWith('/api/research/agents', { params: { topic_id: 't1' } })
      expect(res.data.data).toHaveLength(2)
    })

    it('getAgent → GET /api/research/agents/:id', async () => {
      mockGet.mockResolvedValueOnce(ok({ id: 'a1', name: 'Dr. Smith', role: 'Experimentalist', expertise: ['batteries'] }))
      const { getAgent } = await import('@/api/simulation')
      const res = await getAgent('a1')
      expect(res.data.data.name).toBe('Dr. Smith')
    })

    it('configureAgent → PATCH /api/research/agents/:id/configure', async () => {
      mockPatch.mockResolvedValueOnce(ok({ id: 'a1', name: 'Dr. Smith', role: 'Experimentalist', expertise: ['batteries'], llm_model: 'gpt-4o' }))
      const { configureAgent } = await import('@/api/simulation')
      const res = await configureAgent('a1', { llm_model: 'gpt-4o', is_super_agent: true })
      expect(mockPatch).toHaveBeenCalledWith('/api/research/agents/a1/configure', { llm_model: 'gpt-4o', is_super_agent: true })
      expect(res.data.data.llm_model).toBe('gpt-4o')
    })
  })

  describe('Models & Skills', () => {
    it('listModels → GET /api/research/models', async () => {
      mockGet.mockResolvedValueOnce(ok([
        { provider: 'anthropic', models: [{ id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet' }] },
      ]))
      const { listModels } = await import('@/api/simulation')
      const res = await listModels()
      expect(res.data.data[0]?.provider).toBe('anthropic')
    })

    it('listSkills → GET /api/research/skills', async () => {
      mockGet.mockResolvedValueOnce(ok([
        { id: 's1', name: 'literature_review', category: 'research' },
        { id: 's2', name: 'data_analysis', category: 'analysis' },
      ]))
      const { listSkills } = await import('@/api/simulation')
      const res = await listSkills('research')
      expect(mockGet).toHaveBeenCalledWith('/api/research/skills', { params: { category: 'research' } })
      expect(res.data.data).toHaveLength(2)
    })
  })

  describe('Simulation Lifecycle', () => {
    it('listFormats → GET /api/research/simulate/formats', async () => {
      mockGet.mockResolvedValueOnce(ok([
        { id: 'oxford', name: 'Oxford Debate', description: 'Structured pro/con' },
        { id: 'panel', name: 'Panel Discussion', description: 'Open format' },
      ]))
      const { listFormats } = await import('@/api/simulation')
      const res = await listFormats()
      expect(res.data.data).toHaveLength(2)
    })

    it('createSimulation → POST /api/research/simulate with retry', async () => {
      mockPost.mockResolvedValueOnce(ok({ simulation_id: 'sim_001' }))
      const { createSimulation } = await import('@/api/simulation')
      const res = await createSimulation({ format: 'oxford', topic: 'superconductors', agent_ids: ['a1', 'a2'] })
      expect(mockPost).toHaveBeenCalledWith('/api/research/simulate', expect.objectContaining({ format: 'oxford' }))
      expect(res.data.data.simulation_id).toBe('sim_001')
    })

    it('startSimulation → POST /api/research/simulate/:id/start with retry', async () => {
      mockPost.mockResolvedValueOnce(ok({ status: 'running' }))
      const { startSimulation } = await import('@/api/simulation')
      const res = await startSimulation('sim_001')
      expect(mockPost).toHaveBeenCalledWith('/api/research/simulate/sim_001/start')
      expect(res.data.data.status).toBe('running')
    })

    it('getSimulationStatus → GET /api/research/simulate/:id/status', async () => {
      mockGet.mockResolvedValueOnce(ok({ id: 'sim_001', status: 'running', current_round: 2, total_rounds: 5 }))
      const { getSimulationStatus } = await import('@/api/simulation')
      const res = await getSimulationStatus('sim_001')
      expect(res.data.data.current_round).toBe(2)
    })

    it('getTranscript → GET /api/research/simulate/:id/transcript', async () => {
      mockGet.mockResolvedValueOnce(ok([
        { round: 1, agent: 'Dr. Smith', content: 'Opening argument' },
        { round: 1, agent: 'Dr. Jones', content: 'Counterpoint' },
      ]))
      const { getTranscript } = await import('@/api/simulation')
      const res = await getTranscript('sim_001', 1)
      expect(mockGet).toHaveBeenCalledWith('/api/research/simulate/sim_001/transcript', { params: { round: 1 } })
      expect(res.data.data).toHaveLength(2)
    })

    it('injectPaper → POST /api/research/simulate/:id/inject', async () => {
      mockPost.mockResolvedValueOnce(ok({ status: 'paper_injected' }))
      const { injectPaper } = await import('@/api/simulation')
      await injectPaper('sim_001', '10.1234/test')
      expect(mockPost).toHaveBeenCalledWith('/api/research/simulate/sim_001/inject', { doi: '10.1234/test' })
    })

    it('listSimulations → GET /api/research/simulate', async () => {
      mockGet.mockResolvedValueOnce(ok([{ id: 'sim_001', format: 'oxford', topic: 'test', status: 'completed', created_at: '2026-03-21' }]))
      const { listSimulations } = await import('@/api/simulation')
      const res = await listSimulations()
      expect(res.data.data).toHaveLength(1)
    })
  })

  describe('Deep Interaction', () => {
    it('chatWithAgent → POST /api/research/simulate/:simId/chat', async () => {
      mockPost.mockResolvedValueOnce(ok({ reply: 'I believe thermal analysis is key.', agent_id: 'a1' }))
      const { chatWithAgent } = await import('@/api/simulation')
      const res = await chatWithAgent('sim_001', 'a1', 'What about thermal effects?')
      expect(mockPost).toHaveBeenCalledWith('/api/research/simulate/sim_001/chat', { agent_id: 'a1', message: 'What about thermal effects?' })
      expect(res.data.data.reply).toContain('thermal')
    })

    it('chatWithReport → POST /api/research/report/:reportId/chat', async () => {
      mockPost.mockResolvedValueOnce(ok({ reply: 'The report highlights three key findings.' }))
      const { chatWithReport } = await import('@/api/simulation')
      const res = await chatWithReport('rpt_001', 'Summarize findings')
      expect(mockPost).toHaveBeenCalledWith('/api/research/report/rpt_001/chat', { message: 'Summarize findings' })
      expect(res.data.data.reply).toBeTruthy()
    })

    it('forkSimulation → POST /api/research/simulate/:id/fork', async () => {
      mockPost.mockResolvedValueOnce(ok({ simulation_id: 'sim_002', forked_from: 'sim_001', from_round: 3 }))
      const { forkSimulation } = await import('@/api/simulation')
      const res = await forkSimulation('sim_001', 3, { inject_paper: '10.1/x' })
      expect(mockPost).toHaveBeenCalledWith('/api/research/simulate/sim_001/fork', { from_round: 3, modifications: { inject_paper: '10.1/x' } })
      expect(res.data.data.forked_from).toBe('sim_001')
    })
  })

  describe('Reports', () => {
    it('listReportTypes → GET /api/research/report/types', async () => {
      mockGet.mockResolvedValueOnce(ok([
        { id: 'evolution', name: 'Evolution Report', description: 'Track argument evolution' },
      ]))
      const { listReportTypes } = await import('@/api/simulation')
      const res = await listReportTypes()
      expect(res.data.data[0]?.id).toBe('evolution')
    })

    it('generateReport → POST /api/research/report/:simId with retry', async () => {
      mockPost.mockResolvedValueOnce(ok({ task_id: 'rpt_task_001' }))
      const { generateReport } = await import('@/api/simulation')
      const res = await generateReport('sim_001', { type: 'evolution' })
      expect(mockPost).toHaveBeenCalledWith('/api/research/report/sim_001', { type: 'evolution' })
      expect(res.data.data.task_id).toBe('rpt_task_001')
    })

    it('getReport → GET /api/research/report/:id/view', async () => {
      mockGet.mockResolvedValueOnce(ok({ id: 'rpt_001', type: 'evolution', content: { summary: 'test' }, created_at: '2026-03-21' }))
      const { getReport } = await import('@/api/simulation')
      const res = await getReport('rpt_001', 'json')
      expect(mockGet).toHaveBeenCalledWith('/api/research/report/rpt_001/view', { params: { format: 'json' } })
      expect(res.data.data.type).toBe('evolution')
    })

    it('listReports → GET /api/research/reports', async () => {
      mockGet.mockResolvedValueOnce(ok([{ id: 'rpt_001' }]))
      const { listReports } = await import('@/api/simulation')
      const res = await listReports()
      expect(res.data.data).toHaveLength(1)
    })

    it('exportReport with json format → GET /api/research/report/:id/export/json', async () => {
      mockGet.mockResolvedValueOnce(ok({ content: {} }))
      const { exportReport } = await import('@/api/simulation')
      await exportReport('rpt_001', 'json')
      expect(mockGet).toHaveBeenCalledWith('/api/research/report/rpt_001/export/json', { responseType: 'json' })
    })

    it('exportReport with pptx format → blob responseType', async () => {
      mockGet.mockResolvedValueOnce({ data: new Blob(['pptx']) })
      const { exportReport } = await import('@/api/simulation')
      await exportReport('rpt_001', 'pptx')
      expect(mockGet).toHaveBeenCalledWith('/api/research/report/rpt_001/export/pptx', { responseType: 'blob' })
    })

    it('generateInfographic → POST /api/research/report/:id/infographic', async () => {
      mockPost.mockResolvedValueOnce(ok({ svg: '<svg></svg>', metrics: {} }))
      const { generateInfographic } = await import('@/api/simulation')
      const res = await generateInfographic('rpt_001')
      expect(mockPost).toHaveBeenCalledWith('/api/research/report/rpt_001/infographic')
      expect(res.data.data.svg).toBeDefined()
    })
  })
})

// =========================================================================
// 4. MIROFISH — mirofish.ts
// =========================================================================

describe('Mirofish Protocol (mirofish.ts)', () => {
  describe('Debate Frame', () => {
    it('getDebateFrame → GET /api/research/simulate/:id/frame', async () => {
      mockGet.mockResolvedValueOnce(ok({
        simulation_id: 'sim_001',
        topic: 'superconductors',
        format: 'oxford',
        agents: [{ id: 'a1', name: 'Dr. A', role: 'Experimentalist' }],
        rules: { max_rounds: 5 },
      }))
      const { getDebateFrame } = await import('@/api/mirofish')
      const res = await getDebateFrame('sim_001')
      expect(mockGet).toHaveBeenCalledWith('/api/research/simulate/sim_001/frame')
      expect(res.data.data.format).toBe('oxford')
    })
  })

  describe('Knowledge Graph', () => {
    it('getGraphSnapshot → GET /api/research/simulate/:id/graph with D3 format', async () => {
      mockGet.mockResolvedValueOnce(ok({
        nodes: [{ id: 'n1', label: 'Concept A', type: 'concept' }],
        links: [{ source: 'n1', target: 'n2', type: 'supports' }],
        round: 2,
      }))
      const { getGraphSnapshot } = await import('@/api/mirofish')
      const res = await getGraphSnapshot('sim_001', 2)
      expect(mockGet).toHaveBeenCalledWith('/api/research/simulate/sim_001/graph', {
        params: { round: 2, format: 'd3' },
      })
      expect(res.data.data.nodes).toHaveLength(1)
      expect(res.data.data.links).toHaveLength(1)
    })

    it('getGraphSnapshot without round → omits round param', async () => {
      mockGet.mockResolvedValueOnce(ok({ nodes: [], links: [] }))
      const { getGraphSnapshot } = await import('@/api/mirofish')
      await getGraphSnapshot('sim_001')
      expect(mockGet).toHaveBeenCalledWith('/api/research/simulate/sim_001/graph', {
        params: { format: 'd3' },
      })
    })

    it('getGraphEvents → GET /api/research/simulate/:id/graph/events', async () => {
      mockGet.mockResolvedValueOnce(ok([
        { type: 'add_node', target: 'n3', data: { label: 'New Concept' }, round: 2 },
        { type: 'add_link', target: 'n1-n3', data: { type: 'derives' }, round: 2 },
      ]))
      const { getGraphEvents } = await import('@/api/mirofish')
      const res = await getGraphEvents('sim_001', 2)
      expect(mockGet).toHaveBeenCalledWith('/api/research/simulate/sim_001/graph/events', { params: { round: 2 } })
      expect(res.data.data).toHaveLength(2)
    })
  })

  describe('Scoreboard', () => {
    it('getScoreboard → GET /api/research/simulate/:id/scoreboard', async () => {
      mockGet.mockResolvedValueOnce(ok([
        { agent_id: 'a1', agent_name: 'Dr. A', scores: { clarity: 8, depth: 7 }, total: 15, rank: 1 },
        { agent_id: 'a2', agent_name: 'Dr. B', scores: { clarity: 6, depth: 9 }, total: 15, rank: 1 },
      ]))
      const { getScoreboard } = await import('@/api/mirofish')
      const res = await getScoreboard('sim_001', 1)
      expect(mockGet).toHaveBeenCalledWith('/api/research/simulate/sim_001/scoreboard', { params: { round: 1 } })
      expect(res.data.data).toHaveLength(2)
      expect(res.data.data[0]?.total).toBe(15)
    })

    it('getScoreboard without round → all rounds', async () => {
      mockGet.mockResolvedValueOnce(ok([]))
      const { getScoreboard } = await import('@/api/mirofish')
      await getScoreboard('sim_001')
      expect(mockGet).toHaveBeenCalledWith('/api/research/simulate/sim_001/scoreboard', { params: {} })
    })
  })

  describe('Analyst Feed', () => {
    it('getAnalystFeed → GET /api/research/simulate/:id/analyst-feed', async () => {
      mockGet.mockResolvedValueOnce(ok([
        { round: 1, narrative: 'Opening round saw strong positions from both sides.' },
        { round: 2, narrative: 'Convergence emerging on methodology.' },
      ]))
      const { getAnalystFeed } = await import('@/api/mirofish')
      const res = await getAnalystFeed('sim_001', 2)
      expect(mockGet).toHaveBeenCalledWith('/api/research/simulate/sim_001/analyst-feed', { params: { max_round: 2 } })
      expect(res.data.data).toHaveLength(2)
    })
  })

  describe('Stances', () => {
    it('getStances → GET /api/research/simulate/:id/stances', async () => {
      mockGet.mockResolvedValueOnce(ok([
        {
          agent_id: 'a1',
          agent_name: 'Dr. A',
          stance: 0.7,
          confidence: 0.9,
          history: [{ round: 1, stance: 0.5 }, { round: 2, stance: 0.7 }],
        },
      ]))
      const { getStances } = await import('@/api/mirofish')
      const res = await getStances('sim_001')
      expect(mockGet).toHaveBeenCalledWith('/api/research/simulate/sim_001/stances')
      expect(res.data.data[0]?.history).toHaveLength(2)
    })
  })

  describe('Session Snapshots', () => {
    it('createSnapshot → POST /api/research/simulate/:id/snapshot', async () => {
      mockPost.mockResolvedValueOnce(ok({ id: 'snap_001', simulation_id: 'sim_001', source_mode: 'research', created_at: '2026-03-21', data: {} }))
      const { createSnapshot } = await import('@/api/mirofish')
      const res = await createSnapshot('sim_001', 'research')
      expect(mockPost).toHaveBeenCalledWith('/api/research/simulate/sim_001/snapshot', { source_mode: 'research' })
      expect(res.data.data.id).toBe('snap_001')
    })

    it('loadSnapshot → GET /api/research/simulate/:simId/snapshot/:snapId', async () => {
      mockGet.mockResolvedValueOnce(ok({ id: 'snap_001', simulation_id: 'sim_001', source_mode: 'research', created_at: '2026-03-21', data: { round: 3 } }))
      const { loadSnapshot } = await import('@/api/mirofish')
      const res = await loadSnapshot('sim_001', 'snap_001')
      expect(mockGet).toHaveBeenCalledWith('/api/research/simulate/sim_001/snapshot/snap_001')
      expect(res.data.data.data.round).toBe(3)
    })

    it('listSnapshots → GET /api/research/simulate/:id/snapshots', async () => {
      mockGet.mockResolvedValueOnce(ok([{ id: 'snap_001' }, { id: 'snap_002' }]))
      const { listSnapshots } = await import('@/api/mirofish')
      const res = await listSnapshots('sim_001')
      expect(mockGet).toHaveBeenCalledWith('/api/research/simulate/sim_001/snapshots')
      expect(res.data.data).toHaveLength(2)
    })
  })
})

// =========================================================================
// 5. PAPER LAB — paperLab.ts
// =========================================================================

describe('Paper Lab Protocol (paperLab.ts)', () => {
  describe('Upload', () => {
    it('uploadPaper → POST /api/research/paper-lab/upload (multipart)', async () => {
      mockPost.mockResolvedValueOnce(ok({ upload_id: 'upload_001' }))
      const { uploadPaper } = await import('@/api/paperLab')
      const file = new File(['test content'], 'paper.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
      const res = await uploadPaper(file)
      expect(mockPost).toHaveBeenCalledWith(
        '/api/research/paper-lab/upload',
        expect.any(FormData),
        expect.objectContaining({ headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 }),
      )
      expect(res.data.data.upload_id).toBe('upload_001')
    })
  })

  describe('Status & Review', () => {
    it('getUploadStatus → GET /api/research/paper-lab/:id/status', async () => {
      mockGet.mockResolvedValueOnce(ok({
        upload_id: 'upload_001',
        title: 'My Paper',
        language: 'en',
        field: 'materials_science',
        status: 'review_complete',
        round_count: 3,
        review_scores: [5.2, 6.8, 7.1],
        created_at: '2026-03-21',
      }))
      const { getUploadStatus } = await import('@/api/paperLab')
      const res = await getUploadStatus('upload_001')
      expect(mockGet).toHaveBeenCalledWith('/api/research/paper-lab/upload_001/status')
      expect(res.data.data.review_scores).toHaveLength(3)
      expect(res.data.data.round_count).toBe(3)
    })

    it('startReview → POST /api/research/paper-lab/:id/start-review', async () => {
      mockPost.mockResolvedValueOnce(ok({ status: 'review_started' }))
      const { startReview } = await import('@/api/paperLab')
      const res = await startReview('upload_001', { rounds: 3, reviewers: 2, live: true })
      expect(mockPost).toHaveBeenCalledWith('/api/research/paper-lab/upload_001/start-review', { rounds: 3, reviewers: 2, live: true })
      expect(res.data.data.status).toBe('review_started')
    })
  })

  describe('Rounds & Draft', () => {
    it('getRounds → GET /api/research/paper-lab/:id/rounds', async () => {
      mockGet.mockResolvedValueOnce(ok([
        {
          round: 1,
          reviews: [{ reviewer: 'Reviewer 1', score: 5.2, comments: 'Needs more data', strengths: ['novel'], weaknesses: ['thin methods'] }],
          revision: { author: 'AuthorBot', changes: ['Added methodology section'] },
        },
        {
          round: 2,
          reviews: [{ reviewer: 'Reviewer 1', score: 6.8, comments: 'Improved', strengths: ['better methods'], weaknesses: ['citations'] }],
        },
      ]))
      const { getRounds } = await import('@/api/paperLab')
      const res = await getRounds('upload_001')
      expect(mockGet).toHaveBeenCalledWith('/api/research/paper-lab/upload_001/rounds')
      expect(res.data.data).toHaveLength(2)
      expect(res.data.data[0]?.reviews[0]?.score).toBe(5.2)
    })

    it('getDraft → GET /api/research/paper-lab/:id/draft', async () => {
      mockGet.mockResolvedValueOnce(ok({
        title: 'Revised Paper',
        sections: [{ heading: 'Abstract', content: 'Revised abstract' }],
        citations: [{ id: 'c1', title: 'Reference 1' }],
        metadata: { word_count: 5000 },
      }))
      const { getDraft } = await import('@/api/paperLab')
      const res = await getDraft('upload_001')
      expect(res.data.data.title).toBe('Revised Paper')
      expect(res.data.data.sections).toHaveLength(1)
    })
  })

  describe('Uploads Listing', () => {
    it('listUploads → GET /api/research/paper-lab/uploads', async () => {
      mockGet.mockResolvedValueOnce(ok([
        { upload_id: 'upload_001', title: 'Paper A', status: 'completed', language: 'en', field: 'cs', round_count: 2, created_at: '2026-03-21' },
        { upload_id: 'upload_002', title: 'Paper B', status: 'reviewing', language: 'zh', field: 'physics', round_count: 1, created_at: '2026-03-22' },
      ]))
      const { listUploads } = await import('@/api/paperLab')
      const res = await listUploads()
      expect(mockGet).toHaveBeenCalledWith('/api/research/paper-lab/uploads')
      expect(res.data.data).toHaveLength(2)
    })
  })

  describe('Gap-Fill', () => {
    it('fillGaps → POST /api/research/paper-lab/:id/fill-gaps with long timeout', async () => {
      mockPost.mockResolvedValueOnce(ok({ status: 'gaps_filled' }))
      const { fillGaps } = await import('@/api/paperLab')
      const res = await fillGaps('upload_001', { live: true })
      expect(mockPost).toHaveBeenCalledWith(
        '/api/research/paper-lab/upload_001/fill-gaps',
        { live: true },
        expect.objectContaining({ timeout: 120000 }),
      )
      expect(res.data.data.status).toBe('gaps_filled')
    })
  })

  describe('Specialist Review', () => {
    it('runSpecialistReview → POST /api/research/paper-lab/:id/specialist-review', async () => {
      mockPost.mockResolvedValueOnce(ok({ upload_id: 'upload_001', task_id: 'task_001', message: 'started' }))
      const { runSpecialistReview } = await import('@/api/paperLab')
      const res = await runSpecialistReview('upload_001', { target: 'draft', strictness: 0.75 })
      expect(mockPost).toHaveBeenCalledWith(
        '/api/research/paper-lab/upload_001/specialist-review',
        { target: 'draft', strictness: 0.75 },
        expect.objectContaining({ timeout: 120000 }),
      )
      expect(res.data.data.task_id).toBe('task_001')
    })

    it('getSpecialistReview → GET /api/research/paper-lab/:id/specialist-review', async () => {
      mockGet.mockResolvedValueOnce(ok({ upload_id: 'upload_001', reviews: [] }))
      const { getSpecialistReview } = await import('@/api/paperLab')
      const res = await getSpecialistReview('upload_001')
      expect(mockGet).toHaveBeenCalledWith('/api/research/paper-lab/upload_001/specialist-review')
      expect(res.data.data.upload_id).toBe('upload_001')
    })
  })

  describe('Response to Reviewers', () => {
    it('getResponseToReviewers (json) → GET /api/research/paper-lab/:id/response-to-reviewers', async () => {
      mockGet.mockResolvedValueOnce(ok({ rounds: [{ round: 1, responses: [] }] }))
      const { getResponseToReviewers } = await import('@/api/paperLab')
      const res = await getResponseToReviewers('upload_001', 'json')
      expect(mockGet).toHaveBeenCalledWith('/api/research/paper-lab/upload_001/response-to-reviewers?format=json')
      expect(res).toBeDefined()
    })

    it('getResponseToReviewers (docx) → opens window', async () => {
      const openSpy = vi.fn()
      vi.stubGlobal('open', openSpy)
      const { getResponseToReviewers } = await import('@/api/paperLab')
      await getResponseToReviewers('upload_001', 'docx')
      expect(openSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/research/paper-lab/upload_001/response-to-reviewers?format=docx'),
        '_blank',
      )
      vi.unstubAllGlobals()
    })
  })
})

// =========================================================================
// 6. CLIENT UTILITIES — client.ts
// =========================================================================

describe('Client Utilities (client.ts)', () => {
  describe('requestWithRetry', () => {
    it('succeeds on first attempt', async () => {
      const { requestWithRetry } = await import('@/api/client')
      const fn = vi.fn().mockResolvedValueOnce(ok({ result: 'ok' }))
      const res = await requestWithRetry<{ result: string }>(fn, 3, 10)
      expect(fn).toHaveBeenCalledTimes(1)
      expect(res.data.data.result).toBe('ok')
    })

    it('retries on failure then succeeds', async () => {
      const { requestWithRetry } = await import('@/api/client')
      const fn = vi.fn()
        .mockRejectedValueOnce(new Error('Timeout'))
        .mockRejectedValueOnce(new Error('Timeout'))
        .mockResolvedValueOnce(ok({ result: 'recovered' }))
      const res = await requestWithRetry<{ result: string }>(fn, 3, 10)
      expect(fn).toHaveBeenCalledTimes(3)
      expect(res.data.data.result).toBe('recovered')
    })

    it('throws after all retries exhausted', async () => {
      const { requestWithRetry } = await import('@/api/client')
      const fn = vi.fn().mockRejectedValue(new Error('Persistent failure'))
      await expect(requestWithRetry(fn, 2, 10)).rejects.toThrow('Persistent failure')
      expect(fn).toHaveBeenCalledTimes(2)
    })
  })

  describe('createAbortController', () => {
    it('creates AbortController instance', async () => {
      const { createAbortController } = await import('@/api/client')
      const controller = createAbortController()
      expect(controller).toBeInstanceOf(AbortController)
      expect(controller.signal.aborted).toBe(false)
    })
  })

  describe('Timeout constants', () => {
    it('exports correct timeout values', async () => {
      const { STATUS_TIMEOUT, LONG_TIMEOUT } = await import('@/api/client')
      expect(STATUS_TIMEOUT).toBe(4000)
      expect(LONG_TIMEOUT).toBe(300000)
    })
  })
})

// =========================================================================
// 7. CROSS-PROTOCOL INTEGRATION
// =========================================================================

describe('Cross-Protocol Integration', () => {
  it('Full pipeline flow: start → poll → select idea → debate → approve → draft', async () => {
    // Step 1: Start pipeline
    mockPost.mockResolvedValueOnce(ok({ run_id: 'ais_full_001', task_id: 'task_001' }))
    const { startPipeline, getPipelineStatus, getIdeas, selectIdea, startDebate, approveDraft, getDraft } = await import('@/api/ais')

    const startRes = await startPipeline({ research_idea: 'Full pipeline test' })
    const runId = startRes.data.data.run_id
    expect(runId).toBe('ais_full_001')

    // Step 2: Poll status → crawling done, ideas ready
    mockGet.mockResolvedValueOnce(ok({ run_id: runId, status: 'awaiting_selection', current_stage: 'ideas' }))
    const statusRes = await getPipelineStatus(runId)
    expect(statusRes.data.data.status).toBe('awaiting_selection')

    // Step 3: Get ideas
    mockGet.mockResolvedValueOnce(ok([
      { id: 'i1', title: 'Best Idea', hypothesis: 'H1', composite_score: 0.95 },
      { id: 'i2', title: 'Good Idea', hypothesis: 'H2', composite_score: 0.80 },
    ]))
    const ideasRes = await getIdeas(runId)
    const topIdea = ideasRes.data.data[0]
    expect(topIdea).toBeDefined()
    if (!topIdea) throw new Error('Expected at least one idea')
    expect(topIdea.composite_score).toBe(0.95)

    // Step 4: Select best idea
    mockPost.mockResolvedValueOnce(ok({ status: 'idea_selected' }))
    await selectIdea(runId, topIdea.id)

    // Step 5: Start debate
    mockPost.mockResolvedValueOnce(ok({ run_id: runId, task_id: 'task_stage3_full_001', message: 'Stage 3 (debate) started.' }))
    const debateRes = await startDebate(runId)
    expect(debateRes.data.data.task_id).toBe('task_stage3_full_001')

    // Step 6: Approve and proceed to drafting
    mockPost.mockResolvedValueOnce(ok({ status: 'drafting' }))
    await approveDraft(runId)

    // Step 7: Get draft
    mockGet.mockResolvedValueOnce(ok({
      title: 'Full Pipeline Paper',
      sections: [{ heading: 'Intro', content: 'Text' }],
      citations: [],
      metadata: {},
    }))
    const draftRes = await getDraft(runId)
    expect(draftRes.data.data.title).toBe('Full Pipeline Paper')
  })

  it('Paper Lab flow: upload → review → rounds → gap-fill → draft', async () => {
    const { uploadPaper, startReview, getRounds, fillGaps, getDraft } = await import('@/api/paperLab')

    // Upload
    mockPost.mockResolvedValueOnce(ok({ upload_id: 'up_flow_001' }))
    const file = new File(['content'], 'test.docx')
    const upRes = await uploadPaper(file)
    const uploadId = upRes.data.data.upload_id

    // Start review
    mockPost.mockResolvedValueOnce(ok({ status: 'review_started' }))
    await startReview(uploadId, { rounds: 2, live: false })

    // Get rounds
    mockGet.mockResolvedValueOnce(ok([
      { round: 1, reviews: [{ reviewer: 'R1', score: 5.0, comments: 'Needs work' }] },
      { round: 2, reviews: [{ reviewer: 'R1', score: 7.0, comments: 'Much better' }] },
    ]))
    const roundsRes = await getRounds(uploadId)
    expect(roundsRes.data.data).toHaveLength(2)
    expect(roundsRes.data.data[1]?.reviews[0]?.score).toBe(7.0)

    // Fill gaps
    mockPost.mockResolvedValueOnce(ok({ status: 'gaps_filled' }))
    await fillGaps(uploadId)

    // Get final draft
    mockGet.mockResolvedValueOnce(ok({
      title: 'Improved Paper',
      sections: [{ heading: 'Abstract', content: 'Better abstract' }],
      citations: [{ id: 'c1', title: 'New Reference' }],
      metadata: { word_count: 6000 },
    }))
    const draftRes = await getDraft(uploadId)
    expect(draftRes.data.data.citations).toHaveLength(1)
  })

  it('Simulation + Mirofish flow: create sim → run → graph → scoreboard → snapshot', async () => {
    const { createSimulation, startSimulation, getSimulationStatus } = await import('@/api/simulation')
    const { getGraphSnapshot, getScoreboard, getStances, createSnapshot } = await import('@/api/mirofish')

    // Create simulation
    mockPost.mockResolvedValueOnce(ok({ simulation_id: 'sim_cross_001' }))
    const simRes = await createSimulation({ format: 'panel', topic: 'Cross-protocol test', agent_ids: ['a1', 'a2'] })
    const simId = simRes.data.data.simulation_id

    // Start
    mockPost.mockResolvedValueOnce(ok({ status: 'running' }))
    await startSimulation(simId)

    // Check status — completed
    mockGet.mockResolvedValueOnce(ok({ id: simId, status: 'completed', current_round: 3, total_rounds: 3 }))
    const statusRes = await getSimulationStatus(simId)
    expect(statusRes.data.data.status).toBe('completed')

    // Knowledge graph
    mockGet.mockResolvedValueOnce(ok({ nodes: [{ id: 'n1', label: 'A', type: 'concept' }], links: [], round: 3 }))
    const graphRes = await getGraphSnapshot(simId, 3)
    expect(graphRes.data.data.nodes).toHaveLength(1)

    // Scoreboard
    mockGet.mockResolvedValueOnce(ok([{ agent_id: 'a1', agent_name: 'Dr. A', scores: { clarity: 9 }, total: 9, rank: 1 }]))
    const scoreRes = await getScoreboard(simId)
    expect(scoreRes.data.data[0]?.rank).toBe(1)

    // Stances
    mockGet.mockResolvedValueOnce(ok([{ agent_id: 'a1', agent_name: 'Dr. A', stance: 0.8, confidence: 0.95, history: [] }]))
    const stanceRes = await getStances(simId)
    expect(stanceRes.data.data[0]?.stance).toBe(0.8)

    // Create snapshot for handoff
    mockPost.mockResolvedValueOnce(ok({ id: 'snap_cross_001', simulation_id: simId, source_mode: 'research', created_at: '2026-03-21', data: {} }))
    const snapRes = await createSnapshot(simId)
    expect(snapRes.data.data.id).toBe('snap_cross_001')
  })
})

/**
 * Integration Tests — Full User Flows
 *
 * Tests the complete user journey: load dashboard → create project →
 * navigate to detail → see stages. Uses mocked API but real stores + router.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

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
    visible: false,
    requests: [],
    pendingCount: 0,
    errorCount: 0,
    okCount: 0,
    avgDuration: 0,
    toggle: vi.fn(),
    clear: vi.fn(),
  }),
}))

describe('Integration: Create Project Flow', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('starts pipeline and can load the new project', async () => {
    const mockAxios = (await import('axios')).default

    // Step 1: Start pipeline
    vi.mocked(mockAxios.post).mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          run_id: 'ais_run_integration_test',
          task_id: 'task_123',
          message: 'Pipeline started',
        },
      },
    })

    const { startPipeline } = await import('@/api/ais')
    const res = await startPipeline({
      research_idea: 'Integration test topic',
      sources: ['arxiv', 'pubmed'],
      max_papers: 20,
    })

    const runId = res.data.data.run_id
    expect(runId).toBe('ais_run_integration_test')

    // Step 2: Load the project in the pipeline store
    vi.mocked(mockAxios.get).mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          run_id: runId,
          type: 'ais',
          status: 'crawling',
          query: 'Integration test topic',
          source: 'platform',
          current_stage: 1,
          created_at: '2026-03-22T10:00:00',
          summary: { current_stage: 1, stages_total: 6 },
        },
      },
    })

    const { usePipelineStore } = await import('@/stores/pipeline')
    const pipeline = usePipelineStore()
    await pipeline.loadProject(runId)

    expect(pipeline.projectTitle).toBe('Integration test topic')
    expect(pipeline.projectStatus).toBe('crawling')
    expect(pipeline.stages['crawl']?.status).toBe('active')
    expect(pipeline.stages['debate']?.status).toBe('pending')
  })

  it('handles pipeline failure gracefully', async () => {
    const mockAxios = (await import('axios')).default

    vi.mocked(mockAxios.get).mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          run_id: 'ais_run_fail',
          type: 'ais',
          status: 'failed',
          query: 'Failing topic',
          source: 'platform',
          current_stage: 1,
          error: "'ingested' is not a valid IngestionStatus",
          summary: { current_stage: 1, stages_total: 6 },
        },
      },
    })

    const { usePipelineStore } = await import('@/stores/pipeline')
    const pipeline = usePipelineStore()
    await pipeline.loadProject('ais_run_fail')

    expect(pipeline.projectStatus).toBe('failed')
    expect(pipeline.projectError).toContain('IngestionStatus')
    expect(pipeline.stages['crawl']?.status).toBe('failed')
    expect(pipeline.stages['debate']?.status).toBe('pending')
    expect(pipeline.stages['experiment']?.status).toBe('pending')
  })
})

describe('Integration: Dashboard Load Flow', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads recent projects and system status concurrently', async () => {
    const mockAxios = (await import('axios')).default

    vi.mocked(mockAxios.get).mockImplementation(async (url: string) => {
      if (url.includes('/history/recent')) {
        return {
          data: {
            success: true,
            data: {
              items: [
                {
                  run_id: 'run1',
                  type: 'debate',
                  status: 'completed',
                  query: 'Topic 1',
                  source: 'cli',
                  created_at: '2026-03-21T10:00:00',
                },
                {
                  run_id: 'run2',
                  type: 'ais',
                  status: 'failed',
                  query: 'Topic 2',
                  source: 'platform',
                  created_at: '2026-03-22T10:00:00',
                },
              ],
            },
          },
        }
      }
      if (url.includes('/ais/providers')) {
        return {
          data: {
            success: true,
            data: {
              default_provider: 'anthropic',
              default_model: 'claude-sonnet-4-20250514',
              providers: { anthropic: { configured: true, default_model: 'claude-sonnet-4-20250514', models: [] } },
              cache: { total_entries: 10 },
            },
          },
        }
      }
      if (url.includes('/ais/tools')) {
        return {
          data: {
            success: true,
            data: {
              ai_scientist: { available: true },
              scienceclaw: { available: true },
            },
          },
        }
      }
      if (url.includes('/autoresearch/status')) {
        return {
          data: {
            success: true,
            data: { queue_depth: 0, daemon_status: 'stopped' },
          },
        }
      }
      return { data: { success: true, data: {} } }
    })

    const { useProjectsStore } = await import('@/stores/projects')
    const { useSystemStore } = await import('@/stores/system')

    const projects = useProjectsStore()
    const system = useSystemStore()

    // Simulate what CommandCenter.onMounted does — fetch projects + system info
    await Promise.all([
      projects.fetchRecent(10),
      system.fetchProviders(),
    ])
    // Then fetch tools + autoresearch (system.startPolling does this internally)
    await Promise.all([
      system.fetchTools(),
      system.fetchAutoResearchStatus(),
    ])

    // Projects loaded
    expect(projects.recent.length).toBe(2)
    expect(projects.recent[0]!.title).toBe('Topic 1')
    expect(projects.recent[1]!.title).toBe('Topic 2')
    expect(projects.error).toBeNull()

    // System loaded
    expect(system.backendOnline).toBe(true)
    expect(system.providers!.active_provider).toBe('anthropic')
    expect(system.tools.length).toBe(2)
    expect(system.autoResearchStatus!.daemon_status).toBe('stopped')
  })

  it('handles backend offline during dashboard load', async () => {
    const mockAxios = (await import('axios')).default

    vi.mocked(mockAxios.get).mockRejectedValue(new Error('Network Error'))

    const { useProjectsStore } = await import('@/stores/projects')
    const { useSystemStore } = await import('@/stores/system')

    const projects = useProjectsStore()
    const system = useSystemStore()

    await Promise.all([
      projects.fetchRecent(10),
      system.fetchProviders(),
    ])

    expect(projects.error).toContain('Backend unreachable')
    expect(projects.recent).toEqual([])
    expect(system.backendOnline).toBe(false)
  })
})

describe('Integration: History Pagination', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads paginated history with type filter', async () => {
    const mockAxios = (await import('axios')).default

    vi.mocked(mockAxios.get).mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          runs: [
            { run_id: 'run_debate1', type: 'debate', status: 'completed', query: 'Debate 1', source: 'cli', created_at: '2026-03-21T10:00:00' },
            { run_id: 'run_debate2', type: 'debate', status: 'completed', query: 'Debate 2', source: 'cli', created_at: '2026-03-20T10:00:00' },
          ],
          total: 15,
          page: 1,
          per_page: 20,
          total_pages: 1,
        },
      },
    })

    const { useProjectsStore } = await import('@/stores/projects')
    const projects = useProjectsStore()
    await projects.fetchAll({ type: 'debate', page: 1, per_page: 20 })

    expect(projects.all.length).toBe(2)
    expect(projects.totalCount).toBe(15)
    expect(projects.all[0]!.type).toBe('debate')
  })
})

describe('Integration: CLI Run Detail', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads CLI debate run with full data mapping', async () => {
    const mockAxios = (await import('axios')).default

    vi.mocked(mockAxios.get).mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          run_id: 'test_run_full',
          type: 'debate',
          status: 'completed',
          query: 'Full CLI debate run',
          source: 'cli',
          created_at: '2026-03-21T23:09:00',
          data: {
            debate: {
              agent_count: 6,
              agents: [
                { agent_id: 'a1', name: 'Dr. A', role: 'Experimentalist', stance: 'exploratory' },
                { agent_id: 'a2', name: 'Dr. B', role: 'Theoretician', stance: 'critical' },
                { agent_id: 'a3', name: 'Dr. C', role: 'Data Scientist', stance: 'neutral' },
                { agent_id: 'a4', name: 'Dr. D', role: 'Domain Expert', stance: 'supportive' },
                { agent_id: 'a5', name: 'Dr. E', role: 'Synthesizer', stance: 'integrative' },
                { agent_id: 'a6', name: 'Dr. F', role: 'Critic', stance: 'skeptical' },
              ],
              rounds: 2,
              transcript: [
                { agent: 'Dr. A', round: 1, content: 'First message' },
                { agent: 'Dr. B', round: 1, content: 'Response' },
              ],
            },
            ideas: [
              { id: 'idea1', title: 'Idea One', score: 0.9 },
              { id: 'idea2', title: 'Idea Two', score: 0.7 },
            ],
            validation: { overall_score: 0.82, checks: [] },
            ai_scientist: 'queued for experimentation',
          },
          summary: { agent_count: 6, rounds: 2, total_turns: 12 },
        },
      },
    })

    const { usePipelineStore } = await import('@/stores/pipeline')
    const pipeline = usePipelineStore()
    await pipeline.loadProject('test_run_full')

    // All mapped stages should be done
    expect(pipeline.stages['debate']?.status).toBe('done')
    expect(pipeline.stages['ideas']?.status).toBe('done')
    expect(pipeline.stages['validate']?.status).toBe('done')
    expect(pipeline.stages['experiment']?.status).toBe('done')

    // Unmapped stages should be pending
    expect(pipeline.stages['crawl']?.status).toBe('pending')
    expect(pipeline.stages['map']?.status).toBe('pending')
    expect(pipeline.stages['draft']?.status).toBe('pending')
    expect(pipeline.stages['rehab']?.status).toBe('pending')

    // Stage results should be accessible
    expect(pipeline.stageResults['debate']).toBeDefined()
    expect((pipeline.stageResults['debate'] as Record<string, unknown>).agent_count).toBe(6)
    expect(pipeline.stageResults['ideas']).toBeDefined()
    expect(Array.isArray(pipeline.stageResults['ideas'])).toBe(true)

    // Metrics
    expect(pipeline.stages['debate']?.metric).toContain('6 agents')
    expect(pipeline.stages['ideas']?.metric).toContain('2 ideas')
  })
})

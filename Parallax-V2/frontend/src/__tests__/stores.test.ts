/**
 * Pinia Store Unit Tests
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

describe('Debug Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('logs and resolves requests', async () => {
    const mod = await vi.importActual<typeof import('@/stores/debug')>('@/stores/debug')
    const store = mod.useDebugStore()

    expect(store.requests).toEqual([])

    const id = store.logRequest('GET', '/api/test')
    expect(id).toBeGreaterThan(0)
    expect(store.requests.length).toBe(1)
    expect(store.requests[0]!.status).toBe('pending')
    expect(store.pendingCount).toBe(1)

    store.resolveRequest(id, 200, 512)
    expect(store.requests[0]!.status).toBe('ok')
    expect(store.requests[0]!.statusCode).toBe(200)
    expect(store.okCount).toBe(1)
    expect(store.pendingCount).toBe(0)
  })

  it('logs and rejects requests', async () => {
    const mod = await vi.importActual<typeof import('@/stores/debug')>('@/stores/debug')
    const store = mod.useDebugStore()

    const id = store.logRequest('POST', '/api/ais/start')
    store.rejectRequest(id, 'Timeout', 504)
    expect(store.requests[0]!.status).toBe('error')
    expect(store.requests[0]!.error).toBe('Timeout')
    expect(store.errorCount).toBe(1)
  })

  it('computes avgDuration', async () => {
    const mod = await vi.importActual<typeof import('@/stores/debug')>('@/stores/debug')
    const store = mod.useDebugStore()

    expect(store.avgDuration).toBe(0)
    const id1 = store.logRequest('GET', '/a')
    store.resolveRequest(id1, 200)
    expect(store.avgDuration).toBeGreaterThanOrEqual(0)
  })

  it('trims to maxLogs (50)', async () => {
    const mod = await vi.importActual<typeof import('@/stores/debug')>('@/stores/debug')
    const store = mod.useDebugStore()

    for (let i = 0; i < 60; i++) {
      store.logRequest('GET', `/api/test/${i}`)
    }
    expect(store.requests.length).toBe(50)
  })

  it('clears all requests', async () => {
    const mod = await vi.importActual<typeof import('@/stores/debug')>('@/stores/debug')
    const store = mod.useDebugStore()

    store.logRequest('GET', '/test')
    store.clear()
    expect(store.requests.length).toBe(0)
  })

  it('toggles visibility', async () => {
    const mod = await vi.importActual<typeof import('@/stores/debug')>('@/stores/debug')
    const store = mod.useDebugStore()

    expect(store.visible).toBe(false)
    store.toggle()
    expect(store.visible).toBe(true)
    store.toggle()
    expect(store.visible).toBe(false)
  })
})

describe('UI Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('has default theme and locale', async () => {
    const { useUiStore } = await import('@/stores/ui')
    const store = useUiStore()

    expect(['light', 'dark']).toContain(store.theme)
    expect(store.locale).toBe('en')
    expect(store.sidebarOpen).toBe(true)
  })

  it('toggles theme', async () => {
    const { useUiStore } = await import('@/stores/ui')
    const store = useUiStore()

    const initial = store.theme
    store.toggleTheme()
    expect(store.theme).not.toBe(initial)
    store.toggleTheme()
    expect(store.theme).toBe(initial)
  })

  it('toggles sidebar', async () => {
    const { useUiStore } = await import('@/stores/ui')
    const store = useUiStore()

    store.toggleSidebar()
    expect(store.sidebarOpen).toBe(false)
    store.toggleSidebar()
    expect(store.sidebarOpen).toBe(true)
  })
})

describe('Pipeline Store — computed', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('calculates progressPercent from completed stages', async () => {
    const { usePipelineStore } = await import('@/stores/pipeline')
    const mockAxios = (await import('axios')).default

    vi.mocked(mockAxios.get).mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          run_id: 'test_run',
          type: 'debate',
          status: 'completed',
          query: 'test',
          source: 'cli',
          data: {
            debate: { agent_count: 4, rounds: 2 },
            ideas: [{ id: '1', title: 'idea1' }],
          },
          summary: { agent_count: 4, rounds: 2 },
        },
      },
    })

    const store = usePipelineStore()
    await store.loadProject('test_run')

    expect(store.completedStageCount).toBe(2)
    expect(store.progressPercent).toBe(22)
  })

  it('clearProject resets all state', async () => {
    const { usePipelineStore } = await import('@/stores/pipeline')
    const store = usePipelineStore()
    store.clearProject()

    expect(store.activeRunId).toBeNull()
    expect(store.projectTitle).toBe('')
    expect(store.projectStatus).toBe('')
    expect(store.projectError).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })
})

describe('System Store — fetch methods', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('fetchProviders sets backendOnline on success', async () => {
    const { useSystemStore } = await import('@/stores/system')
    const mockAxios = (await import('axios')).default

    vi.mocked(mockAxios.get).mockResolvedValueOnce({
      data: { success: true, data: { default_provider: 'test', default_model: 'test-model', providers: {}, cache: { total_entries: 0 } } },
    })

    const store = useSystemStore()
    await store.fetchProviders()

    expect(store.backendOnline).toBe(true)
    expect(store.providers!.active_provider).toBe('test')
  })

  it('stopPolling clears interval without error', async () => {
    const { useSystemStore } = await import('@/stores/system')
    const store = useSystemStore()
    // Should not throw even when no polling is active
    store.stopPolling()
  })
})

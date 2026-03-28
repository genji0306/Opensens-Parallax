import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { ToolStatus, AutoResearchStatus } from '@/types/api'
import service, { STATUS_TIMEOUT } from '@/api/client'

const POLL_INTERVAL_MS = 30_000

/** Normalized provider info after mapping from backend shape */
export interface NormalizedProviderInfo {
  active_provider: string
  active_model: string
  providers: Record<string, { configured: boolean; default_model: string; models: string[] }>
  cache_entries: number
  proxy?: { url: string; status: string }
}

export const useSystemStore = defineStore('system', () => {
  const providers = ref<NormalizedProviderInfo | null>(null)
  const tools = ref<ToolStatus[]>([])
  const autoResearchStatus = ref<AutoResearchStatus | null>(null)
  const sessionCost = ref(0)
  const loading = ref(false)
  const backendOnline = ref(false)

  let pollHandle: ReturnType<typeof setInterval> | null = null
  let controller: AbortController | null = null

  async function fetchProviders(signal?: AbortSignal): Promise<void> {
    try {
      const res = await service.get('/api/research/ais/providers', {
        timeout: STATUS_TIMEOUT,
        signal,
      })
      if (res.data?.success !== false) {
        const raw = res.data?.data ?? res.data
        // Backend returns: { default_provider, default_model, providers: {...}, cache: {...}, tiers: {...} }
        const p = raw as Record<string, unknown>
        const proxyConfig = p.proxy
        providers.value = {
          active_provider: (p.default_provider ?? p.active_provider ?? 'unknown') as string,
          active_model: (p.default_model ?? p.active_model ?? 'unknown') as string,
          providers: (p.providers ?? {}) as NormalizedProviderInfo['providers'],
          cache_entries: ((p.cache as Record<string, unknown>)?.total_entries ?? 0) as number,
          proxy: proxyConfig
            ? {
                url: ((proxyConfig as Record<string, unknown>).url as string) ?? '',
                status: ((proxyConfig as Record<string, unknown>).status as string) ?? 'unknown',
              }
            : undefined,
        }
        backendOnline.value = true
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      providers.value = null
      backendOnline.value = false
    }
  }

  async function fetchTools(signal?: AbortSignal): Promise<void> {
    try {
      const res = await service.get('/api/research/ais/tools', {
        timeout: STATUS_TIMEOUT,
        signal,
      })
      const raw = res.data?.data ?? res.data
      // Backend returns { ai_scientist: { available, ... }, autoresearch: { ... }, scienceclaw: { ... } }
      // Normalize to ToolStatus[]
      if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
        const entries = Object.entries(raw as Record<string, unknown>)
        tools.value = entries.map(([name, info]) => {
          const obj = (info ?? {}) as Record<string, unknown>
          let status: 'online' | 'degraded' | 'offline' = 'offline'
          if (obj.available === true || obj.status === 'online' || obj.status === 'ok') {
            status = 'online'
          } else if (obj.status === 'degraded' || obj.available === 'partial') {
            status = 'degraded'
          }
          return {
            name,
            status,
            detail: obj.detail as string | undefined,
          }
        })
      } else if (Array.isArray(raw)) {
        tools.value = raw as ToolStatus[]
      }
    } catch {
      // Non-critical
    }
  }

  async function fetchAutoResearchStatus(signal?: AbortSignal): Promise<void> {
    try {
      const res = await service.get('/api/research/ais/autoresearch/status', {
        timeout: STATUS_TIMEOUT,
        signal,
      })
      const raw = res.data?.data ?? res.data
      if (raw && typeof raw === 'object') {
        const obj = raw as Record<string, unknown>
        autoResearchStatus.value = {
          queue_depth: (obj.queue_depth ?? obj.queued ?? 0) as number,
          active_run: obj.active_run as string | undefined,
          daemon_status: (obj.daemon_status ?? obj.status ?? 'stopped') as AutoResearchStatus['daemon_status'],
        }
      }
    } catch {
      // Non-critical
    }
  }

  /** Update session cost from the active pipeline run's cost estimate */
  function updateSessionCost(): void {
    try {
      // Import lazily to avoid circular dependency at module load time
      const { usePipelineStore } = require('@/stores/pipeline') as typeof import('@/stores/pipeline')
      const pipeline = usePipelineStore()
      if (pipeline.costEstimate && pipeline.costEstimate.total > 0) {
        sessionCost.value = pipeline.costEstimate.total
      }
    } catch {
      // Pipeline store not yet available — no-op
    }
  }

  async function pollAll(): Promise<void> {
    controller?.abort()
    controller = new AbortController()
    const signal = controller.signal

    // Provider first — if offline, skip the rest
    await fetchProviders(signal)
    if (signal.aborted) return
    if (backendOnline.value) {
      await Promise.allSettled([
        fetchTools(signal),
        fetchAutoResearchStatus(signal),
      ])
    }
    // Sync session cost from pipeline store on each poll
    updateSessionCost()
  }

  function startPolling(): void {
    if (pollHandle) return
    loading.value = true
    pollAll().finally(() => {
      loading.value = false
    })
    pollHandle = setInterval(pollAll, POLL_INTERVAL_MS)
  }

  function stopPolling(): void {
    if (pollHandle) {
      clearInterval(pollHandle)
      pollHandle = null
    }
    controller?.abort()
    controller = null
  }

  return {
    providers,
    tools,
    autoResearchStatus,
    sessionCost,
    loading,
    backendOnline,
    fetchProviders,
    fetchTools,
    fetchAutoResearchStatus,
    startPolling,
    stopPolling,
  }
})

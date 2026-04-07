import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { ProjectSummary } from '@/types/pipeline'
import { normalizeStageId } from '@/types/pipeline'
import { getRecentActivity, getHistoryRuns } from '@/api/ais'

export interface FetchAllParams {
  page?: number
  per_page?: number
  type?: string
  status?: string
  q?: string
}

export const useProjectsStore = defineStore('projects', () => {
  const recent = ref<ProjectSummary[]>([])
  const all = ref<ProjectSummary[]>([])
  const totalCount = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value)
  }

  function normalizeProject(item: unknown): ProjectSummary {
    const raw = item as Record<string, unknown>
    const type = (raw.type ?? 'debate') as ProjectSummary['type']
    const runId = (raw.run_id ?? raw.id ?? raw.upload_id ?? raw.report_id ?? '') as string
    const summary = isRecord(raw.summary) ? raw.summary : null
    const currentStage = normalizeStageId(raw.current_stage ?? summary?.current_stage)

    return {
      id: runId,
      run_id: runId,
      title: (raw.title ?? raw.query ?? '') as string,
      topic: (raw.topic ?? raw.query ?? '') as string,
      type,
      status: (raw.status ?? 'unknown') as string,
      current_stage: currentStage,
      created_at: (raw.created_at ?? '') as string,
      updated_at: (raw.updated_at ?? raw.created_at ?? '') as string,
      stage_results: raw.stage_results as ProjectSummary['stage_results'],
      simulation_id: (raw.simulation_id ?? raw.run_id) as string | undefined,
      upload_id: (raw.upload_id ?? (type === 'paper' || type === 'paper_rehab' ? runId : undefined)) as string | undefined,
    } satisfies ProjectSummary
  }

  async function fetchRecent(limit = 10): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const res = await getRecentActivity(limit)
      const payload = res.data?.data
      // Backend returns { items: [...] } or a raw array
      let items: unknown[]
      if (payload && typeof payload === 'object' && 'items' in payload) {
        items = (payload as { items: unknown[] }).items ?? []
      } else if (Array.isArray(payload)) {
        items = payload
      } else {
        items = []
      }
      // Normalize CLI runs: map `query` → `topic`, ensure `run_id` exists
      recent.value = items.map(normalizeProject)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load projects'
      if (msg.includes('Network Error') || msg.includes('timeout')) {
        error.value = 'Backend unreachable — start the Flask server on :5002'
      } else {
        error.value = msg
      }
      recent.value = []
    } finally {
      loading.value = false
    }
  }

  async function fetchAll(params?: FetchAllParams): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const res = await getHistoryRuns(params as { type?: string; page?: number; per_page?: number })
      const payload = res.data?.data
      if (payload && typeof payload === 'object') {
        const p = payload as Record<string, unknown>
        const runs = (p.runs ?? p.items ?? []) as unknown[]
        all.value = runs.map(normalizeProject)
        totalCount.value = (p.total as number) ?? runs.length
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load history'
      if (msg.includes('Network Error') || msg.includes('timeout')) {
        error.value = 'Backend unreachable — start the Flask server on :5002'
      } else {
        error.value = msg
      }
    } finally {
      loading.value = false
    }
  }

  async function refreshAll(): Promise<void> {
    await fetchAll()
  }

  return {
    recent,
    all,
    totalCount,
    loading,
    error,
    fetchRecent,
    fetchAll,
    refreshAll,
  }
})

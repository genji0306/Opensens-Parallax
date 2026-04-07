import service, { requestWithRetry } from './client'
import type { AxiosResponse } from 'axios'
import type { ApiResponse, TaskStatus } from '@/types/api'

// ── Local Types ────────────────────────────────────────────────────────

interface IngestionParams {
  query: string
  sources: string[]
  date_from?: string
  date_to?: string
  max_results?: number
}

interface Paper {
  doi: string
  title: string
  abstract?: string
  authors: string[]
  year?: number
  source: string
  topics?: string[]
}

interface Topic {
  id: string
  name: string
  paper_count: number
  children?: Topic[]
}

interface ResearchMapNode {
  id: string
  label: string
  type: string
  connections: string[]
}

interface ResearchGap {
  id: string
  description: string
  score: number
  related_topics: string[]
}

interface ResearchStats {
  total_papers: number
  total_topics: number
  total_agents: number
  total_simulations: number
  sources: Record<string, number>
}

interface ListPapersParams {
  source?: string
  topic_id?: string
  limit?: number
  offset?: number
}

interface ListTopicsParams {
  tree?: boolean
}

// ── Ingestion ──────────────────────────────────────────────────────────

/**
 * Start an academic paper ingestion job.
 */
export function startIngestion(
  data: IngestionParams,
): Promise<AxiosResponse<ApiResponse<{ task_id: string }>>> {
  return requestWithRetry(() => service.post('/api/research/ingest', data), 3, 1000)
}

/**
 * Check ingestion task progress.
 */
export function getIngestionStatus(
  taskId: string,
): Promise<AxiosResponse<ApiResponse<TaskStatus>>> {
  return service.get(`/api/research/ingest/${taskId}/status`)
}

// ── Papers ─────────────────────────────────────────────────────────────

/**
 * List papers with optional filters.
 */
export function listPapers(
  params: ListPapersParams = {},
): Promise<AxiosResponse<ApiResponse<Paper[]>>> {
  return service.get('/api/research/papers', { params })
}

/**
 * Get a single paper by DOI.
 */
export function getPaper(
  doi: string,
): Promise<AxiosResponse<ApiResponse<Paper>>> {
  return service.get(`/api/research/papers/${encodeURIComponent(doi)}`)
}

// ── Topics ─────────────────────────────────────────────────────────────

/**
 * List all topics (flat or tree).
 */
export function listTopics(
  params: ListTopicsParams = {},
): Promise<AxiosResponse<ApiResponse<Topic[]>>> {
  return service.get('/api/research/topics', { params })
}

/**
 * Get topic details.
 */
export function getTopic(
  topicId: string,
): Promise<AxiosResponse<ApiResponse<Topic>>> {
  return service.get(`/api/research/topics/${topicId}`)
}

/**
 * Get papers under a specific topic.
 */
export function getTopicPapers(
  topicId: string,
): Promise<AxiosResponse<ApiResponse<Paper[]>>> {
  return service.get(`/api/research/topics/${topicId}/papers`)
}

// ── Mapping & Gaps ─────────────────────────────────────────────────────

/**
 * Get the full research landscape map.
 */
export function getResearchMap(
  params: { query?: string; run_id?: string } = {},
): Promise<AxiosResponse<ApiResponse<{ nodes: ResearchMapNode[] }>>> {
  return service.get('/api/research/map', { params, timeout: 30_000 })
}

/**
 * Get identified research gaps.
 */
export function getResearchGaps(
  params: { min_score?: number; run_id?: string } = {},
): Promise<AxiosResponse<ApiResponse<ResearchGap[]>>> {
  return service.get('/api/research/gaps', { params })
}

// ── Stats ──────────────────────────────────────────────────────────────

/**
 * Get research data store statistics.
 */
export function getResearchStats(): Promise<AxiosResponse<ApiResponse<ResearchStats>>> {
  return service.get('/api/research/stats')
}

// ── Polling Helper ─────────────────────────────────────────────────────

/**
 * Poll an ingestion task until it completes or fails.
 */
export function pollIngestion(
  taskId: string,
  onProgress?: (task: TaskStatus) => void,
  interval = 2000,
): Promise<TaskStatus> {
  return new Promise((resolve, reject) => {
    const check = async () => {
      try {
        const res = await getIngestionStatus(taskId)
        const task = res.data?.data || (res.data as unknown as TaskStatus)

        if (onProgress) onProgress(task)

        if (task.status === 'completed') {
          resolve(task)
          return
        }
        if (task.status === 'failed') {
          reject(new Error(task.error || 'Ingestion failed'))
          return
        }

        setTimeout(check, interval)
      } catch (err) {
        reject(err)
      }
    }
    check()
  })
}

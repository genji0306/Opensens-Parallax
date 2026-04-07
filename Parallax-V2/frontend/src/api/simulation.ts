import service, { requestWithRetry } from './client'
import type { AxiosResponse } from 'axios'
import type { ApiResponse, TaskStatus } from '@/types/api'

// ── Local Types ────────────────────────────────────────────────────────

interface GenerateAgentsParams {
  topic_id?: string
  agents_per_cluster?: number
  role_distribution?: Record<string, number>
}

interface AgentProfile {
  id: string
  name: string
  role: string
  expertise: string[]
  llm_provider?: string
  llm_model?: string
  skills?: string[]
  is_super_agent?: boolean
}

interface ConfigureAgentParams {
  llm_provider?: string
  llm_model?: string
  skills?: string[]
  is_super_agent?: boolean
}

interface ModelInfo {
  provider: string
  models: Array<{ id: string; name: string }>
}

interface SkillInfo {
  id: string
  name: string
  category: string
  description?: string
}

interface DiscussionFormat {
  id: string
  name: string
  description: string
}

interface CreateSimulationParams {
  format: string
  topic: string
  agent_ids: string[]
  max_rounds?: number
}

interface SimulationStatus {
  id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  current_round?: number
  total_rounds?: number
  error?: string
}

interface TranscriptEntry {
  round: number
  agent: string
  content: string
  timestamp?: string
}

interface SimulationSummary {
  id: string
  format: string
  topic: string
  status: string
  created_at: string
}

interface ChatResponse {
  reply: string
  agent_id?: string
  context?: Record<string, unknown>
}

interface ForkResult {
  simulation_id: string
  forked_from: string
  from_round: number
}

interface ReportType {
  id: string
  name: string
  description: string
}

interface ReportStatus extends TaskStatus {
  report_id?: string
}

interface ReportData {
  id: string
  type: string
  content: Record<string, unknown>
  created_at: string
}

// ── Agent Generation ───────────────────────────────────────────────────

/**
 * Start researcher agent generation from topic clusters.
 */
export function generateAgents(
  data: GenerateAgentsParams,
): Promise<AxiosResponse<ApiResponse<{ task_id: string }>>> {
  return requestWithRetry(() => service.post('/api/research/agents/generate', data), 3, 1000)
}

/**
 * Check agent generation task progress.
 */
export function getAgentGenerationStatus(
  taskId: string,
): Promise<AxiosResponse<ApiResponse<TaskStatus>>> {
  return service.get(`/api/research/agents/generate/${taskId}/status`)
}

/**
 * List generated researcher agents.
 */
export function listAgents(
  params: { topic_id?: string } = {},
): Promise<AxiosResponse<ApiResponse<AgentProfile[]>>> {
  return service.get('/api/research/agents', { params })
}

/**
 * Get a single agent profile.
 */
export function getAgent(
  agentId: string,
): Promise<AxiosResponse<ApiResponse<AgentProfile>>> {
  return service.get(`/api/research/agents/${agentId}`)
}

/**
 * Update an agent's model, skills, or super-agent configuration.
 */
export function configureAgent(
  agentId: string,
  data: ConfigureAgentParams,
): Promise<AxiosResponse<ApiResponse<AgentProfile>>> {
  return service.patch(`/api/research/agents/${agentId}/configure`, data)
}

// ── Models & Skills ────────────────────────────────────────────────────

/**
 * List available LLM providers and their models.
 */
export function listModels(): Promise<AxiosResponse<ApiResponse<ModelInfo[]>>> {
  return service.get('/api/research/models')
}

/**
 * List available scientific skills.
 */
export function listSkills(
  category: string | null = null,
): Promise<AxiosResponse<ApiResponse<SkillInfo[]>>> {
  const params = category ? { category } : {}
  return service.get('/api/research/skills', { params })
}

// ── Simulation ─────────────────────────────────────────────────────────

/**
 * List available discussion formats.
 */
export function listFormats(): Promise<AxiosResponse<ApiResponse<DiscussionFormat[]>>> {
  return service.get('/api/research/simulate/formats')
}

/**
 * Create a new discussion simulation.
 */
export function createSimulation(
  data: CreateSimulationParams,
): Promise<AxiosResponse<ApiResponse<{ simulation_id: string }>>> {
  return requestWithRetry(() => service.post('/api/research/simulate', data), 3, 1000)
}

/**
 * Start a created simulation.
 */
export function startSimulation(
  simulationId: string,
): Promise<AxiosResponse<ApiResponse<{ status: string }>>> {
  return requestWithRetry(
    () => service.post(`/api/research/simulate/${simulationId}/start`),
    3,
    1000,
  )
}

/**
 * Get simulation status.
 */
export function getSimulationStatus(
  simulationId: string,
): Promise<AxiosResponse<ApiResponse<SimulationStatus>>> {
  return service.get(`/api/research/simulate/${simulationId}/status`)
}

/**
 * Get discussion transcript.
 */
export function getTranscript(
  simulationId: string,
  round: number | null = null,
): Promise<AxiosResponse<ApiResponse<TranscriptEntry[]>>> {
  const params = round !== null ? { round } : {}
  return service.get(`/api/research/simulate/${simulationId}/transcript`, { params })
}

/**
 * Inject a paper into a running longitudinal simulation.
 */
export function injectPaper(
  simulationId: string,
  doi: string,
): Promise<AxiosResponse<ApiResponse<{ status: string }>>> {
  return service.post(`/api/research/simulate/${simulationId}/inject`, { doi })
}

/**
 * List all simulations.
 */
export function listSimulations(): Promise<AxiosResponse<ApiResponse<SimulationSummary[]>>> {
  return service.get('/api/research/simulate')
}

// ── Deep Interaction ───────────────────────────────────────────────────

/**
 * Chat with a specific agent post-simulation.
 */
export function chatWithAgent(
  simulationId: string,
  agentId: string,
  message: string,
): Promise<AxiosResponse<ApiResponse<ChatResponse>>> {
  return service.post(`/api/research/simulate/${simulationId}/chat`, {
    agent_id: agentId,
    message,
  })
}

/**
 * Chat with a generated report's ReportAgent.
 */
export function chatWithReport(
  reportId: string,
  message: string,
): Promise<AxiosResponse<ApiResponse<ChatResponse>>> {
  return service.post(`/api/research/report/${reportId}/chat`, { message })
}

/**
 * Fork a simulation from a specific round with optional modifications.
 */
export function forkSimulation(
  simulationId: string,
  fromRound: number,
  modifications: Record<string, unknown> = {},
): Promise<AxiosResponse<ApiResponse<ForkResult>>> {
  return service.post(`/api/research/simulate/${simulationId}/fork`, {
    from_round: fromRound,
    modifications,
  })
}

// ── Polling Helpers ────────────────────────────────────────────────────

/**
 * Poll a simulation until completed or failed.
 */
export function pollSimulation(
  simulationId: string,
  onUpdate?: (sim: SimulationStatus) => void,
  interval = 3000,
): Promise<SimulationStatus> {
  return new Promise((resolve, reject) => {
    const check = async () => {
      try {
        const res = await getSimulationStatus(simulationId)
        const sim = res.data?.data || (res.data as unknown as SimulationStatus)

        if (onUpdate) onUpdate(sim)

        if (sim.status === 'completed') {
          resolve(sim)
          return
        }
        if (sim.status === 'failed') {
          reject(new Error(sim.error || 'Simulation failed'))
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

/**
 * Poll agent generation task.
 */
export function pollAgentGeneration(
  taskId: string,
  onProgress?: (task: TaskStatus) => void,
  interval = 2000,
): Promise<TaskStatus> {
  return new Promise((resolve, reject) => {
    const check = async () => {
      try {
        const res = await getAgentGenerationStatus(taskId)
        const task = res.data?.data || (res.data as unknown as TaskStatus)

        if (onProgress) onProgress(task)

        if (task.status === 'completed') {
          resolve(task)
          return
        }
        if (task.status === 'failed') {
          reject(new Error(task.error || 'Agent generation failed'))
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

// ── Report Export ──────────────────────────────────────────────────────

type ExportFormat = 'pptx' | 'audio' | 'markdown' | 'json'

/**
 * Export a report in a specified format.
 */
export function exportReport(
  reportId: string,
  format: ExportFormat = 'json',
): Promise<AxiosResponse<ApiResponse<unknown> | Blob>> {
  return service.get(`/api/research/report/${reportId}/export/${format}`, {
    responseType: format === 'json' ? 'json' : 'blob',
  })
}

/**
 * Generate structured infographic data for a report.
 */
export function generateInfographic(
  reportId: string,
): Promise<AxiosResponse<ApiResponse<Record<string, unknown>>>> {
  return service.post(`/api/research/report/${reportId}/infographic`)
}

/**
 * Trigger a file download from a Blob or string data.
 */
export function downloadFile(
  data: Blob | string,
  filename: string,
  mimeType = 'application/octet-stream',
): void {
  const blob = data instanceof Blob ? data : new Blob([data], { type: mimeType })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

// ── Reports ────────────────────────────────────────────────────────────

/**
 * List available report types.
 */
export function listReportTypes(): Promise<AxiosResponse<ApiResponse<ReportType[]>>> {
  return service.get('/api/research/report/types')
}

/**
 * Generate a report from a simulation.
 */
export function generateReport(
  simulationId: string,
  data: { type?: 'evolution' | 'comparative'; topic_ids?: string[] } = {},
): Promise<AxiosResponse<ApiResponse<{ task_id: string }>>> {
  return requestWithRetry(
    () => service.post(`/api/research/report/${simulationId}`, data),
    3,
    1000,
  )
}

/**
 * Get a completed report.
 */
export function getReport(
  reportId: string,
  format: 'json' | 'markdown' = 'json',
): Promise<AxiosResponse<ApiResponse<ReportData>>> {
  return service.get(`/api/research/report/${reportId}/view`, { params: { format } })
}

/**
 * List all generated reports.
 */
export function listReports(): Promise<AxiosResponse<ApiResponse<ReportData[]>>> {
  return service.get('/api/research/reports')
}

/**
 * Poll report generation task.
 */
export function pollReport(
  simulationId: string,
  taskId: string,
  onProgress?: (task: ReportStatus) => void,
  interval = 2000,
): Promise<ReportStatus> {
  return new Promise((resolve, reject) => {
    const check = async () => {
      try {
        const res = await service.get<ApiResponse<ReportStatus>>(
          `/api/research/report/${simulationId}/status`,
          { params: { task_id: taskId } },
        )
        const task = res.data?.data || (res.data as unknown as ReportStatus)

        if (onProgress) onProgress(task)

        if (task.status === 'completed') {
          resolve(task)
          return
        }
        if (task.status === 'failed') {
          reject(new Error(task.error || 'Report generation failed'))
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

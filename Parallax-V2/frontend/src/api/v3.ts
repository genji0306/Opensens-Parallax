/**
 * V3 Gateway API client.
 *
 * Connects to the V3 Gateway (FastAPI on :5003) for project management,
 * workflow runs, phase execution, cost tracking, approvals, and DRVP events.
 */

import axios from 'axios'
import type { AxiosInstance } from 'axios'

// ── Types ──────────────────────────────────────────────────────────

/** V3 API response envelope (no `success` flag — uses HTTP status codes) */
interface V3Response<T = unknown> {
  data: T
}

export interface V3Project {
  project_id: string
  name: string
  description: string
  domain: 'academic' | 'experiment' | 'simulation' | 'damd' | 'hybrid'
  template_id: string | null
  owner_id: string
  budget_cap_usd: number
  budget_spent_usd: number
  status: 'active' | 'paused' | 'completed' | 'archived'
  created_at: string
  updated_at: string
}

export interface V3WorkflowRun {
  run_id: string
  project_id: string
  template_id: string | null
  config: Record<string, unknown>
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed'
  budget_spent_usd: number
  v2_run_id: string | null
  created_at: string
  updated_at: string
  phases?: V3Phase[]
  edges?: V3PhaseEdge[]
}

export interface V3Phase {
  phase_id: string
  run_id: string
  phase_type: string
  label: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'invalidated' | 'awaiting_approval'
  config: Record<string, unknown>
  inputs: Record<string, unknown>
  outputs: Record<string, unknown>
  assigned_agent: string | null
  model_config: Record<string, unknown>
  model_used: string
  cost_usd: number
  score: number | null
  error: string | null
  sort_order: number
  started_at: string | null
  completed_at: string | null
}

export interface V3PhaseEdge {
  edge_id: string
  run_id: string
  source_phase_id: string
  target_phase_id: string
  edge_type: 'dependency' | 'conditional' | 'optional' | 'feedback' | 'approval' | 'branch' | 'merge'
}

export interface V3GraphState {
  run_id: string
  phases: V3Phase[]
  edges: V3PhaseEdge[]
  summary: {
    total_phases: number
    completed: number
    running: number
    failed: number
    pending: number
    progress_pct: number
  }
}

export interface V3Template {
  template_id: string
  label: string
  domain: string
  description: string
  phase_count: number
  edge_count: number
}

export interface V3CostSummary {
  project_id?: string
  run_id?: string
  total_cost_usd: number
  total_tokens_in?: number
  total_tokens_out?: number
  entry_count?: number
  by_phase?: Record<string, { cost_usd: number; calls: number; models: Record<string, number> }>
}

export interface V3BudgetStatus {
  allowed: boolean
  remaining_usd: number
  spent_usd: number
  cap_usd: number
}

export interface V3CostEntry {
  entry_id: string
  project_id: string
  run_id: string | null
  phase_id: string | null
  agent_id: string | null
  source_system: string
  cost_type: string
  model_name: string | null
  tokens_in: number
  tokens_out: number
  cost_usd: number
  timestamp: string
}

export interface V3Approval {
  approval_id: string
  project_id: string
  run_id: string
  phase_id: string
  reason: string
  risk_class: 'low' | 'medium' | 'high' | 'critical'
  details: Record<string, unknown>
  status: 'pending' | 'approved' | 'denied' | 'expired'
  requested_by: string
  decided_by: string | null
  decided_at: string | null
  created_at: string
}

export interface V3AuditEntry {
  entry_id: string
  actor: string
  action: string
  resource_type: string
  resource_id: string
  details: Record<string, unknown>
  timestamp: string
}

export interface V3DRVPEvent {
  event_id: string
  event_type: string
  source_system: string
  project_id: string | null
  run_id: string | null
  phase_id: string | null
  agent_id: string | null
  payload: Record<string, unknown>
  timestamp: string
}

// ── Client ─────────────────────────────────────────────────────────

const v3: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_V3_BASE_URL || 'http://localhost:5003/api/v3',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

async function get<T>(url: string): Promise<T> {
  const res = await v3.get<V3Response<T>>(url)
  return res.data.data
}

async function post<T>(url: string, data?: unknown): Promise<T> {
  const res = await v3.post<V3Response<T>>(url, data)
  return res.data.data
}

async function patch<T>(url: string, data?: unknown): Promise<T> {
  const res = await v3.patch<V3Response<T>>(url, data)
  return res.data.data
}

async function put<T>(url: string, data?: unknown): Promise<T> {
  const res = await v3.put<V3Response<T>>(url, data)
  return res.data.data
}

// ── Projects ───────────────────────────────────────────────────────

export const v3Projects = {
  list: (status?: string) =>
    get<V3Project[]>(`/projects${status ? `?status=${status}` : ''}`),

  get: (id: string) =>
    get<V3Project>(`/projects/${id}`),

  create: (data: { name: string; description?: string; domain?: string; template_id?: string; budget_cap_usd?: number }) =>
    post<V3Project>('/projects', data),

  update: (id: string, data: Partial<V3Project>) =>
    patch<V3Project>(`/projects/${id}`, data),
}

// ── Workflow Runs ──────────────────────────────────────────────────

export const v3Runs = {
  list: (projectId?: string, status?: string) => {
    const params = new URLSearchParams()
    if (projectId) params.set('project_id', projectId)
    if (status) params.set('status', status)
    const qs = params.toString()
    return get<V3WorkflowRun[]>(`/runs${qs ? `?${qs}` : ''}`)
  },

  get: (id: string) =>
    get<V3WorkflowRun>(`/runs/${id}`),

  create: (data: { project_id: string; template_id?: string; config?: Record<string, unknown> }) =>
    post<V3WorkflowRun>('/runs', data),

  graph: (id: string) =>
    get<V3GraphState>(`/runs/${id}/graph`),

  restart: (runId: string, phaseId: string) =>
    post<{ restarted_phase: string; invalidated: string[]; invalidated_count: number }>(
      `/runs/${runId}/restart/${phaseId}`
    ),
}

// ── Phases ─────────────────────────────────────────────────────────

export const v3Phases = {
  list: (runId: string) =>
    get<V3Phase[]>(`/phases/run/${runId}`),

  get: (id: string) =>
    get<V3Phase>(`/phases/${id}`),

  executeNext: (runId: string) =>
    post<{ executed: Array<{ phase_id: string; status: string; backend?: string }>; count: number }>(
      `/phases/run/${runId}/execute-next`
    ),

  complete: (id: string, data: { outputs?: Record<string, unknown>; score?: number; model_used?: string; cost_usd?: number }) =>
    post<{ phase_id: string; status: string }>(`/phases/${id}/complete`, data),

  fail: (id: string, error: string) =>
    post<{ phase_id: string; status: string }>(`/phases/${id}/fail`, { error }),

  setModel: (id: string, model: string) =>
    put<{ phase_id: string; model: string }>(`/phases/${id}/model`, { model }),

  setSettings: (id: string, settings: Record<string, unknown>) =>
    put<{ phase_id: string; config: Record<string, unknown> }>(`/phases/${id}/settings`, { settings }),
}

// ── Templates ──────────────────────────────────────────────────────

export const v3Templates = {
  list: () => get<V3Template[]>('/templates'),
}

// ── Costs ──────────────────────────────────────────────────────────

export const v3Costs = {
  project: (id: string) =>
    get<V3CostSummary>(`/costs/project/${id}`),

  run: (id: string) =>
    get<V3CostSummary>(`/costs/run/${id}`),

  budget: (projectId: string) =>
    get<V3BudgetStatus>(`/costs/project/${projectId}/budget`),

  entries: (projectId: string, limit = 50) =>
    get<V3CostEntry[]>(`/costs/project/${projectId}/entries?limit=${limit}`),
}

// ── Approvals ──────────────────────────────────────────────────────

export const v3Approvals = {
  list: (status = 'pending', projectId?: string) => {
    const params = new URLSearchParams({ status })
    if (projectId) params.set('project_id', projectId)
    return get<V3Approval[]>(`/approvals?${params}`)
  },

  get: (id: string) =>
    get<V3Approval>(`/approvals/${id}`),

  decide: (id: string, decision: 'approved' | 'denied', decidedBy = 'local', reason = '') =>
    post<V3Approval>(`/approvals/${id}/decide`, { decision, decided_by: decidedBy, reason }),
}

// ── Audit ──────────────────────────────────────────────────────────

export const v3Audit = {
  list: (filters?: { resource_type?: string; resource_id?: string; action?: string; limit?: number }) => {
    const params = new URLSearchParams()
    if (filters?.resource_type) params.set('resource_type', filters.resource_type)
    if (filters?.resource_id) params.set('resource_id', filters.resource_id)
    if (filters?.action) params.set('action', filters.action)
    if (filters?.limit) params.set('limit', String(filters.limit))
    return get<V3AuditEntry[]>(`/audit?${params}`)
  },
}

// ── DRVP Event Stream (SSE) ────────────────────────────────────────

export function createEventStream(
  onEvent: (event: V3DRVPEvent) => void,
  onError?: (error: Event) => void,
): EventSource {
  const baseUrl = import.meta.env.VITE_V3_BASE_URL || 'http://localhost:5003/api/v3'
  const source = new EventSource(`${baseUrl}/events/stream`)

  source.onmessage = (msg) => {
    try {
      const event: V3DRVPEvent = JSON.parse(msg.data)
      onEvent(event)
    } catch {
      // Ignore parse errors (keepalive, etc.)
    }
  }

  source.onerror = (err) => {
    onError?.(err)
  }

  return source
}

export default v3

import service from './client'
import type { AxiosResponse } from 'axios'
import type { ApiResponse } from '@/types/api'

// ── Local Types ────────────────────────────────────────────────────────

interface DebateFrame {
  simulation_id: string
  topic: string
  format: string
  agents: Array<{ id: string; name: string; role: string }>
  rules: Record<string, unknown>
}

interface GraphNode {
  id: string
  label: string
  type: string
  [key: string]: unknown
}

interface GraphLink {
  source: string
  target: string
  type: string
  [key: string]: unknown
}

interface GraphSnapshot {
  nodes: GraphNode[]
  links: GraphLink[]
  round?: number
}

interface GraphEvent {
  type: 'add_node' | 'add_link' | 'update_node' | 'remove_node'
  target: string
  data: Record<string, unknown>
  round: number
}

interface ScoreboardEntry {
  agent_id: string
  agent_name: string
  scores: Record<string, number>
  total: number
  rank: number
}

interface AnalystEntry {
  round: number
  narrative: string
  timestamp?: string
}

interface StanceData {
  agent_id: string
  agent_name: string
  stance: number
  confidence: number
  history: Array<{ round: number; stance: number }>
}

interface SessionSnapshot {
  id: string
  simulation_id: string
  source_mode: string
  created_at: string
  data: Record<string, unknown>
}

// ── Debate Frame ───────────────────────────────────────────────────────

/**
 * Get the orchestrator-generated debate frame for a simulation.
 */
export function getDebateFrame(
  simId: string,
): Promise<AxiosResponse<ApiResponse<DebateFrame>>> {
  return service.get(`/api/research/simulate/${simId}/frame`)
}

// ── Knowledge Graph ────────────────────────────────────────────────────

/**
 * Get a graph snapshot for a specific round (D3-ready format).
 */
export function getGraphSnapshot(
  simId: string,
  round: number | null = null,
): Promise<AxiosResponse<ApiResponse<GraphSnapshot>>> {
  return service.get(`/api/research/simulate/${simId}/graph`, {
    params: { ...(round !== null && { round }), format: 'd3' },
  })
}

/**
 * Get graph mutation events for a specific round.
 */
export function getGraphEvents(
  simId: string,
  round: number | null = null,
): Promise<AxiosResponse<ApiResponse<GraphEvent[]>>> {
  return service.get(`/api/research/simulate/${simId}/graph/events`, {
    params: round !== null ? { round } : {},
  })
}

// ── Scoreboard ─────────────────────────────────────────────────────────

/**
 * Get scoreboard metrics for a specific round or all rounds.
 */
export function getScoreboard(
  simId: string,
  round: number | null = null,
): Promise<AxiosResponse<ApiResponse<ScoreboardEntry[]>>> {
  return service.get(`/api/research/simulate/${simId}/scoreboard`, {
    params: round !== null ? { round } : {},
  })
}

// ── Analyst Feed ───────────────────────────────────────────────────────

/**
 * Get analyst narrator feed entries up to a specific round.
 */
export function getAnalystFeed(
  simId: string,
  maxRound: number | null = null,
): Promise<AxiosResponse<ApiResponse<AnalystEntry[]>>> {
  return service.get(`/api/research/simulate/${simId}/analyst-feed`, {
    params: maxRound !== null ? { max_round: maxRound } : {},
  })
}

// ── Stances ────────────────────────────────────────────────────────────

/**
 * Get agent stance data for the simulation.
 */
export function getStances(
  simId: string,
): Promise<AxiosResponse<ApiResponse<StanceData[]>>> {
  return service.get(`/api/research/simulate/${simId}/stances`)
}

// ── Session Snapshots ──────────────────────────────────────────────────

/**
 * Create a session snapshot for handoff to live mode.
 */
export function createSnapshot(
  simId: string,
  sourceMode: 'research' | 'live' = 'research',
): Promise<AxiosResponse<ApiResponse<SessionSnapshot>>> {
  return service.post(`/api/research/simulate/${simId}/snapshot`, { source_mode: sourceMode })
}

/**
 * Load a specific session snapshot.
 */
export function loadSnapshot(
  simId: string,
  snapshotId: string,
): Promise<AxiosResponse<ApiResponse<SessionSnapshot>>> {
  return service.get(`/api/research/simulate/${simId}/snapshot/${snapshotId}`)
}

/**
 * List all snapshots for a simulation.
 */
export function listSnapshots(
  simId: string,
): Promise<AxiosResponse<ApiResponse<SessionSnapshot[]>>> {
  return service.get(`/api/research/simulate/${simId}/snapshots`)
}

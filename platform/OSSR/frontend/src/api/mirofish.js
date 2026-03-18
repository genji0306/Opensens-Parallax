import service from './index'

// ── Debate Frame ────────────────────────────────────────────────────

/**
 * Get the orchestrator-generated debate frame for a simulation.
 * @param {string} simId
 */
export const getDebateFrame = (simId) =>
  service.get(`/api/research/simulate/${simId}/frame`)

// ── Knowledge Graph ─────────────────────────────────────────────────

/**
 * Get a graph snapshot for a specific round (D3-ready format).
 * @param {string} simId
 * @param {number|null} round - specific round or null for latest
 */
export const getGraphSnapshot = (simId, round = null) =>
  service.get(`/api/research/simulate/${simId}/graph`, {
    params: { ...(round !== null && { round }), format: 'd3' },
  })

/**
 * Get graph mutation events for a specific round.
 * @param {string} simId
 * @param {number|null} round
 */
export const getGraphEvents = (simId, round = null) =>
  service.get(`/api/research/simulate/${simId}/graph/events`, {
    params: round !== null ? { round } : {},
  })

// ── Scoreboard ──────────────────────────────────────────────────────

/**
 * Get scoreboard metrics for a specific round or all rounds.
 * @param {string} simId
 * @param {number|null} round
 */
export const getScoreboard = (simId, round = null) =>
  service.get(`/api/research/simulate/${simId}/scoreboard`, {
    params: round !== null ? { round } : {},
  })

// ── Analyst Feed ────────────────────────────────────────────────────

/**
 * Get analyst narrator feed entries up to a specific round.
 * @param {string} simId
 * @param {number|null} maxRound
 */
export const getAnalystFeed = (simId, maxRound = null) =>
  service.get(`/api/research/simulate/${simId}/analyst-feed`, {
    params: maxRound !== null ? { max_round: maxRound } : {},
  })

// ── Stances ─────────────────────────────────────────────────────────

/**
 * Get agent stance data for the simulation.
 * @param {string} simId
 */
export const getStances = (simId) =>
  service.get(`/api/research/simulate/${simId}/stances`)

// ── Session Snapshots ───────────────────────────────────────────────

/**
 * Create a session snapshot for handoff to live mode.
 * @param {string} simId
 * @param {string} sourceMode - 'research' or 'live'
 */
export const createSnapshot = (simId, sourceMode = 'research') =>
  service.post(`/api/research/simulate/${simId}/snapshot`, { source_mode: sourceMode })

/**
 * Load a specific session snapshot.
 * @param {string} simId
 * @param {string} snapshotId
 */
export const loadSnapshot = (simId, snapshotId) =>
  service.get(`/api/research/simulate/${simId}/snapshot/${snapshotId}`)

/**
 * List all snapshots for a simulation.
 * @param {string} simId
 */
export const listSnapshots = (simId) =>
  service.get(`/api/research/simulate/${simId}/snapshots`)

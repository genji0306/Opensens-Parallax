import service from './index'

// ── Agent AiS Pipeline ──────────────────────────────────────────────

/**
 * Start the full Agent AiS pipeline (Stages 1-2, then pauses for selection).
 * @param {Object} data - { research_idea, sources?, max_papers?, num_ideas?, num_reflections? }
 */
export const startPipeline = (data) => {
  return service.post('/api/research/ais/start', data)
}

/**
 * Poll pipeline run status.
 * @param {string} runId
 */
export const getPipelineStatus = (runId) => {
  return service.get(`/api/research/ais/${runId}/status`)
}

/**
 * Get Stage 2 ideas (ranked).
 * @param {string} runId
 */
export const getIdeas = (runId) => {
  return service.get(`/api/research/ais/${runId}/ideas`)
}

/**
 * Human selects a winning idea for Stage 3.
 * @param {string} runId
 * @param {string} ideaId
 */
export const selectIdea = (runId, ideaId) => {
  return service.post(`/api/research/ais/${runId}/select-idea`, { idea_id: ideaId })
}

/**
 * Start Stage 3: agent-to-agent debate.
 * @param {string} runId
 */
export const startDebate = (runId) => {
  return service.post(`/api/research/ais/${runId}/debate`)
}

/**
 * Stage 4: approve debate results, proceed to drafting.
 * @param {string} runId
 * @param {Object} data - { feedback? }
 */
export const approveDraft = (runId, data = {}) => {
  return service.post(`/api/research/ais/${runId}/approve`, data)
}

/**
 * Get Stage 5 paper draft.
 * @param {string} runId
 */
export const getDraft = (runId) => {
  return service.get(`/api/research/ais/${runId}/draft`)
}

/**
 * Export draft as markdown.
 * @param {string} runId
 * @param {string} format - 'markdown' | 'latex' | 'json'
 */
export const exportDraft = (runId, format = 'markdown') => {
  return service.get(`/api/research/ais/${runId}/export`, { params: { format } })
}

/**
 * List all pipeline runs.
 * @param {Object} params - { status?, limit? }
 */
export const listRuns = (params = {}) => {
  return service.get('/api/research/ais/runs', { params })
}

/**
 * Poll pipeline status until it reaches a target status or fails.
 * @param {string} runId
 * @param {string[]} targetStatuses
 * @param {Function} onProgress - callback with status data
 * @param {number} interval - ms between polls (default 3000)
 * @returns {Promise<Object>} final status data
 */
export const pollPipeline = async (runId, targetStatuses, onProgress, interval = 3000) => {
  const terminalStatuses = ['completed', 'failed', ...targetStatuses]
  while (true) {
    const res = await getPipelineStatus(runId)
    const data = res.data.data
    if (onProgress) onProgress(data)
    if (terminalStatuses.includes(data.status)) {
      return data
    }
    await new Promise(resolve => setTimeout(resolve, interval))
  }
}

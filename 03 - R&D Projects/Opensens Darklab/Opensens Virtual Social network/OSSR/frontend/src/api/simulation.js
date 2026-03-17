import service, { requestWithRetry } from './index'

// ── Agent Generation ─────────────────────────────────────────────────

/**
 * Start researcher agent generation from topic clusters.
 * @param {Object} data - { topic_id?, agents_per_cluster?, role_distribution? }
 */
export const generateAgents = (data) => {
  return requestWithRetry(() => service.post('/api/research/agents/generate', data), 3, 1000)
}

/**
 * Check agent generation task progress.
 * @param {string} taskId
 */
export const getAgentGenerationStatus = (taskId) => {
  return service.get(`/api/research/agents/generate/${taskId}/status`)
}

/**
 * List generated researcher agents.
 * @param {Object} params - { topic_id? }
 */
export const listAgents = (params = {}) => {
  return service.get('/api/research/agents', { params })
}

/**
 * Get a single agent profile.
 * @param {string} agentId
 */
export const getAgent = (agentId) => {
  return service.get(`/api/research/agents/${agentId}`)
}

/**
 * Update an agent's model, skills, or super-agent configuration.
 * @param {string} agentId
 * @param {Object} data - { llm_provider?, llm_model?, skills?, is_super_agent? }
 */
export const configureAgent = (agentId, data) => {
  return service.patch(`/api/research/agents/${agentId}/configure`, data)
}

// ── Models & Skills ─────────────────────────────────────────────────

/**
 * List available LLM providers and their models.
 */
export const listModels = () => {
  return service.get('/api/research/models')
}

/**
 * List available scientific skills.
 * @param {string} category - optional filter: 'database', 'package', 'analysis', 'integration'
 */
export const listSkills = (category = null) => {
  const params = category ? { category } : {}
  return service.get('/api/research/skills', { params })
}

// ── Simulation ───────────────────────────────────────────────────────

/**
 * List available discussion formats.
 */
export const listFormats = () => {
  return service.get('/api/research/simulate/formats')
}

/**
 * Create a new discussion simulation.
 * @param {Object} data - { format, topic, agent_ids, max_rounds? }
 */
export const createSimulation = (data) => {
  return requestWithRetry(() => service.post('/api/research/simulate', data), 3, 1000)
}

/**
 * Start a created simulation.
 * @param {string} simulationId
 */
export const startSimulation = (simulationId) => {
  return requestWithRetry(
    () => service.post(`/api/research/simulate/${simulationId}/start`),
    3, 1000
  )
}

/**
 * Get simulation status.
 * @param {string} simulationId
 */
export const getSimulationStatus = (simulationId) => {
  return service.get(`/api/research/simulate/${simulationId}/status`)
}

/**
 * Get discussion transcript.
 * @param {string} simulationId
 * @param {number} round - optional round filter
 */
export const getTranscript = (simulationId, round = null) => {
  const params = round !== null ? { round } : {}
  return service.get(`/api/research/simulate/${simulationId}/transcript`, { params })
}

/**
 * Inject a paper into a running longitudinal simulation.
 * @param {string} simulationId
 * @param {string} doi
 */
export const injectPaper = (simulationId, doi) => {
  return service.post(`/api/research/simulate/${simulationId}/inject`, { doi })
}

/**
 * List all simulations.
 */
export const listSimulations = () => {
  return service.get('/api/research/simulate')
}

// ── Deep Interaction ────────────────────────────────────────────────

/**
 * Chat with a specific agent post-simulation.
 * @param {string} simulationId
 * @param {string} agentId
 * @param {string} message
 */
export const chatWithAgent = (simulationId, agentId, message) => {
  return service.post(`/api/research/simulate/${simulationId}/chat`, {
    agent_id: agentId,
    message,
  })
}

/**
 * Chat with a generated report's ReportAgent.
 * @param {string} reportId
 * @param {string} message
 */
export const chatWithReport = (reportId, message) => {
  return service.post(`/api/research/report/${reportId}/chat`, { message })
}

/**
 * Fork a simulation from a specific round with optional modifications.
 * @param {string} simulationId
 * @param {number} fromRound
 * @param {Object} modifications - { format?, max_rounds?, ... }
 */
export const forkSimulation = (simulationId, fromRound, modifications = {}) => {
  return service.post(`/api/research/simulate/${simulationId}/fork`, {
    from_round: fromRound,
    modifications,
  })
}

// ── Polling helper ───────────────────────────────────────────────────

/**
 * Poll a simulation until completed or failed.
 * @param {string} simulationId
 * @param {Function} onUpdate - callback({ status, current_round, ... })
 * @param {number} interval - ms (default 3000)
 */
export const pollSimulation = (simulationId, onUpdate, interval = 3000) => {
  return new Promise((resolve, reject) => {
    const check = async () => {
      try {
        const res = await getSimulationStatus(simulationId)
        const sim = res.data?.data || res.data

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
 * @param {string} taskId
 * @param {Function} onProgress
 * @param {number} interval
 */
// ── Report Export ───────────────────────────────────────────────────

/**
 * Export a report in a specified format.
 * @param {string} reportId
 * @param {string} format - 'pptx', 'audio', 'markdown', 'json'
 */
export const exportReport = (reportId, format = 'json') => {
  return service.get(`/api/research/report/${reportId}/export/${format}`, {
    responseType: format === 'json' ? 'json' : 'blob',
  })
}

/**
 * Generate structured infographic data for a report.
 * @param {string} reportId
 */
export const generateInfographic = (reportId) => {
  return service.post(`/api/research/report/${reportId}/infographic`)
}

/**
 * Trigger a file download from a Blob or string data.
 * @param {Blob|string} data
 * @param {string} filename
 * @param {string} mimeType
 */
export const downloadFile = (data, filename, mimeType = 'application/octet-stream') => {
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

// ── Reports ─────────────────────────────────────────────────────────

/**
 * List available report types.
 */
export const listReportTypes = () => {
  return service.get('/api/research/report/types')
}

/**
 * Generate a report from a simulation.
 * @param {string} simulationId
 * @param {Object} data - { type: 'evolution'|'comparative', topic_ids? }
 */
export const generateReport = (simulationId, data = {}) => {
  return requestWithRetry(
    () => service.post(`/api/research/report/${simulationId}`, data),
    3, 1000
  )
}

/**
 * Get a completed report.
 * @param {string} reportId
 * @param {string} format - 'json' or 'markdown'
 */
export const getReport = (reportId, format = 'json') => {
  return service.get(`/api/research/report/${reportId}/view`, { params: { format } })
}

/**
 * List all generated reports.
 */
export const listReports = () => {
  return service.get('/api/research/reports')
}

/**
 * Poll report generation task.
 * @param {string} simulationId
 * @param {string} taskId
 * @param {Function} onProgress
 * @param {number} interval
 */
export const pollReport = (simulationId, taskId, onProgress, interval = 2000) => {
  return new Promise((resolve, reject) => {
    const check = async () => {
      try {
        const res = await service.get(
          `/api/research/report/${simulationId}/status`,
          { params: { task_id: taskId } }
        )
        const task = res.data?.data || res.data

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

export const pollAgentGeneration = (taskId, onProgress, interval = 2000) => {
  return new Promise((resolve, reject) => {
    const check = async () => {
      try {
        const res = await getAgentGenerationStatus(taskId)
        const task = res.data?.data || res.data

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

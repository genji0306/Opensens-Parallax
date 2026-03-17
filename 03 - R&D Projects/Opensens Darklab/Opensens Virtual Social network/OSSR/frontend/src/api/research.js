import service, { requestWithRetry } from './index'

// ── Ingestion ────────────────────────────────────────────────────────

/**
 * Start an academic paper ingestion job.
 * @param {Object} data - { query, sources, date_from?, date_to?, max_results? }
 */
export const startIngestion = (data) => {
  return requestWithRetry(() => service.post('/api/research/ingest', data), 3, 1000)
}

/**
 * Check ingestion task progress.
 * @param {string} taskId
 */
export const getIngestionStatus = (taskId) => {
  return service.get(`/api/research/ingest/${taskId}/status`)
}

// ── Papers ───────────────────────────────────────────────────────────

/**
 * List papers with optional filters.
 * @param {Object} params - { source?, topic_id?, limit?, offset? }
 */
export const listPapers = (params = {}) => {
  return service.get('/api/research/papers', { params })
}

/**
 * Get a single paper by DOI.
 * @param {string} doi - URL-encoded DOI
 */
export const getPaper = (doi) => {
  return service.get(`/api/research/papers/${encodeURIComponent(doi)}`)
}

// ── Topics ───────────────────────────────────────────────────────────

/**
 * List all topics (flat or tree).
 * @param {Object} params - { tree? } — set tree=true for hierarchical view
 */
export const listTopics = (params = {}) => {
  return service.get('/api/research/topics', { params })
}

/**
 * Get topic details.
 * @param {string} topicId
 */
export const getTopic = (topicId) => {
  return service.get(`/api/research/topics/${topicId}`)
}

/**
 * Get papers under a specific topic.
 * @param {string} topicId
 */
export const getTopicPapers = (topicId) => {
  return service.get(`/api/research/topics/${topicId}/papers`)
}

// ── Mapping & Gaps (S3 endpoints) ────────────────────────────────────

/**
 * Get the full research landscape map.
 * @param {Object} params - { query? }
 */
export const getResearchMap = (params = {}) => {
  return service.get('/api/research/map', { params })
}

/**
 * Get identified research gaps.
 * @param {Object} params - { min_score? }
 */
export const getResearchGaps = (params = {}) => {
  return service.get('/api/research/gaps', { params })
}

// ── Stats ────────────────────────────────────────────────────────────

/**
 * Get research data store statistics.
 */
export const getResearchStats = () => {
  return service.get('/api/research/stats')
}

// ── Polling helper ───────────────────────────────────────────────────

/**
 * Poll an ingestion task until it completes or fails.
 * @param {string} taskId
 * @param {Function} onProgress - callback({ status, progress, message })
 * @param {number} interval - polling interval in ms (default 2000)
 * @returns {Promise<Object>} final task result
 */
export const pollIngestion = (taskId, onProgress, interval = 2000) => {
  return new Promise((resolve, reject) => {
    const check = async () => {
      try {
        const res = await getIngestionStatus(taskId)
        const task = res.data || res

        if (onProgress) {
          onProgress(task)
        }

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

import { ref, onUnmounted } from 'vue'
import { getSimulationStatus, getTranscript } from '../api/simulation'
import { getDebateFrame, getGraphSnapshot, getScoreboard, getAnalystFeed } from '../api/mirofish'

/**
 * Composable for streaming orchestrated simulation data via SSE.
 * Falls back to REST polling for completed simulations.
 *
 * @param {string} simId - Simulation ID
 * @returns {Object} Reactive refs for all Mirofish data
 */
export function useSimulationSSE(simId) {
  const frame = ref(null)
  const graphSnapshot = ref(null)
  const scoreboard = ref(null)
  const analystEntries = ref([])
  const transcript = ref([])
  const stances = ref([])
  const disagreements = ref([])
  const coalitions = ref([])
  const status = ref('connecting')
  const currentRound = ref(0)
  const maxRound = ref(0)
  const error = ref(null)

  let eventSource = null
  let reconnectTimeout = null

  function connect() {
    if (eventSource) eventSource.close()

    const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
    eventSource = new EventSource(`${baseUrl}/api/research/simulate/${simId}/stream`)

    eventSource.onopen = () => {
      status.value = 'live'
      error.value = null
    }

    // Debate frame (sent once at start)
    eventSource.addEventListener('frame', (e) => {
      try { frame.value = JSON.parse(e.data) } catch (err) { console.warn('SSE frame parse error:', err) }
    })

    // Agent turn
    eventSource.addEventListener('turn', (e) => {
      try {
        const turn = JSON.parse(e.data)
        transcript.value = [...transcript.value, turn]
      } catch (err) { console.warn('SSE turn parse error:', err) }
    })

    // Round lifecycle
    eventSource.addEventListener('round_start', (e) => {
      try {
        const data = JSON.parse(e.data)
        currentRound.value = data.round_num || data.round
        if (currentRound.value > maxRound.value) maxRound.value = currentRound.value
      } catch (err) { console.warn('SSE round_start parse error:', err) }
    })

    eventSource.addEventListener('round_end', (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.round_num > maxRound.value) maxRound.value = data.round_num
      } catch (err) { console.warn('SSE round_end parse error:', err) }
    })

    // Graph updates
    eventSource.addEventListener('graph_update', (e) => {
      try {
        const data = JSON.parse(e.data)
        graphSnapshot.value = data.snapshot || data
      } catch (err) { console.warn('SSE graph_update parse error:', err) }
    })

    // Scoreboard
    eventSource.addEventListener('scoreboard', (e) => {
      try { scoreboard.value = JSON.parse(e.data) } catch (err) { console.warn('SSE scoreboard parse error:', err) }
    })

    // Analyst narrative
    eventSource.addEventListener('analyst_note', (e) => {
      try {
        const entry = JSON.parse(e.data)
        analystEntries.value = [...analystEntries.value, entry]
      } catch (err) { console.warn('SSE analyst_note parse error:', err) }
    })

    // Stance updates
    eventSource.addEventListener('stance_update', (e) => {
      try {
        const data = JSON.parse(e.data)
        const newStances = Array.isArray(data.stances) ? data.stances : [data]
        stances.value = [...stances.value, ...newStances]
      } catch (err) { console.warn('SSE stance_update parse error:', err) }
    })

    // Conflicts
    eventSource.addEventListener('conflict', (e) => {
      try {
        disagreements.value = [...disagreements.value, JSON.parse(e.data)]
      } catch (err) { console.warn('SSE conflict parse error:', err) }
    })

    // Coalitions
    eventSource.addEventListener('coalition', (e) => {
      try {
        coalitions.value = [...coalitions.value, JSON.parse(e.data)]
      } catch (err) { console.warn('SSE coalition parse error:', err) }
    })

    // Simulation completed
    eventSource.addEventListener('completed', () => {
      status.value = 'completed'
      close()
    })

    eventSource.addEventListener('error_event', (e) => {
      try {
        const data = JSON.parse(e.data)
        error.value = data.error || 'Simulation error'
        status.value = 'error'
      } catch (err) { /* ignore */ }
    })

    eventSource.onerror = () => {
      if (status.value === 'completed') return
      status.value = 'reconnecting'
      close()
      reconnectTimeout = setTimeout(() => connect(), 3000)
    }
  }

  /**
   * Load all data via REST for completed simulations or replay mode.
   */
  async function loadFromRest() {
    status.value = 'loading'
    try {
      const [statusRes, frameRes, graphRes, scoreRes, feedRes, transcriptRes] = await Promise.allSettled([
        getSimulationStatus(simId),
        getDebateFrame(simId),
        getGraphSnapshot(simId),
        getScoreboard(simId),
        getAnalystFeed(simId),
        getTranscript(simId),
      ])

      const simData = statusRes.status === 'fulfilled' ? (statusRes.value.data?.data || statusRes.value.data) : null
      if (simData) {
        currentRound.value = simData.current_round || 0
        maxRound.value = simData.max_rounds || simData.current_round || 0
      }

      if (frameRes.status === 'fulfilled') {
        frame.value = frameRes.value.data?.data || frameRes.value.data
      }

      if (graphRes.status === 'fulfilled') {
        graphSnapshot.value = graphRes.value.data?.data || graphRes.value.data
      }

      if (scoreRes.status === 'fulfilled') {
        const scoreData = scoreRes.value.data?.data || scoreRes.value.data
        if (Array.isArray(scoreData)) {
          scoreboard.value = scoreData[scoreData.length - 1] || null
        } else {
          scoreboard.value = scoreData
        }
      }

      if (feedRes.status === 'fulfilled') {
        const feedData = feedRes.value.data?.data || feedRes.value.data
        analystEntries.value = Array.isArray(feedData) ? feedData : []
      }

      if (transcriptRes.status === 'fulfilled') {
        const tData = transcriptRes.value.data?.data || transcriptRes.value.data
        transcript.value = Array.isArray(tData) ? tData : tData?.turns || []
      }

      status.value = simData?.status === 'completed' ? 'completed' : (simData?.status || 'loaded')
    } catch (err) {
      error.value = err.message
      status.value = 'error'
    }
  }

  /**
   * Load graph snapshot for a specific round (for replay scrubbing).
   * @param {number} round
   */
  async function loadRound(round) {
    try {
      const [graphRes, scoreRes] = await Promise.all([
        getGraphSnapshot(simId, round),
        getScoreboard(simId, round),
      ])
      graphSnapshot.value = graphRes.data?.data || graphRes.data
      const scoreData = scoreRes.data?.data || scoreRes.data
      scoreboard.value = Array.isArray(scoreData) ? scoreData[scoreData.length - 1] : scoreData
    } catch (err) {
      console.warn('Failed to load round', round, err)
    }
  }

  /**
   * Initialize: check sim status, then connect SSE or load via REST.
   */
  async function init() {
    try {
      const res = await getSimulationStatus(simId)
      const simData = res.data?.data || res.data
      const simStatus = simData?.status

      if (simStatus === 'running') {
        await loadFromRest() // load existing data first
        connect() // then stream new events
      } else if (simStatus === 'completed' || simStatus === 'failed') {
        await loadFromRest()
      } else {
        // Not started yet — connect SSE and wait
        connect()
      }
    } catch (err) {
      error.value = err.message
      status.value = 'error'
    }
  }

  function close() {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }
  }

  onUnmounted(close)

  return {
    frame,
    graphSnapshot,
    scoreboard,
    analystEntries,
    transcript,
    stances,
    disagreements,
    coalitions,
    status,
    currentRound,
    maxRound,
    error,
    init,
    connect,
    loadFromRest,
    loadRound,
    close,
  }
}

<template>
  <div class="research-console">
    <!-- Header -->
    <div class="console-header">
      <div class="header-left">
        <button class="btn-back" @click="$router.push('/')">&#9664; Dashboard</button>
        <span class="console-title">Research Console</span>
        <span class="topic-label" v-if="frame">{{ frame.topic }}</span>
      </div>
      <div class="header-right">
        <span class="status-badge" :class="status">{{ status }}</span>
        <span class="round-badge" v-if="maxRound > 0">
          R{{ currentRound }}/{{ maxRound }}
        </span>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="status === 'connecting' || status === 'loading'" class="console-loading">
      <div class="loading-spinner"></div>
      <span>Loading simulation data...</span>
    </div>

    <!-- Error state -->
    <div v-else-if="status === 'error'" class="console-error">
      <span>Error: {{ error || 'Failed to load simulation' }}</span>
      <button class="btn-retry" @click="retryLoad">Retry</button>
    </div>

    <!-- Main 3-panel layout -->
    <div v-else class="console-body">
      <!-- Left Panel: Scoreboard -->
      <div class="panel-left">
        <ScoreboardPanel
          :frame="frame"
          :scoreboard="scoreboard"
          :currentRound="displayRound"
        />
      </div>

      <!-- Center Panel: Graph / Transcript / Replay -->
      <div class="panel-center">
        <div class="center-tabs">
          <button
            v-for="tab in ['graph', 'transcript', 'replay']"
            :key="tab"
            class="tab-btn"
            :class="{ active: activeTab === tab }"
            @click="activeTab = tab"
          >
            {{ tabLabels[tab] }}
          </button>
        </div>

        <div class="center-content">
          <!-- Graph tab -->
          <KnowledgeGraphView
            v-if="activeTab === 'graph' || activeTab === 'replay'"
            :graphSnapshot="graphSnapshot"
            :selectedRound="displayRound"
            @node-selected="onNodeSelected"
          />

          <!-- Transcript tab -->
          <div v-if="activeTab === 'transcript'" class="transcript-view">
            <div v-if="transcript.length === 0" class="empty-state">
              <p>No turns yet. Simulation in progress...</p>
            </div>
            <div v-for="turn in roundFilteredTranscript" :key="turn.turn_id || turn.id" class="turn-card">
              <div class="turn-header">
                <span class="turn-agent-dot" :style="{ background: agentColor(turn.agent_id) }"></span>
                <span class="turn-agent">{{ turn.agent_name || turn.agent_id }}</span>
                <span class="turn-role">{{ turn.agent_role }}</span>
                <span class="turn-round-badge">R{{ turn.round_num }}</span>
              </div>
              <div class="turn-content">{{ turn.content }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Panel: Detail + Analyst + Conflicts -->
      <div class="panel-right">
        <NodeDetailPanel
          v-if="selectedNode"
          :node="selectedNode"
          @close="selectedNode = null"
        />

        <StanceHeatmap
          :stances="stances"
          :frame="frame"
          :currentRound="displayRound"
        />

        <AnalystFeed
          :entries="analystEntries"
          :currentRound="displayRound"
        />

        <ConflictFeed
          :disagreements="scoreboard?.major_disagreements || []"
          :coalitions="coalitions"
        />
      </div>
    </div>

    <!-- Bottom: Round Timeline -->
    <RoundTimeline
      v-if="status !== 'connecting' && status !== 'loading' && status !== 'error'"
      :maxRound="maxRound"
      :currentRound="displayRound"
      :isLive="status === 'live'"
      :isPlaying="isPlaying"
      @seek="onSeek"
      @play="startPlayback"
      @pause="stopPlayback"
      @next="nextRound"
      @prev="prevRound"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useSimulationSSE } from '../composables/useSimulationSSE'
import KnowledgeGraphView from '../components/research/KnowledgeGraphView.vue'
import ScoreboardPanel from '../components/research/ScoreboardPanel.vue'
import AnalystFeed from '../components/research/AnalystFeed.vue'
import ConflictFeed from '../components/research/ConflictFeed.vue'
import NodeDetailPanel from '../components/research/NodeDetailPanel.vue'
import RoundTimeline from '../components/research/RoundTimeline.vue'
import StanceHeatmap from '../components/research/StanceHeatmap.vue'

const props = defineProps({
  simId: { type: String, required: true },
})

const tabLabels = { graph: 'Graph', transcript: 'Transcript', replay: 'Replay' }
const activeTab = ref('graph')
const selectedNode = ref(null)
const isPlaying = ref(false)
const displayRound = ref(0)
let playbackInterval = null

const AGENT_COLORS = ['#1EA88E', '#3B82F6', '#8B5CF6', '#F59E0B', '#EF4444', '#EC4899', '#14B8A6', '#6366F1']

const {
  frame, graphSnapshot, scoreboard, analystEntries, transcript,
  stances, disagreements, coalitions, status, currentRound, maxRound,
  error, init, loadRound, loadFromRest,
} = useSimulationSSE(props.simId)

const roundFilteredTranscript = computed(() => {
  if (!displayRound.value || displayRound.value === 0) return transcript.value
  return transcript.value.filter(t => t.round_num === displayRound.value)
})

function agentColor(agentId) {
  if (!agentId) return AGENT_COLORS[0]
  const hash = agentId.split('').reduce((a, c) => a + c.charCodeAt(0), 0)
  return AGENT_COLORS[hash % AGENT_COLORS.length]
}

function onNodeSelected(node) {
  selectedNode.value = node
}

function onSeek(round) {
  displayRound.value = round
  if (status.value === 'completed') loadRound(round)
}

function nextRound() {
  if (displayRound.value < maxRound.value) onSeek(displayRound.value + 1)
}

function prevRound() {
  if (displayRound.value > 1) onSeek(displayRound.value - 1)
}

function startPlayback() {
  isPlaying.value = true
  playbackInterval = setInterval(() => {
    if (displayRound.value >= maxRound.value) {
      stopPlayback()
      return
    }
    onSeek(displayRound.value + 1)
  }, 2000)
}

function stopPlayback() {
  isPlaying.value = false
  if (playbackInterval) {
    clearInterval(playbackInterval)
    playbackInterval = null
  }
}

function retryLoad() {
  loadFromRest()
}

// Sync displayRound with live currentRound during streaming
watch(currentRound, (val) => {
  if (status.value === 'live' && !isPlaying.value) {
    displayRound.value = val
  }
})

// Set initial display round when maxRound is first known
watch(maxRound, (val) => {
  if (displayRound.value === 0 && val > 0) displayRound.value = val
})

onMounted(() => { init() })
onUnmounted(stopPlayback)
</script>

<style scoped>
.research-console {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: var(--font-sans);
}

/* ── Header ── */
.console-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 16px;
  height: 48px;
  border-bottom: 1px solid var(--border-primary);
  background: var(--bg-secondary);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-back {
  background: none;
  border: 1px solid var(--border-primary);
  color: var(--text-secondary);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 12px;
  font-family: var(--font-sans);
  transition: all var(--transition-fast);
}
.btn-back:hover { background: var(--bg-hover); color: var(--text-primary); }

.console-title {
  font-weight: 600;
  font-size: 14px;
}

.topic-label {
  font-size: 12px;
  color: var(--text-secondary);
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.status-badge.live { background: rgba(var(--os-brand-rgb), 0.15); color: var(--os-brand); }
.status-badge.completed { background: rgba(34,197,94,0.15); color: var(--success); }
.status-badge.error { background: rgba(239,68,68,0.15); color: var(--error); }
.status-badge.loading, .status-badge.connecting, .status-badge.reconnecting {
  background: rgba(59,130,246,0.15); color: var(--info);
}

.round-badge {
  font-size: 11px;
  font-weight: 600;
  font-family: var(--font-mono);
  color: var(--text-secondary);
}

/* ── Loading / Error ── */
.console-loading, .console-error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-secondary);
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-primary);
  border-top-color: var(--os-brand);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.btn-retry {
  background: var(--os-brand);
  color: var(--text-on-brand);
  border: none;
  padding: 6px 16px;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-family: var(--font-sans);
}

/* ── 3-Panel Layout ── */
.console-body {
  display: grid;
  grid-template-columns: 280px 1fr 300px;
  flex: 1;
  overflow: hidden;
}

.panel-left, .panel-right {
  overflow-y: auto;
  border-right: 1px solid var(--border-primary);
  padding: 12px;
}
.panel-right {
  border-right: none;
  border-left: 1px solid var(--border-primary);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-center {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Center Tabs ── */
.center-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border-primary);
  background: var(--bg-secondary);
  flex-shrink: 0;
}

.tab-btn {
  padding: 8px 20px;
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  font-family: var(--font-sans);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all var(--transition-fast);
}
.tab-btn:hover { color: var(--text-primary); background: var(--bg-hover); }
.tab-btn.active {
  color: var(--os-brand);
  border-bottom-color: var(--os-brand);
}

.center-content {
  flex: 1;
  overflow: hidden;
  position: relative;
}

/* ── Transcript View ── */
.transcript-view {
  overflow-y: auto;
  padding: 12px;
  height: 100%;
}

.turn-card {
  margin-bottom: 10px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
}

.turn-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.turn-agent-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.turn-agent {
  font-weight: 600;
  font-size: 13px;
}

.turn-role {
  font-size: 11px;
  color: var(--text-tertiary);
}

.turn-round-badge {
  margin-left: auto;
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--text-tertiary);
}

.turn-content {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary);
  white-space: pre-wrap;
}

.empty-state {
  text-align: center;
  color: var(--text-tertiary);
  padding: 40px;
  font-size: 13px;
}
</style>

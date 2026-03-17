<template>
  <div class="research-dashboard">
    <!-- Header -->
    <div class="dashboard-header">
      <div class="brand">
        <img src="/opensens-icon.jpg" alt="Opensens" class="brand-icon" />
        <div class="brand-text">
          <span class="brand-name">OSSR</span>
          <span class="brand-sub">Research Mapping & Simulation</span>
        </div>
      </div>
      <div class="header-right">
        <div class="header-stats" v-if="stats">
          <span class="stat-chip">{{ stats.papers || 0 }} papers</span>
          <span class="stat-chip">{{ stats.topics || 0 }} topics</span>
          <span class="stat-chip">{{ stats.citations || 0 }} citations</span>
        </div>
        <button class="theme-toggle" @click="toggleTheme" :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'">
          <span v-if="isDark">&#9788;</span>
          <span v-else>&#9790;</span>
        </button>
      </div>
    </div>

    <!-- Main layout: sidebar + graph -->
    <div class="dashboard-body" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
      <!-- Left sidebar -->
      <div class="sidebar" v-show="!sidebarCollapsed">
        <!-- Ingestion panel -->
        <div class="sidebar-section">
          <div class="section-header" @click="toggleSection('ingest')">
            <span class="section-title">Ingest Papers</span>
            <span class="section-toggle">{{ openSections.ingest ? '&#9660;' : '&#9654;' }}</span>
          </div>
          <div v-show="openSections.ingest" class="section-body">
            <div class="form-group">
              <label>Search Query</label>
              <input
                v-model="ingestForm.query"
                type="text"
                placeholder="e.g. electrochemical impedance spectroscopy"
                class="form-input"
              />
            </div>
            <div class="form-group">
              <label>Sources</label>
              <div class="checkbox-group">
                <label class="checkbox-item" v-for="src in availableSources" :key="src.value">
                  <input type="checkbox" v-model="ingestForm.sources" :value="src.value" />
                  <span>{{ src.label }}</span>
                </label>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group half">
                <label>From</label>
                <input v-model="ingestForm.date_from" type="date" class="form-input" />
              </div>
              <div class="form-group half">
                <label>To</label>
                <input v-model="ingestForm.date_to" type="date" class="form-input" />
              </div>
            </div>
            <div class="form-group">
              <label>Max Results</label>
              <input v-model.number="ingestForm.max_results" type="number" min="10" max="500" class="form-input" />
            </div>
            <button class="btn-primary" @click="startIngestion" :disabled="ingesting || !ingestForm.query.trim()">
              {{ ingesting ? 'Ingesting...' : 'Start Ingestion' }}
            </button>

            <!-- Progress -->
            <div v-if="ingestTask" class="task-progress">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: (ingestTask.progress || 0) + '%' }"></div>
              </div>
              <span class="progress-text">{{ ingestTask.message || 'Working...' }}</span>
            </div>
          </div>
        </div>

        <!-- Topic mapping panel -->
        <div class="sidebar-section">
          <div class="section-header" @click="toggleSection('map')">
            <span class="section-title">Topic Mapping</span>
            <span class="section-toggle">{{ openSections.map ? '&#9660;' : '&#9654;' }}</span>
          </div>
          <div v-show="openSections.map" class="section-body">
            <button class="btn-primary" @click="buildMap" :disabled="mapping">
              {{ mapping ? 'Mapping...' : 'Build Topic Map' }}
            </button>
            <div v-if="mapTask" class="task-progress">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: (mapTask.progress || 0) + '%' }"></div>
              </div>
              <span class="progress-text">{{ mapTask.message || 'Working...' }}</span>
            </div>
          </div>
        </div>

        <!-- Agent Generation panel -->
        <div class="sidebar-section">
          <div class="section-header" @click="toggleSection('agents')">
            <span class="section-title">Generate Agents</span>
            <span class="section-toggle">{{ openSections.agents ? '&#9660;' : '&#9654;' }}</span>
          </div>
          <div v-show="openSections.agents" class="section-body">
            <div class="form-group">
              <label>Agents per Cluster</label>
              <input v-model.number="agentForm.agents_per_cluster" type="number" min="1" max="10" class="form-input" />
            </div>
            <button class="btn-primary" @click="startAgentGeneration" :disabled="generatingAgents || (!stats?.topics)">
              {{ generatingAgents ? 'Generating...' : 'Generate Agents' }}
            </button>
            <div v-if="agentGenTask" class="task-progress">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: (agentGenTask.progress || 0) + '%' }"></div>
              </div>
              <span class="progress-text">{{ agentGenTask.message || 'Working...' }}</span>
            </div>
            <div v-if="agents.length > 0" class="agent-chips">
              <div v-for="agent in agents" :key="agent.agent_id" class="agent-chip" :title="agent.role">
                <span class="agent-chip-name">{{ agent.name }}</span>
                <span class="agent-chip-role">{{ agent.role }}</span>
              </div>
            </div>
            <div v-else-if="!generatingAgents" class="empty-section">
              No agents yet. Build topics first, then generate.
            </div>
          </div>
        </div>

        <!-- Topic tree panel -->
        <div class="sidebar-section">
          <div class="section-header" @click="toggleSection('topics')">
            <span class="section-title">Topic Explorer</span>
            <span class="section-toggle">{{ openSections.topics ? '&#9660;' : '&#9654;' }}</span>
          </div>
          <div v-show="openSections.topics" class="section-body topic-tree-body">
            <div v-if="selectedTopicIds.length > 0" class="selected-topics-bar">
              <span class="selected-count">{{ selectedTopicIds.length }} selected</span>
              <button class="btn-clear-topics" @click="selectedTopicIds = []">Clear</button>
            </div>
            <div v-if="!topicTree || topicTree.length === 0" class="empty-section">
              No topics yet. Build a map first.
            </div>
            <div v-for="domain in topicTree" :key="domain.topic_id" class="tree-node domain-node">
              <div class="tree-label" @click="toggleTopicSelection(domain)">
                <input type="checkbox" class="tree-checkbox" :checked="selectedTopicIds.includes(domain.topic_id)" @click.stop="toggleTopicSelection(domain)" />
                <span class="tree-dot domain"></span>
                <span class="tree-name">{{ domain.name }}</span>
                <span class="tree-count">{{ domain.paper_count }}</span>
              </div>
              <div v-if="domain.children" class="tree-children">
                <div v-for="sf in domain.children" :key="sf.topic_id" class="tree-node subfield-node">
                  <div class="tree-label" @click="toggleTopicSelection(sf)">
                    <input type="checkbox" class="tree-checkbox" :checked="selectedTopicIds.includes(sf.topic_id)" @click.stop="toggleTopicSelection(sf)" />
                    <span class="tree-dot subfield"></span>
                    <span class="tree-name">{{ sf.name }}</span>
                    <span class="tree-count">{{ sf.paper_count }}</span>
                  </div>
                  <div v-if="sf.children" class="tree-children">
                    <div v-for="th in sf.children" :key="th.topic_id" class="tree-node thread-node">
                      <div class="tree-label" @click="toggleTopicSelection(th)">
                        <input type="checkbox" class="tree-checkbox" :checked="selectedTopicIds.includes(th.topic_id)" @click.stop="toggleTopicSelection(th)" />
                        <span class="tree-dot thread"></span>
                        <span class="tree-name">{{ th.name }}</span>
                        <span class="tree-count">{{ th.paper_count }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Gaps panel -->
        <div class="sidebar-section">
          <div class="section-header" @click="toggleSection('gaps')">
            <span class="section-title">Research Gaps</span>
            <span class="section-toggle">{{ openSections.gaps ? '&#9660;' : '&#9654;' }}</span>
          </div>
          <div v-show="openSections.gaps" class="section-body">
            <div v-if="!gaps || gaps.length === 0" class="empty-section">
              No gaps detected yet.
            </div>
            <div v-for="(gap, i) in gaps" :key="i" class="gap-item">
              <div class="gap-header">
                <span class="gap-score" :style="{ background: gapScoreColor(gap.gap_score) }">
                  {{ (gap.gap_score * 100).toFixed(0) }}%
                </span>
                <span class="gap-label">{{ gap.topic_a }} &harr; {{ gap.partner_topic }}</span>
              </div>
              <p class="gap-desc" v-if="gap.opportunity">{{ gap.opportunity }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Sidebar toggle -->
      <button class="sidebar-toggle" @click="sidebarCollapsed = !sidebarCollapsed">
        {{ sidebarCollapsed ? '&#9654;' : '&#9664;' }}
      </button>

      <!-- Main panels -->
      <div class="main-panels" :class="viewMode">
        <!-- Graph panel (Claudecode) -->
        <div class="graph-area" v-show="viewMode !== 'debate-only'">
          <TopicGraph
            :graphData="landscapeData"
            :loading="loadingLandscape"
            :gaps="gaps"
            @refresh="fetchLandscape"
            @toggle-maximize="toggleViewMode"
            @node-click="handleNodeClick"
          />
        </div>

        <!-- Debate panel (AntiGravity) -->
        <div class="debate-area" v-show="viewMode !== 'graph-only'">
          <AgentDebate
            :topicIds="selectedTopicIds"
            :topicNames="selectedTopicNames"
            :highlightedAgent="highlightedAgentId"
            @simulation-started="onSimStarted"
            @simulation-completed="onSimCompleted"
          />
        </div>
      </div>

      <!-- View mode tabs -->
      <div class="view-tabs">
        <button class="view-tab" :class="{ active: viewMode === 'split' }" @click="viewMode = 'split'" title="Split view">&#9638;&#9638;</button>
        <button class="view-tab" :class="{ active: viewMode === 'graph-only' }" @click="viewMode = 'graph-only'" title="Graph only">&#9638;</button>
        <button class="view-tab" :class="{ active: viewMode === 'debate-only' }" @click="viewMode = 'debate-only'" title="Debate only">&#9639;</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import TopicGraph from '../components/TopicGraph.vue'
import AgentDebate from '../components/AgentDebate.vue'
import {
  startIngestion as apiStartIngestion,
  listTopics,
  getResearchMap,
  getResearchGaps,
  getResearchStats,
  pollIngestion,
} from '../api/research.js'
import {
  generateAgents as apiGenerateAgents,
  listAgents,
  pollAgentGeneration,
} from '../api/simulation.js'
import service, { requestWithRetry } from '../api/index'

// Theme
const isDark = ref(document.documentElement.getAttribute('data-theme') === 'dark')

function toggleTheme() {
  isDark.value = !isDark.value
  const theme = isDark.value ? 'dark' : 'light'
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem('ossr-theme', theme)
}

// State
const stats = ref(null)
const landscapeData = ref(null)
const loadingLandscape = ref(false)
const topicTree = ref([])
const gaps = ref([])
const sidebarCollapsed = ref(false)
const viewMode = ref('split') // 'split' | 'graph-only' | 'debate-only'
const selectedTopicIds = ref([])
const highlightedAgentId = ref(null)

// Flatten topic tree into a lookup map for name resolution
const topicLookup = computed(() => {
  const map = {}
  function walk(nodes) {
    for (const n of (nodes || [])) {
      map[n.topic_id] = n.name
      if (n.children) walk(n.children)
    }
  }
  walk(topicTree.value)
  return map
})

const selectedTopicNames = computed(() =>
  selectedTopicIds.value.map(id => topicLookup.value[id] || id)
)

const openSections = reactive({
  ingest: true,
  map: false,
  agents: false,
  topics: true,
  gaps: false,
})

// Ingestion form
const ingestForm = reactive({
  query: '',
  sources: ['biorxiv', 'arxiv', 'semantic_scholar', 'openalex'],
  date_from: '',
  date_to: '',
  max_results: 50,
})

const availableSources = [
  { value: 'biorxiv', label: 'bioRxiv' },
  { value: 'medrxiv', label: 'medRxiv' },
  { value: 'arxiv', label: 'arXiv' },
  { value: 'semantic_scholar', label: 'Semantic Scholar' },
  { value: 'openalex', label: 'OpenAlex' },
]

const ingesting = ref(false)
const ingestTask = ref(null)
const mapping = ref(false)
const mapTask = ref(null)
const generatingAgents = ref(false)
const agentGenTask = ref(null)
const agents = ref([])
const agentForm = reactive({
  agents_per_cluster: 3,
})

// Methods
function toggleSection(key) {
  openSections[key] = !openSections[key]
}

async function fetchStats() {
  try {
    const res = await getResearchStats()
    stats.value = res.data?.data || res.data
  } catch (e) {
    console.warn('Failed to fetch stats:', e)
  }
}

async function fetchLandscape() {
  loadingLandscape.value = true
  try {
    const res = await getResearchMap()
    landscapeData.value = res.data?.data || res.data
    topicTree.value = landscapeData.value?.topic_tree || []
  } catch (e) {
    console.warn('Failed to fetch landscape:', e)
  } finally {
    loadingLandscape.value = false
  }
}

async function fetchGaps() {
  try {
    const res = await getResearchGaps()
    gaps.value = res.data?.data || res.data || []
  } catch (e) {
    console.warn('Failed to fetch gaps:', e)
  }
}

async function fetchTopics() {
  try {
    const res = await listTopics({ tree: true })
    topicTree.value = res.data?.data || res.data || []
  } catch (e) {
    console.warn('Failed to fetch topics:', e)
  }
}

async function startIngestion() {
  if (!ingestForm.query.trim()) return
  ingesting.value = true
  ingestTask.value = null

  try {
    const res = await apiStartIngestion({
      query: ingestForm.query,
      sources: ingestForm.sources,
      date_from: ingestForm.date_from || undefined,
      date_to: ingestForm.date_to || undefined,
      max_results: ingestForm.max_results,
    })
    const taskId = res.data?.task_id || res.data?.data?.task_id

    await pollIngestion(taskId, (task) => {
      ingestTask.value = task.data || task
    })

    // Refresh data after ingestion
    await fetchStats()
    ingestTask.value = { ...ingestTask.value, message: 'Ingestion complete!' }
  } catch (e) {
    ingestTask.value = { message: `Error: ${e.message}`, progress: 0 }
  } finally {
    ingesting.value = false
  }
}

async function buildMap() {
  mapping.value = true
  mapTask.value = null

  try {
    const res = await requestWithRetry(
      () => service.post('/api/research/map/build', { include_gaps: true }),
      3, 1000
    )
    const taskId = res.data?.task_id

    // Poll mapping progress
    const poll = async () => {
      try {
        const statusRes = await service.get(`/api/research/map/${taskId}/status`)
        const task = statusRes.data?.data || statusRes.data
        mapTask.value = task

        if (task.status === 'completed') {
          await Promise.all([fetchLandscape(), fetchGaps(), fetchTopics(), fetchStats()])
          mapTask.value = { ...mapTask.value, message: 'Mapping complete!' }
          mapping.value = false
          return
        }
        if (task.status === 'failed') {
          mapTask.value = { message: `Error: ${task.error}`, progress: 0 }
          mapping.value = false
          return
        }
        setTimeout(poll, 2000)
      } catch (e) {
        mapTask.value = { message: `Error: ${e.message}`, progress: 0 }
        mapping.value = false
      }
    }
    poll()
  } catch (e) {
    mapTask.value = { message: `Error: ${e.message}`, progress: 0 }
    mapping.value = false
  }
}

async function fetchAgents() {
  try {
    const res = await listAgents()
    agents.value = res.data?.data || res.data || []
  } catch (e) {
    console.warn('Failed to fetch agents:', e)
  }
}

async function startAgentGeneration() {
  generatingAgents.value = true
  agentGenTask.value = null

  try {
    const res = await apiGenerateAgents({
      agents_per_cluster: agentForm.agents_per_cluster,
    })
    const taskId = res.data?.task_id || res.data?.data?.task_id

    await pollAgentGeneration(taskId, (task) => {
      agentGenTask.value = task
    })

    await fetchAgents()
    agentGenTask.value = { ...agentGenTask.value, message: 'Agents generated!' }
  } catch (e) {
    agentGenTask.value = { message: `Error: ${e.message}`, progress: 0 }
  } finally {
    generatingAgents.value = false
  }
}

function toggleTopicSelection(topic) {
  const idx = selectedTopicIds.value.indexOf(topic.topic_id)
  if (idx >= 0) {
    selectedTopicIds.value.splice(idx, 1)
  } else {
    selectedTopicIds.value.push(topic.topic_id)
  }
}

function handleNodeClick(node) {
  if (node.type === 'topic') {
    toggleTopicSelection({ topic_id: node.id })
    openSections.topics = true
  }
}

function toggleViewMode() {
  const modes = ['split', 'graph-only', 'debate-only']
  const idx = modes.indexOf(viewMode.value)
  viewMode.value = modes[(idx + 1) % modes.length]
}

function onSimStarted(simData) {
  if (viewMode.value === 'graph-only') {
    viewMode.value = 'split'
  }
}

function onSimCompleted(simData) {
  fetchStats()
}

function gapScoreColor(score) {
  if (score >= 0.7) return 'var(--error)'
  if (score >= 0.4) return 'var(--warning)'
  return 'var(--text-tertiary)'
}

// Init
onMounted(async () => {
  await Promise.all([fetchStats(), fetchLandscape(), fetchTopics(), fetchGaps(), fetchAgents()])
})
</script>

<style scoped>
.research-dashboard {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-primary);
  font-family: var(--font-sans);
}

/* Header */
.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  border-bottom: 1px solid var(--border-primary);
  background: var(--bg-secondary);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  object-fit: contain;
}

.brand-text {
  display: flex;
  flex-direction: column;
}

.brand-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--os-brand);
  letter-spacing: 1.5px;
  line-height: 1.2;
}

.brand-sub {
  font-size: 11px;
  color: var(--text-tertiary);
  font-weight: 400;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-stats {
  display: flex;
  gap: 6px;
}

.stat-chip {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  background: var(--os-brand-light);
  border: 1px solid var(--os-brand-subtle);
  border-radius: var(--radius-pill);
  color: var(--os-brand);
}

.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 16px;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.theme-toggle:hover {
  background: var(--bg-hover);
  color: var(--os-brand);
  border-color: var(--os-brand);
}

/* Body layout */
.dashboard-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.dashboard-body.sidebar-collapsed .sidebar {
  display: none;
}

/* Sidebar */
.sidebar {
  width: 320px;
  min-width: 320px;
  border-right: 1px solid var(--border-primary);
  overflow-y: auto;
  background: var(--bg-secondary);
}

.sidebar-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  min-width: 20px;
  background: var(--bg-tertiary);
  border: none;
  border-right: 1px solid var(--border-primary);
  cursor: pointer;
  color: var(--text-tertiary);
  font-size: 10px;
  transition: all var(--transition-fast);
}

.sidebar-toggle:hover {
  background: var(--bg-hover);
  color: var(--os-brand);
}

/* Sidebar sections */
.sidebar-section {
  border-bottom: 1px solid var(--border-secondary);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  cursor: pointer;
  user-select: none;
  transition: background var(--transition-fast);
}

.section-header:hover {
  background: var(--bg-hover);
}

.section-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.section-toggle {
  font-size: 10px;
  color: var(--text-tertiary);
}

.section-body {
  padding: 0 16px 16px;
}

/* Forms */
.form-group {
  margin-bottom: 10px;
}

.form-group label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-tertiary);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.form-input {
  width: 100%;
  padding: 7px 10px;
  font-size: 12px;
  font-family: var(--font-sans);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  color: var(--text-primary);
  box-sizing: border-box;
  transition: border-color var(--transition-fast);
}

.form-input:focus {
  outline: none;
  border-color: var(--os-brand);
  box-shadow: 0 0 0 3px rgba(var(--os-brand-rgb), 0.12);
}

.form-input::placeholder {
  color: var(--text-tertiary);
}

.form-row {
  display: flex;
  gap: 8px;
}

.form-group.half {
  flex: 1;
}

.checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-secondary);
  cursor: pointer;
}

.checkbox-item input[type="checkbox"] {
  accent-color: var(--os-brand);
}

.btn-primary {
  width: 100%;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  font-family: var(--font-sans);
  background: var(--os-brand);
  color: var(--text-on-brand);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-primary:hover {
  background: var(--os-brand-hover);
}

.btn-primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Task progress */
.task-progress {
  margin-top: 10px;
}

.progress-bar {
  height: 4px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--os-brand);
  border-radius: 2px;
  transition: width 0.3s;
}

.progress-text {
  display: block;
  margin-top: 4px;
  font-size: 10px;
  color: var(--text-tertiary);
}

/* Topic tree */
.topic-tree-body {
  max-height: 300px;
  overflow-y: auto;
}

.selected-topics-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
  margin-bottom: 6px;
  border-bottom: 1px solid var(--border-secondary);
}

.selected-count {
  font-size: 10px;
  font-weight: 600;
  color: var(--os-brand);
}

.btn-clear-topics {
  font-size: 10px;
  font-weight: 500;
  font-family: var(--font-sans);
  padding: 2px 8px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-tertiary);
  transition: all var(--transition-fast);
}

.btn-clear-topics:hover {
  color: var(--error);
  border-color: var(--error);
}

.tree-checkbox {
  width: 13px;
  height: 13px;
  accent-color: var(--os-brand);
  cursor: pointer;
  flex-shrink: 0;
}

.empty-section {
  font-size: 11px;
  color: var(--text-tertiary);
  padding: 8px 0;
}

.tree-node {
  margin-left: 0;
}

.tree-children {
  margin-left: 16px;
}

.tree-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-primary);
  transition: color var(--transition-fast);
}

.tree-label:hover {
  color: var(--os-brand);
}

.tree-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.tree-dot.domain { background: var(--graph-domain); }
.tree-dot.subfield { background: var(--graph-subfield); }
.tree-dot.thread { background: var(--graph-thread); }

.tree-name {
  flex: 1;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-count {
  font-size: 10px;
  font-weight: 600;
  color: var(--os-brand);
  background: var(--os-brand-light);
  padding: 1px 6px;
  border-radius: 8px;
}

/* Gap items */
.gap-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--border-secondary);
}

.gap-item:last-child {
  border-bottom: none;
}

.gap-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.gap-score {
  font-size: 10px;
  font-weight: 700;
  color: #FFF;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.gap-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-primary);
}

.gap-desc {
  margin: 4px 0 0;
  font-size: 10px;
  color: var(--text-tertiary);
  line-height: 1.4;
}

/* Main panels */
.main-panels {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
}

.main-panels.split .graph-area,
.main-panels.split .debate-area {
  flex: 1;
}

.main-panels.graph-only .graph-area {
  flex: 1;
}

.main-panels.debate-only .debate-area {
  flex: 1;
}

.graph-area {
  overflow: hidden;
  border-right: 1px solid var(--border-primary);
}

.debate-area {
  overflow: hidden;
}

/* View mode tabs */
.view-tabs {
  position: fixed;
  bottom: 16px;
  right: 16px;
  display: flex;
  gap: 4px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-md);
  padding: 3px;
  box-shadow: var(--shadow-md);
  z-index: 10;
}

.view-tab {
  padding: 4px 10px;
  font-size: 12px;
  font-family: var(--font-sans);
  background: none;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-tertiary);
  transition: all var(--transition-fast);
}

.view-tab:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.view-tab.active {
  color: var(--os-brand);
  background: var(--os-brand-light);
  border-color: var(--os-brand-subtle);
  font-weight: 600;
}

/* Agent chips */
.agent-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.agent-chip {
  display: flex;
  flex-direction: column;
  padding: 6px 10px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-md);
  cursor: default;
}

.agent-chip-name {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
}

.agent-chip-role {
  font-size: 9px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
</style>

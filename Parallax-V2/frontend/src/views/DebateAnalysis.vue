<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getHistoryRunDetail, getHistoryTranscript } from '@/api/ais'
import GlassPanel from '@/components/shared/GlassPanel.vue'

const props = defineProps<{
  runId: string
}>()

const router = useRouter()

const loading = ref(true)
const error = ref<string | null>(null)
const runDetail = ref<any>(null)
const transcript = ref<any[]>([])

const activeTab = ref('heatmap') // 'heatmap', 'coalitions', 'highlights', 'transcript'

async function loadData() {
  try {
    loading.value = true
    error.value = null
    const res = await getHistoryRunDetail(props.runId)
    if (res.data?.success) {
      runDetail.value = res.data.data
    }

    const tRes = await getHistoryTranscript(props.runId)
    if (tRes.data?.success) {
      transcript.value = (tRes.data.data.transcript as any[]) || []
    }
  } catch (err: any) {
    console.error('Failed to load debate:', err)
    error.value = err.message || 'Failed to load debate analysis.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})

const title = computed(() => {
  return runDetail.value?.title || runDetail.value?.query || 'Debate Analysis'
})

const agentCount = computed(() => {
  return runDetail.value?.summary?.agent_count || 10
})

const rounds = computed(() => {
  return runDetail.value?.summary?.rounds || 3
})

const consensus = computed(() => {
  // stub metric
  return 72
})

function goBack() {
  router.push({ name: 'command-center' })
}

// Generate dummy heatmap data for agents based on transcript
const heatmapAgents = computed(() => {
  const agents = new Set<string>()
  transcript.value.forEach(t => {
    if (t.name) agents.add(t.name)
    else if (t.agent) agents.add(t.agent)
    else if (t.role) agents.add(t.role)
  })
  
  if (agents.size === 0) {
    return Array.from({ length: 20 }, (_, i) => ({
      id: `A${(i + 1).toString().padStart(2, '0')}`,
      name: `Agent_${(i + 1).toString().padStart(2, '0')}`,
      type: i % 3 === 0 ? 'opponent' : (i % 5 === 0 ? 'neutral' : 'proponent'),
      opacity: 0.7 + (Math.random() * 0.3)
    }))
  }
  
  return Array.from(agents).map((name, i) => {
    const isNeutral = i % 3 === 0
    const isPro = !isNeutral && i % 2 !== 0
    return {
      id: name.substring(0, 3).toUpperCase(),
      name,
      type: isNeutral ? 'neutral' : (isPro ? 'proponent' : 'opponent'),
      opacity: 0.8 + (Math.random() * 0.2)
    }
  })
})

function getHeatmapColor(type: string): string {
  if (type === 'proponent') return 'var(--os-brand)'
  if (type === 'neutral') return 'var(--success)'
  return 'var(--text-tertiary)'
}

function formatTime(isoOrTimestamp: any) {
  if (!isoOrTimestamp) return '00:00:00'
  try {
    const d = new Date(isoOrTimestamp)
    return d.toLocaleTimeString()
  } catch {
    return '00:00:00'
  }
}
</script>

<template>
  <div class="debate-layout">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar__brand">
        <span class="sidebar__brand-text">OPENSENS</span>
      </div>
      
      <div class="sidebar__nav">
        <p class="sidebar__nav-title">Analysis Modules</p>
        
        <button 
          class="nav-btn" 
          :class="{ 'nav-btn--active': activeTab === 'heatmap' }"
          @click="activeTab = 'heatmap'"
        >
          <span class="material-symbols-outlined">grid_view</span>
          <span class="nav-btn__text">Stance Heatmap</span>
        </button>
        
        <button 
          class="nav-btn" 
          :class="{ 'nav-btn--active': activeTab === 'coalitions' }"
          @click="activeTab = 'coalitions'"
        >
          <span class="material-symbols-outlined">groups</span>
          <span class="nav-btn__text">Coalition Groups</span>
        </button>
        
        <button 
          class="nav-btn" 
          :class="{ 'nav-btn--active': activeTab === 'highlights' }"
          @click="activeTab = 'highlights'"
        >
          <span class="material-symbols-outlined">analytics</span>
          <span class="nav-btn__text">Argument Highlights</span>
        </button>
        
        <button 
          class="nav-btn" 
          :class="{ 'nav-btn--active': activeTab === 'transcript' }"
          @click="activeTab = 'transcript'"
        >
          <span class="material-symbols-outlined">segment</span>
          <span class="nav-btn__text">Transcript</span>
        </button>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="main-content">
      <header class="header">
        <div class="header__left">
          <button class="back-btn" @click="goBack">
            <span class="material-symbols-outlined">arrow_back</span>
          </button>
          <h1 class="header__title">Debate Analysis: {{ title }}</h1>
        </div>
        <button class="header__link" @click="goBack">Back to Command Center</button>
      </header>
      
      <div class="header__divider"></div>

      <div v-if="loading" class="content-body loading-state">
        <span class="material-symbols-outlined spin">progress_activity</span>
        <p>Loading analysis...</p>
      </div>

      <div v-else-if="error" class="content-body error-state">
        <span class="material-symbols-outlined">error</span>
        <p>{{ error }}</p>
      </div>

      <div v-else class="content-body">
        
        <!-- Metrics -->
        <section class="metrics-grid">
          <GlassPanel class="metric-card">
            <span class="metric-label">Active Agents</span>
            <div class="metric-value-row">
              <span class="metric-value">{{ agentCount }}</span>
              <span class="metric-unit">Instances</span>
            </div>
          </GlassPanel>
          
          <GlassPanel class="metric-card">
            <span class="metric-label">Debate Rounds</span>
            <div class="metric-value-row">
              <span class="metric-value">{{ rounds }}</span>
              <span class="metric-unit">Iterations</span>
            </div>
          </GlassPanel>
          
          <GlassPanel class="metric-card consensus-card">
            <div class="consensus-header">
              <span class="metric-label">Consensus Vector</span>
              <span class="metric-value consensus-val">{{ consensus }}%</span>
            </div>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" :style="`width: ${consensus}%`"></div>
            </div>
          </GlassPanel>
        </section>

        <!-- Bento Grid -->
        <div class="bento-grid">
          <!-- Stance Heatmap -->
          <GlassPanel class="bento-item heatmap" :class="{ 'focus': activeTab === 'heatmap' }">
            <div class="bento-header">
              <div>
                <h2 class="bento-title">Stance Heatmap</h2>
                <p class="bento-desc">Distribution of agent perspectives.</p>
              </div>
              <div class="legend">
                <div class="legend-item"><div class="legend-box" style="background: var(--os-brand)"></div> Proponent</div>
                <div class="legend-item"><div class="legend-box" style="background: var(--success)"></div> Neutral</div>
                <div class="legend-item"><div class="legend-box" style="background: var(--text-tertiary)"></div> Opponent</div>
              </div>
            </div>
            
            <div class="heatmap-grid">
              <div 
                v-for="agent in heatmapAgents" 
                :key="agent.id"
                class="agent-square"
                :style="`background: ${getHeatmapColor(agent.type)}; opacity: ${agent.opacity}`"
                :title="agent.name"
              >
                {{ agent.id }}
              </div>
            </div>
          </GlassPanel>

          <!-- Coalitions -->
          <GlassPanel class="bento-item coalitions" :class="{ 'focus': activeTab === 'coalitions' }">
            <h3 class="bento-subtitle">Coalition Groups</h3>
            <div class="coalition-list">
              <div class="coalition-group">
                <div class="coalition-header">
                  <span class="coalition-name">The Optimization Group</span>
                  <span class="coalition-badge">PRO</span>
                </div>
                <div class="avatar-stack">
                  <div v-for="i in 4" :key="i" class="avatar-sm" style="background: var(--os-brand)">A0{{i}}</div>
                </div>
              </div>

              <div class="coalition-group">
                <div class="coalition-header">
                  <span class="coalition-name">The Validity Group</span>
                  <span class="coalition-badge alt">CON</span>
                </div>
                <div class="avatar-stack">
                  <div v-for="i in 3" :key="i" class="avatar-sm" style="background: var(--text-tertiary)">A0{{i + 4}}</div>
                </div>
              </div>
            </div>
          </GlassPanel>

          <!-- Highlights -->
          <GlassPanel class="bento-item highlights" :class="{ 'focus': activeTab === 'highlights' }">
            <h3 class="bento-subtitle">Key Arguments</h3>
            <ul class="highlight-list">
              <li class="highlight-item">
                <span class="material-symbols-outlined highlight-icon">terminal</span>
                <p class="highlight-text">Multi-agent consensus shifted during <span class="highlight-bold">Round 2</span> when focusing on scaling laws.</p>
              </li>
              <li class="highlight-item">
                <span class="material-symbols-outlined highlight-icon">terminal</span>
                <p class="highlight-text">Adversarial models challenged the baseline metrics with a <span class="highlight-bold">high confidence</span> score.</p>
              </li>
              <li class="highlight-item">
                <span class="material-symbols-outlined highlight-icon">terminal</span>
                <p class="highlight-text">Simulation indicates <span class="highlight-bold">72%</span> thermodynamic stability in proposed hypothesis.</p>
              </li>
            </ul>
          </GlassPanel>

          <!-- Transcript -->
          <GlassPanel class="bento-item transcript-box" :class="{ 'focus': activeTab === 'transcript' }">
            <div class="bento-header mb-4">
              <h3 class="bento-title">Transcript Preview</h3>
              <div class="stream-indicator">
                <span class="pulse-dot"></span>
                <span class="stream-label">Complete</span>
              </div>
            </div>
            
            <div class="transcript-scroll">
              <div v-if="transcript.length === 0" class="no-data">No transcript available</div>
              
              <div v-else v-for="(turn, idx) in transcript" :key="idx" class="chat-message">
                <div class="chat-avatar" :style="{ backgroundColor: getHeatmapColor(idx % 2 === 0 ? 'proponent' : 'opponent') }">
                  {{ (turn.name || turn.agent || turn.role || 'SYS').substring(0, 3).toUpperCase() }}
                </div>
                <div class="chat-content">
                  <div class="chat-meta">
                    <span class="chat-author">{{ turn.name || turn.agent || turn.role || 'System' }}</span>
                    <span class="chat-time">{{ formatTime(turn.timestamp) }}</span>
                  </div>
                  <p class="chat-text">{{ turn.content || turn.message }}</p>
                </div>
              </div>
            </div>
          </GlassPanel>
        </div>

      </div>
    </main>
  </div>
</template>

<style scoped>
.debate-layout {
  display: flex;
  min-height: 100vh;
  background: var(--bg-primary);
}

.sidebar {
  width: 256px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-secondary);
  display: flex;
  flex-direction: column;
  padding: 32px 16px;
  position: fixed;
  top: 0;
  left: 0;
  height: 100%;
  z-index: 50;
}

.sidebar__brand {
  margin-bottom: 40px;
  padding: 0 16px;
}

.sidebar__brand-text {
  font-family: var(--font-sans);
  font-weight: 900;
  color: var(--os-brand);
  font-size: 20px;
  letter-spacing: -0.05em;
}

.sidebar__nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sidebar__nav-title {
  font-family: var(--font-mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  color: var(--text-tertiary);
  margin-bottom: 16px;
  padding: 0 16px;
}

.nav-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  border-right: 2px solid transparent;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.15s ease;
  text-align: left;
}

.nav-btn:hover {
  background: var(--bg-tertiary);
  color: var(--os-brand);
}

.nav-btn--active {
  background: rgba(var(--os-brand-rgb), 0.1);
  color: var(--os-brand);
  border-right-color: var(--os-brand);
  font-weight: 700;
}

.nav-btn__text {
  font-size: 13px;
}

.main-content {
  margin-left: 256px;
  flex: 1;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  position: sticky;
  top: 0;
  background: var(--bg-primary);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  z-index: 40;
}

.header__left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  background: none;
  border: none;
  color: var(--os-brand);
  cursor: pointer;
  padding: 8px;
  border-radius: 50%;
  transition: background 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.back-btn:hover {
  background: var(--bg-hover);
}

.header__title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header__link {
  background: none;
  border: none;
  color: var(--os-brand);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.header__link:hover {
  text-decoration: underline;
}

.header__divider {
  height: 1px;
  background: var(--border-secondary);
  width: 100%;
}

.content-body {
  padding: 32px;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.loading-state, .error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 100px 0;
  color: var(--text-secondary);
}

.spin {
  animation: spin 1s linear infinite;
  color: var(--os-brand);
}

@keyframes spin { 100% { transform: rotate(360deg); } }

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
}

.metric-card {
  padding: 24px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.metric-label {
  font-size: 11px;
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.15em;
  color: var(--text-tertiary);
  margin-bottom: 12px;
}

.metric-value-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.metric-value {
  font-size: 36px;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--os-brand);
}

.metric-unit {
  font-size: 13px;
  color: var(--text-secondary);
}

.consensus-card {
  gap: 16px;
}

.consensus-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.consensus-val {
  font-size: 16px;
}

.progress-bar-bg {
  width: 100%;
  height: 6px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-pill);
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: var(--os-brand);
}

.bento-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 24px;
}

.bento-item {
  padding: 32px;
  border: 1px solid var(--border-secondary);
}

.bento-item.focus {
  border-color: var(--os-brand);
  box-shadow: 0 0 0 1px var(--os-brand);
}

.bento-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 32px;
}

.bento-title {
  font-size: 20px;
  font-weight: 700;
  margin: 0 0 4px 0;
}

.bento-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

.bento-subtitle {
  font-size: 11px;
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: var(--text-tertiary);
  margin: 0 0 24px 0;
}

/* Heatmap */
.heatmap {
  grid-column: span 12;
}

@media (min-width: 1024px) {
  .heatmap { grid-column: span 8; }
}

.legend {
  display: flex;
  gap: 16px;
  font-size: 10px;
  font-family: var(--font-mono);
  text-transform: uppercase;
  color: var(--text-secondary);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-box {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}

.heatmap-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(40px, 1fr));
  gap: 12px;
}

.agent-square {
  aspect-ratio: 1;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--bg-primary);
}

/* Coalitions */
.coalitions {
  grid-column: span 12;
}

@media (min-width: 1024px) {
  .coalitions { grid-column: span 4; }
}

.coalition-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.coalition-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.coalition-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.coalition-name {
  font-size: 14px;
  font-weight: 600;
}

.coalition-badge {
  font-size: 10px;
  font-family: var(--font-mono);
  padding: 2px 6px;
  background: rgba(var(--os-brand-rgb), 0.1);
  color: var(--os-brand);
  border-radius: 4px;
}

.coalition-badge.alt {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}

.avatar-stack {
  display: flex;
  margin-left: 8px;
}

.avatar-sm {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 2px solid var(--bg-primary);
  margin-left: -8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-family: var(--font-mono);
  font-weight: 700;
  color: #fff;
}

/* Highlights */
.highlights {
  grid-column: span 12;
  background: var(--bg-secondary);
}

@media (min-width: 1024px) {
  .highlights { grid-column: span 5; }
}

.highlight-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.highlight-item {
  display: flex;
  gap: 16px;
}

.highlight-icon {
  color: var(--os-brand);
  font-size: 14px;
  margin-top: 4px;
}

.highlight-text {
  font-size: 12px;
  font-family: var(--font-mono);
  line-height: 1.6;
  margin: 0;
  color: var(--text-primary);
}

.highlight-bold {
  color: var(--os-brand);
  font-weight: 700;
}

/* Transcript */
.transcript-box {
  grid-column: span 12;
  height: 480px;
  display: flex;
  flex-direction: column;
}

@media (min-width: 1024px) {
  .transcript-box { grid-column: span 7; }
}

.stream-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  background: var(--os-brand);
  border-radius: 50%;
}

.stream-label {
  font-size: 10px;
  font-family: var(--font-mono);
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.transcript-scroll {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding-right: 16px;
}

.chat-message {
  display: flex;
  gap: 16px;
}

.chat-avatar {
  width: 40px;
  height: 40px;
  border-radius: 4px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  color: #fff;
}

.chat-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chat-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-author {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.chat-time {
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--text-tertiary);
}

.chat-text {
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
  color: var(--text-secondary);
}

.no-data {
  color: var(--text-tertiary);
  font-size: 14px;
  text-align: center;
  padding: 40px;
}
</style>

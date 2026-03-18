<template>
  <div class="ais-pipeline">
    <!-- Header -->
    <div class="ais-header">
      <router-link to="/" class="back-link">&larr; Dashboard</router-link>
      <div class="ais-brand">
        <span class="ais-title">Agent AiS</span>
        <span class="ais-sub">AI Scientist Pipeline</span>
      </div>
      <div class="header-actions">
        <button class="btn-secondary" @click="showHistory = !showHistory">
          {{ showHistory ? 'Hide History' : 'Past Runs' }}
        </button>
        <button class="theme-toggle" @click="toggleTheme" :title="isDark ? 'Light' : 'Dark'">
          <span v-if="isDark">&#9788;</span>
          <span v-else>&#9790;</span>
        </button>
      </div>
    </div>

    <!-- Run History Panel -->
    <div v-if="showHistory" class="history-panel">
      <h3>Pipeline Runs</h3>
      <div v-if="runs.length === 0" class="empty-state">No runs yet.</div>
      <div v-for="run in runs" :key="run.run_id" class="history-item" @click="loadRun(run.run_id)">
        <div class="history-meta">
          <span class="history-id">{{ run.run_id.slice(0, 12) }}...</span>
          <span class="history-status" :class="run.status">{{ run.status }}</span>
        </div>
        <div class="history-idea">{{ run.research_idea || 'Untitled' }}</div>
        <div class="history-date">{{ formatDate(run.created_at) }}</div>
      </div>
    </div>

    <!-- Stage Progress Tracker -->
    <div class="stage-tracker">
      <div
        v-for="(stage, idx) in stages"
        :key="idx"
        class="stage-step"
        :class="{
          active: currentStage === idx + 1,
          completed: currentStage > idx + 1 || pipelineStatus === 'completed',
          failed: pipelineStatus === 'failed' && currentStage === idx + 1,
        }"
      >
        <div class="stage-dot">
          <span v-if="currentStage > idx + 1 || pipelineStatus === 'completed'">&#10003;</span>
          <span v-else-if="pipelineStatus === 'failed' && currentStage === idx + 1">&#10007;</span>
          <span v-else>{{ idx + 1 }}</span>
        </div>
        <div class="stage-label">{{ stage }}</div>
        <div class="stage-connector" v-if="idx < stages.length - 1"></div>
      </div>
    </div>

    <!-- Main Content Area -->
    <div class="ais-content">

      <!-- Stage 0: Start Form (no run yet) -->
      <div v-if="!runId" class="stage-panel start-panel">
        <h2>Start a New Research Pipeline</h2>
        <div class="form-group">
          <label>Research Idea / Question</label>
          <textarea
            v-model="startForm.research_idea"
            rows="3"
            placeholder="e.g. Can transformer attention patterns predict protein folding accuracy?"
            class="form-input form-textarea"
          ></textarea>
        </div>
        <div class="form-group">
          <label>Data Sources</label>
          <div class="checkbox-group">
            <label class="checkbox-item" v-for="src in availableSources" :key="src.value">
              <input type="checkbox" v-model="startForm.sources" :value="src.value" />
              <span>{{ src.label }}</span>
            </label>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group half">
            <label>Max Papers</label>
            <input v-model.number="startForm.max_papers" type="number" min="10" max="500" class="form-input" />
          </div>
          <div class="form-group half">
            <label>Ideas to Generate</label>
            <input v-model.number="startForm.num_ideas" type="number" min="3" max="20" class="form-input" />
          </div>
        </div>
        <div class="form-group">
          <label>Reflection Rounds</label>
          <input v-model.number="startForm.num_reflections" type="number" min="1" max="5" class="form-input" />
          <span class="form-hint">More rounds = higher quality ideas, slower generation</span>
        </div>
        <button class="btn-primary btn-large" @click="startPipeline" :disabled="starting || !startForm.research_idea.trim()">
          {{ starting ? 'Starting...' : 'Launch Pipeline' }}
        </button>
      </div>

      <!-- Progress Bar (active pipeline) -->
      <div v-if="runId && taskMessage" class="progress-section">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: taskProgress + '%' }"></div>
        </div>
        <span class="progress-text">{{ taskMessage }}</span>
      </div>

      <!-- Error display -->
      <div v-if="error" class="error-banner">
        <span class="error-icon">&#9888;</span>
        <span>{{ error }}</span>
        <button class="btn-clear" @click="error = null">&times;</button>
      </div>

      <!-- Stage 2 Output: Idea Selection -->
      <div v-if="showIdeas" class="stage-panel ideas-panel">
        <h2>Research Ideas — Select One to Continue</h2>
        <p class="panel-desc">{{ ideas.length }} ideas generated. Select the most promising direction for debate.</p>
        <div class="idea-grid">
          <div
            v-for="(idea, ideaIdx) in ideas"
            :key="idea.idea_id"
            class="idea-card"
            :class="{ selected: selectedIdeaId === idea.idea_id }"
            @click="selectedIdeaId = idea.idea_id"
          >
            <div class="idea-header">
              <span class="idea-rank">#{{ ideaIdx + 1 }}</span>
              <span class="idea-score">{{ idea.composite_score?.toFixed(1) || '?' }}</span>
            </div>
            <h3 class="idea-title">{{ idea.title }}</h3>
            <p class="idea-hypothesis">{{ idea.hypothesis }}</p>
            <div class="idea-metrics">
              <span class="metric" title="Interestingness">
                <span class="metric-icon">&#9733;</span> {{ idea.interestingness }}
              </span>
              <span class="metric" title="Feasibility">
                <span class="metric-icon">&#9881;</span> {{ idea.feasibility }}
              </span>
              <span class="metric" title="Novelty">
                <span class="metric-icon">&#9670;</span> {{ idea.novelty }}
              </span>
            </div>
            <div class="idea-methodology" v-if="expandedIdea === idea.idea_id">
              <strong>Methodology:</strong> {{ idea.methodology }}
              <br/>
              <strong>Contribution:</strong> {{ idea.expected_contribution }}
              <div v-if="idea.grounding_papers && idea.grounding_papers.length > 0" class="idea-papers">
                <strong>Grounding Papers:</strong> {{ idea.grounding_papers.length }} references
              </div>
            </div>
            <button class="btn-expand" @click.stop="expandedIdea = expandedIdea === idea.idea_id ? null : idea.idea_id">
              {{ expandedIdea === idea.idea_id ? 'Less' : 'More' }}
            </button>
          </div>
        </div>
        <div class="idea-actions">
          <button
            class="btn-primary btn-large"
            @click="confirmIdeaSelection"
            :disabled="!selectedIdeaId || selectingIdea"
          >
            {{ selectingIdea ? 'Selecting...' : 'Select & Continue to Debate' }}
          </button>
        </div>
      </div>

      <!-- Stage 3: Debate Status -->
      <div v-if="showDebate" class="stage-panel debate-panel">
        <h2>Agent Debate</h2>
        <div v-if="debating" class="debate-waiting">
          <div class="spinner"></div>
          <p>Agents are debating the selected research direction...</p>
          <p class="progress-text">{{ taskMessage }}</p>
        </div>
        <div v-else-if="debateResult" class="debate-result">
          <div class="debate-stats">
            <div class="stat-card">
              <span class="stat-value">{{ debateResult.agent_count || '?' }}</span>
              <span class="stat-label">Agents</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ debateResult.rounds_completed || '?' }}</span>
              <span class="stat-label">Rounds</span>
            </div>
          </div>
          <div class="debate-actions">
            <button class="btn-primary btn-large" @click="approveAndDraft" :disabled="approving">
              {{ approving ? 'Approving...' : 'Approve & Generate Paper Draft' }}
            </button>
          </div>
        </div>
        <div v-else class="debate-start">
          <p>Idea selected. Ready to start agent debate.</p>
          <button class="btn-primary" @click="triggerDebate" :disabled="debating">Start Debate</button>
        </div>
      </div>

      <!-- Stage 5: Draft Viewer -->
      <div v-if="showDraft" class="stage-panel draft-panel">
        <h2>Paper Draft</h2>
        <div v-if="drafting" class="draft-waiting">
          <div class="spinner"></div>
          <p>Generating paper draft with self-review...</p>
          <p class="progress-text">{{ taskMessage }}</p>
        </div>
        <div v-else-if="draft" class="draft-content">
          <!-- Review summary -->
          <div v-if="draft.review" class="review-summary">
            <div class="review-score" :class="reviewClass">
              {{ draft.review.overall }}/10
            </div>
            <span class="review-decision">{{ draft.review.decision }}</span>
          </div>

          <h1 class="draft-title">{{ draft.title }}</h1>

          <!-- Section tabs -->
          <div class="section-tabs">
            <button
              v-for="(section, idx) in draft.sections"
              :key="idx"
              class="section-tab"
              :class="{ active: activeSection === idx }"
              @click="activeSection = idx"
            >
              {{ section.heading }}
            </button>
          </div>

          <!-- Active section content -->
          <div v-if="draft.sections[activeSection]" class="section-content">
            <h2>{{ draft.sections[activeSection].heading }}</h2>
            <div class="section-body-text" v-html="renderMarkdown(draft.sections[activeSection].content)"></div>
            <div class="section-meta">
              {{ draft.sections[activeSection].word_count }} words
            </div>
          </div>

          <!-- Bibliography -->
          <div v-if="showBibliography" class="bibliography">
            <h2>Bibliography</h2>
            <div v-for="(entry, idx) in draft.bibliography" :key="idx" class="bib-entry">
              <span class="bib-key">[{{ entry.key }}]</span>
              <span class="bib-text">{{ entry.authors?.join(', ') }} ({{ entry.year }}). <em>{{ entry.title }}</em></span>
            </div>
          </div>

          <!-- Draft actions -->
          <div class="draft-actions">
            <button class="btn-secondary" @click="showBibliography = !showBibliography">
              {{ showBibliography ? 'Hide' : 'Show' }} Bibliography ({{ draft.bibliography?.length || 0 }})
            </button>
            <button class="btn-primary" @click="exportMarkdown">Export Markdown</button>
          </div>
        </div>
      </div>

      <!-- Completed State -->
      <div v-if="pipelineStatus === 'completed' && !showDraft" class="stage-panel completed-panel">
        <div class="completed-icon">&#10003;</div>
        <h2>Pipeline Complete</h2>
        <p>Paper draft has been generated and reviewed.</p>
        <button class="btn-primary" @click="viewDraft">View Draft</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import {
  startPipeline as apiStart,
  getPipelineStatus,
  getIdeas as apiGetIdeas,
  selectIdea as apiSelectIdea,
  startDebate as apiStartDebate,
  approveDraft as apiApproveDraft,
  getDraft as apiGetDraft,
  exportDraft as apiExportDraft,
  listRuns as apiListRuns,
  pollPipeline,
} from '../api/ais.js'

// Theme
const isDark = ref(document.documentElement.getAttribute('data-theme') === 'dark')
function toggleTheme() {
  isDark.value = !isDark.value
  const theme = isDark.value ? 'dark' : 'light'
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem('ossr-theme', theme)
}

// Pipeline stages
const stages = ['Crawl & Map', 'Ideate', 'Debate', 'Human Review', 'Paper Draft']

const availableSources = [
  { label: 'arXiv', value: 'arxiv' },
  { label: 'Semantic Scholar', value: 'semantic_scholar' },
  { label: 'OpenAlex', value: 'openalex' },
  { label: 'bioRxiv', value: 'biorxiv' },
  { label: 'OpenReview', value: 'openreview' },
  { label: 'IEEE Xplore', value: 'ieee' },
]

// State
const runId = ref(null)
const pipelineStatus = ref(null)
const currentStage = ref(0)
const error = ref(null)
const taskMessage = ref('')
const taskProgress = ref(0)

// Start form
const startForm = reactive({
  research_idea: '',
  sources: ['arxiv', 'semantic_scholar', 'openalex'],
  max_papers: 100,
  num_ideas: 10,
  num_reflections: 3,
})
const starting = ref(false)

// Ideas
const ideas = ref([])
const selectedIdeaId = ref(null)
const expandedIdea = ref(null)
const selectingIdea = ref(false)

// Debate
const debating = ref(false)
const debateResult = ref(null)
const approving = ref(false)

// Draft
const drafting = ref(false)
const draft = ref(null)
const activeSection = ref(0)
const showBibliography = ref(false)

// History
const showHistory = ref(false)
const runs = ref([])

// Computed visibility
const showIdeas = computed(() => {
  return runId.value && ideas.value.length > 0 &&
    ['awaiting_selection'].includes(pipelineStatus.value)
})

const showDebate = computed(() => {
  return runId.value &&
    ['debating', 'human_review'].includes(pipelineStatus.value)
})

const showDraft = computed(() => {
  return runId.value &&
    ['drafting', 'reviewing', 'completed'].includes(pipelineStatus.value) &&
    (draft.value || drafting.value)
})

const reviewClass = computed(() => {
  if (!draft.value?.review) return ''
  const score = draft.value.review.overall
  if (score >= 7) return 'score-high'
  if (score >= 5) return 'score-mid'
  return 'score-low'
})

// Actions
async function startPipeline() {
  starting.value = true
  error.value = null
  try {
    const res = await apiStart(startForm)
    const data = res.data.data
    runId.value = data.run_id
    currentStage.value = 1
    pipelineStatus.value = 'crawling'
    taskMessage.value = 'Starting pipeline...'
    taskProgress.value = 0
    pollForIdeas(data.run_id, data.task_id)
  } catch (err) {
    error.value = err.message || 'Failed to start pipeline'
  } finally {
    starting.value = false
  }
}

async function pollForIdeas(rId, taskId) {
  try {
    const finalStatus = await pollPipeline(
      rId,
      ['awaiting_selection'],
      (data) => {
        pipelineStatus.value = data.status
        currentStage.value = data.current_stage || 1
        taskMessage.value = data.task_message || data.status
        taskProgress.value = data.task_progress || 0
      },
      3000
    )
    if (finalStatus.status === 'awaiting_selection') {
      currentStage.value = 2
      await fetchIdeas()
    } else if (finalStatus.status === 'failed') {
      error.value = finalStatus.error || 'Pipeline failed during Stages 1-2'
    }
  } catch (err) {
    error.value = err.message || 'Lost connection to pipeline'
  }
  taskMessage.value = ''
}

async function fetchIdeas() {
  try {
    const res = await apiGetIdeas(runId.value)
    ideas.value = res.data.data?.ideas || []
  } catch (err) {
    error.value = err.message || 'Failed to fetch ideas'
  }
}

async function confirmIdeaSelection() {
  if (!selectedIdeaId.value) return
  selectingIdea.value = true
  error.value = null
  try {
    await apiSelectIdea(runId.value, selectedIdeaId.value)
    pipelineStatus.value = 'debating'
    currentStage.value = 3
  } catch (err) {
    error.value = err.message || 'Failed to select idea'
  } finally {
    selectingIdea.value = false
  }
}

async function triggerDebate() {
  debating.value = true
  error.value = null
  taskMessage.value = 'Starting agent debate...'
  try {
    const res = await apiStartDebate(runId.value)
    const taskId = res.data.data?.task_id
    // Poll for debate completion
    const finalStatus = await pollPipeline(
      runId.value,
      ['human_review'],
      (data) => {
        pipelineStatus.value = data.status
        currentStage.value = data.current_stage || 3
        taskMessage.value = data.task_message || 'Debating...'
        taskProgress.value = data.task_progress || 0
      },
      3000
    )
    if (finalStatus.status === 'human_review') {
      debateResult.value = finalStatus.stage_results?.stage_3 || { agent_count: '?', rounds_completed: '?' }
      pipelineStatus.value = 'human_review'
      currentStage.value = 4
    } else if (finalStatus.status === 'failed') {
      error.value = finalStatus.error || 'Debate failed'
    }
  } catch (err) {
    error.value = err.message || 'Failed to run debate'
  } finally {
    debating.value = false
    taskMessage.value = ''
  }
}

async function approveAndDraft() {
  approving.value = true
  drafting.value = true
  error.value = null
  taskMessage.value = 'Approving and starting draft generation...'
  try {
    const res = await apiApproveDraft(runId.value)
    const taskId = res.data.data?.task_id
    pipelineStatus.value = 'drafting'
    currentStage.value = 5

    // Poll for draft completion
    const finalStatus = await pollPipeline(
      runId.value,
      ['completed', 'reviewing'],
      (data) => {
        pipelineStatus.value = data.status
        currentStage.value = data.current_stage || 5
        taskMessage.value = data.task_message || 'Drafting...'
        taskProgress.value = data.task_progress || 0
      },
      3000
    )
    if (['completed', 'reviewing'].includes(finalStatus.status)) {
      await fetchDraft()
    } else if (finalStatus.status === 'failed') {
      error.value = finalStatus.error || 'Draft generation failed'
    }
  } catch (err) {
    error.value = err.message || 'Failed to generate draft'
  } finally {
    approving.value = false
    drafting.value = false
    taskMessage.value = ''
  }
}

async function fetchDraft() {
  try {
    const res = await apiGetDraft(runId.value)
    draft.value = res.data.data
    activeSection.value = 0
  } catch (err) {
    error.value = err.message || 'Failed to fetch draft'
  }
}

function viewDraft() {
  fetchDraft()
}

async function exportMarkdown() {
  try {
    const res = await apiExportDraft(runId.value, 'markdown')
    const markdown = res.data.data?.content || res.data.data?.markdown || ''
    const blob = new Blob([markdown], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ais-draft-${runId.value.slice(0, 8)}.md`
    a.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    error.value = err.message || 'Export failed'
  }
}

async function fetchRuns() {
  try {
    const res = await apiListRuns()
    runs.value = res.data.data?.runs || []
  } catch (err) {
    console.error('Failed to load runs:', err)
  }
}

async function loadRun(rId) {
  runId.value = rId
  showHistory.value = false
  error.value = null
  try {
    const res = await getPipelineStatus(rId)
    const data = res.data.data
    pipelineStatus.value = data.status
    currentStage.value = data.current_stage || 1
    debateResult.value = data.stage_results?.stage_3 || null

    if (data.status === 'awaiting_selection') {
      await fetchIdeas()
    } else if (['completed', 'reviewing'].includes(data.status)) {
      await fetchDraft()
    }
  } catch (err) {
    error.value = err.message || 'Failed to load run'
  }
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function renderMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>')
}

onMounted(() => {
  fetchRuns()
})

watch(showHistory, (val) => {
  if (val) fetchRuns()
})
</script>

<style scoped>
.ais-pipeline {
  min-height: 100vh;
  background: var(--bg-secondary);
  color: var(--text-primary);
}

/* Header */
.ais-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-primary);
}
.back-link {
  color: var(--os-brand);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
}
.back-link:hover { text-decoration: underline; }
.ais-brand { text-align: center; }
.ais-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--os-brand);
}
.ais-sub {
  display: block;
  font-size: 11px;
  color: var(--text-secondary);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.header-actions { display: flex; gap: 8px; align-items: center; }
.theme-toggle {
  background: none;
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-md);
  padding: 6px 10px;
  cursor: pointer;
  font-size: 16px;
  color: var(--text-primary);
}

/* History panel */
.history-panel {
  max-height: 300px;
  overflow-y: auto;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-primary);
  padding: 16px 24px;
}
.history-panel h3 {
  margin: 0 0 12px;
  font-size: 14px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.history-item {
  padding: 10px 12px;
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-md);
  margin-bottom: 8px;
  cursor: pointer;
  transition: border-color var(--transition-normal);
}
.history-item:hover { border-color: var(--os-brand); }
.history-meta { display: flex; justify-content: space-between; margin-bottom: 4px; }
.history-id { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--text-secondary); }
.history-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 600;
  text-transform: uppercase;
}
.history-status.completed { background: var(--semantic-success-bg, #dcfce7); color: var(--semantic-success, #22C55E); }
.history-status.failed { background: var(--semantic-error-bg, #fef2f2); color: var(--semantic-error, #EF4444); }
.history-status.awaiting_selection { background: var(--semantic-warning-bg, #fffbeb); color: var(--semantic-warning, #F59E0B); }
.history-idea { font-size: 13px; color: var(--text-primary); }
.history-date { font-size: 11px; color: var(--text-secondary); margin-top: 4px; }

/* Stage tracker */
.stage-tracker {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 24px;
  gap: 0;
}
.stage-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  flex: 1;
  max-width: 160px;
}
.stage-dot {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--bg-primary);
  border: 2px solid var(--border-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  z-index: 1;
  transition: all var(--transition-normal);
}
.stage-step.active .stage-dot {
  border-color: var(--os-brand);
  color: var(--os-brand);
  box-shadow: 0 0 0 4px var(--os-brand-subtle, rgba(30, 168, 142, 0.15));
}
.stage-step.completed .stage-dot {
  background: var(--os-brand);
  border-color: var(--os-brand);
  color: white;
}
.stage-step.failed .stage-dot {
  background: var(--semantic-error, #EF4444);
  border-color: var(--semantic-error, #EF4444);
  color: white;
}
.stage-label {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  text-align: center;
  font-weight: 500;
}
.stage-step.active .stage-label { color: var(--os-brand); font-weight: 600; }
.stage-connector {
  position: absolute;
  top: 18px;
  left: 50%;
  width: 100%;
  height: 2px;
  background: var(--border-primary);
  z-index: 0;
}
.stage-step.completed .stage-connector { background: var(--os-brand); }

/* Content area */
.ais-content {
  max-width: 960px;
  margin: 0 auto;
  padding: 0 24px 48px;
}
.stage-panel {
  background: var(--bg-primary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-lg, 10px);
  padding: 28px;
  box-shadow: var(--shadow-md);
}
.stage-panel h2 {
  margin: 0 0 8px;
  font-size: 18px;
  color: var(--text-primary);
}
.panel-desc {
  color: var(--text-secondary);
  font-size: 13px;
  margin: 0 0 20px;
}

/* Forms */
.form-group { margin-bottom: 16px; }
.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}
.form-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-md);
  font-size: 14px;
  background: var(--bg-primary);
  color: var(--text-primary);
  transition: border-color var(--transition-normal);
  box-sizing: border-box;
}
.form-input:focus { border-color: var(--os-brand); outline: none; }
.form-textarea { resize: vertical; font-family: inherit; }
.form-hint { font-size: 11px; color: var(--text-secondary); margin-top: 4px; display: block; }
.form-row { display: flex; gap: 12px; }
.form-group.half { flex: 1; }
.checkbox-group { display: flex; flex-wrap: wrap; gap: 8px 16px; }
.checkbox-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  cursor: pointer;
}

/* Buttons */
.btn-primary {
  background: var(--os-brand);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: background var(--transition-normal);
}
.btn-primary:hover { background: var(--os-brand-hover, #178f7a); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-large { padding: 14px 28px; font-size: 15px; }
.btn-secondary {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-primary);
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-weight: 500;
  font-size: 13px;
  cursor: pointer;
  transition: border-color var(--transition-normal);
}
.btn-secondary:hover { border-color: var(--os-brand); }
.btn-clear {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 18px;
  cursor: pointer;
  padding: 0 4px;
}

/* Progress */
.progress-section {
  margin-bottom: 20px;
  background: var(--bg-primary);
  padding: 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-primary);
}
.progress-bar {
  height: 6px;
  background: var(--border-primary);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 8px;
}
.progress-fill {
  height: 100%;
  background: var(--os-brand);
  border-radius: 3px;
  transition: width 0.3s ease;
}
.progress-text {
  font-size: 12px;
  color: var(--text-secondary);
}

/* Error */
.error-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--semantic-error-bg, #fef2f2);
  border: 1px solid var(--semantic-error, #EF4444);
  border-radius: var(--radius-md);
  margin-bottom: 20px;
  color: var(--semantic-error, #EF4444);
  font-size: 13px;
}
.error-icon { font-size: 18px; }

/* Idea cards */
.idea-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}
.idea-card {
  background: var(--bg-secondary);
  border: 2px solid transparent;
  border-radius: var(--radius-md);
  padding: 16px;
  cursor: pointer;
  transition: all var(--transition-normal);
}
.idea-card:hover { border-color: var(--os-brand-light, #8dd8c8); }
.idea-card.selected {
  border-color: var(--os-brand);
  box-shadow: 0 0 0 3px var(--os-brand-subtle, rgba(30, 168, 142, 0.15));
}
.idea-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.idea-rank {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
}
.idea-score {
  font-size: 14px;
  font-weight: 700;
  color: var(--os-brand);
  background: var(--os-brand-subtle, rgba(30, 168, 142, 0.1));
  padding: 2px 8px;
  border-radius: 12px;
}
.idea-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 6px;
  color: var(--text-primary);
}
.idea-hypothesis {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0 0 10px;
  line-height: 1.5;
}
.idea-metrics {
  display: flex;
  gap: 12px;
}
.metric {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 3px;
}
.metric-icon { font-size: 14px; }
.idea-methodology {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-primary);
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}
.idea-papers {
  margin-top: 8px;
  font-size: 11px;
}
.btn-expand {
  margin-top: 8px;
  background: none;
  border: none;
  color: var(--os-brand);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
  font-weight: 500;
}
.idea-actions {
  display: flex;
  justify-content: center;
  padding-top: 8px;
}

/* Debate */
.debate-waiting, .draft-waiting {
  text-align: center;
  padding: 32px;
}
.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border-primary);
  border-top-color: var(--os-brand);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 16px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.debate-stats {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-bottom: 24px;
}
.stat-card {
  text-align: center;
  padding: 16px 24px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-primary);
}
.stat-value {
  display: block;
  font-size: 28px;
  font-weight: 700;
  color: var(--os-brand);
}
.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.debate-actions, .debate-start {
  text-align: center;
}

/* Draft */
.review-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding: 12px 16px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}
.review-score {
  font-size: 24px;
  font-weight: 700;
  padding: 4px 12px;
  border-radius: var(--radius-md);
}
.review-score.score-high { color: var(--semantic-success, #22C55E); }
.review-score.score-mid { color: var(--semantic-warning, #F59E0B); }
.review-score.score-low { color: var(--semantic-error, #EF4444); }
.review-decision {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.draft-title {
  font-size: 22px;
  margin: 0 0 20px;
  color: var(--text-primary);
  line-height: 1.3;
}
.section-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--border-primary);
  padding-bottom: 8px;
}
.section-tab {
  padding: 8px 14px;
  background: none;
  border: 1px solid transparent;
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  font-size: 13px;
  cursor: pointer;
  color: var(--text-secondary);
  font-weight: 500;
  transition: all var(--transition-normal);
}
.section-tab.active {
  border-color: var(--border-primary);
  border-bottom-color: var(--bg-primary);
  color: var(--os-brand);
  font-weight: 600;
  background: var(--bg-primary);
}
.section-tab:hover:not(.active) { color: var(--text-primary); }
.section-content {
  padding: 20px 0;
}
.section-content h2 {
  font-size: 16px;
  margin: 0 0 16px;
}
.section-body-text {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
}
.section-body-text p { margin: 0 0 12px; }
.section-meta {
  margin-top: 16px;
  font-size: 11px;
  color: var(--text-secondary);
}
.bibliography {
  border-top: 1px solid var(--border-primary);
  padding-top: 20px;
  margin-top: 20px;
}
.bib-entry {
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}
.bib-key {
  font-family: 'JetBrains Mono', monospace;
  color: var(--os-brand);
  margin-right: 8px;
}
.draft-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--border-primary);
}

/* Completed */
.completed-panel {
  text-align: center;
  padding: 48px;
}
.completed-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--os-brand);
  color: white;
  font-size: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}

/* Empty state */
.empty-state {
  text-align: center;
  padding: 24px;
  color: var(--text-secondary);
  font-size: 13px;
}
</style>

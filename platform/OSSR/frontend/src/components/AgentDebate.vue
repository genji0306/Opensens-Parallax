<template>
  <div class="agent-debate-panel">
    <div class="panel-header">
      <span class="panel-title">Research Discussion</span>
      <div class="header-tools">
        <span v-if="simStatus" class="status-badge" :class="simStatus.status">
          {{ simStatus.status }}
        </span>
        <span v-if="simStatus" class="round-badge">
          Round {{ simStatus.current_round || 0 }}/{{ simStatus.max_rounds || '?' }}
        </span>
      </div>
    </div>

    <!-- Setup panel (before simulation starts) -->
    <div v-if="!simulationId" class="setup-panel">
      <div class="setup-section">
        <label class="form-label">Discussion Mode</label>
        <div class="mode-selector">
          <button class="mode-btn" :class="{ active: discussionMode === 'text' }" @click="discussionMode = 'text'">
            <svg class="mode-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
              <path d="M4 6h16M4 10h16M4 14h10M4 18h6"/>
            </svg>
            <span class="mode-label">Text</span>
            <span class="mode-desc">Classic transcript view</span>
          </button>
          <button class="mode-btn" :class="{ active: discussionMode === 'visual' }" @click="discussionMode = 'visual'">
            <svg class="mode-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
              <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z"/>
              <path d="M12 12l8-4.5"/>
              <path d="M12 12v9"/>
              <path d="M12 12L4 7.5"/>
            </svg>
            <span class="mode-label">Visual</span>
            <span class="mode-desc">2D/3D Agent Office</span>
          </button>
          <button class="mode-btn" :class="{ active: discussionMode === 'orchestrated' }" @click="discussionMode = 'orchestrated'">
            <svg class="mode-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
              <circle cx="12" cy="12" r="3"/>
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
            </svg>
            <span class="mode-label">Research</span>
            <span class="mode-desc">Mirofish orchestrated console</span>
          </button>
        </div>
      </div>

      <div class="setup-section">
        <label class="form-label">Discussion Format</label>
        <select v-model="setupForm.format" class="form-select">
          <option v-for="fmt in formats" :key="fmt.id" :value="fmt.id">
            {{ fmt.name }}
          </option>
        </select>
        <p class="format-desc" v-if="selectedFormat">{{ selectedFormat.description }}</p>
      </div>

      <div class="setup-section">
        <label class="form-label">Topic</label>
        <input v-model="setupForm.topic" type="text" class="form-input" placeholder="e.g., Future of EIT for neural monitoring" />
      </div>

      <div class="setup-section">
        <label class="form-label">Agents ({{ selectedAgentIds.length }} selected)</label>
        <div class="agent-picker">
          <div
            v-for="agent in availableAgents"
            :key="agent.agent_id"
            class="agent-chip"
            :class="{ selected: selectedAgentIds.includes(agent.agent_id) }"
            @click="toggleAgent(agent.agent_id)"
          >
            <span class="agent-role-dot" :style="{ background: roleColor(agent.role) }"></span>
            <span class="agent-chip-name">{{ agent.name }}</span>
            <span class="agent-chip-role">{{ agent.role }}</span>
            <span v-if="agentConfig[agent.agent_id]?.llm_provider" class="agent-model-tag">
              {{ agentConfig[agent.agent_id].llm_provider }}
            </span>
            <span v-if="agentConfig[agent.agent_id]?.is_super_agent" class="super-tag">S</span>
          </div>
          <div v-if="availableAgents.length === 0" class="empty-agents">
            No agents generated yet. Generate agents first.
          </div>
        </div>
      </div>

      <div class="setup-section">
        <label class="form-label">Rounds</label>
        <input v-model.number="setupForm.max_rounds" type="number" min="1" max="20" class="form-input small" />
      </div>

      <!-- Advanced Settings Toggle -->
      <div class="advanced-toggle" @click="showAdvanced = !showAdvanced">
        <span class="toggle-arrow" :class="{ open: showAdvanced }">&#9654;</span>
        <span class="toggle-label">Advanced Settings</span>
        <span class="toggle-hint" v-if="!showAdvanced">Multi-model, skills, super-agents</span>
      </div>

      <!-- Advanced Settings Panel -->
      <div v-if="showAdvanced" class="advanced-panel">
        <div v-if="selectedAgentIds.length === 0" class="advanced-empty">
          Select agents above to configure their models and skills.
        </div>

        <div v-for="agentId in selectedAgentIds" :key="agentId" class="agent-config-card">
          <div class="config-header">
            <span class="config-dot" :style="{ background: roleColor(getAgent(agentId)?.role) }"></span>
            <span class="config-name">{{ getAgent(agentId)?.name }}</span>
            <span class="config-role">{{ getAgent(agentId)?.role }}</span>
          </div>

          <div class="config-row">
            <div class="config-field">
              <label class="config-label">Provider</label>
              <select
                :value="agentConfig[agentId]?.llm_provider || ''"
                @change="setAgentConfig(agentId, 'llm_provider', $event.target.value)"
                class="config-select"
              >
                <option value="">Default ({{ defaultProvider }})</option>
                <option
                  v-for="(info, prov) in providers"
                  :key="prov"
                  :value="prov"
                  :disabled="!info.configured"
                >
                  {{ providerLabel(prov) }} {{ info.configured ? '' : '(no key)' }}
                </option>
              </select>
            </div>

            <div class="config-field">
              <label class="config-label">Model</label>
              <select
                :value="agentConfig[agentId]?.llm_model || ''"
                @change="setAgentConfig(agentId, 'llm_model', $event.target.value)"
                class="config-select"
              >
                <option value="">Default</option>
                <option
                  v-for="m in modelsForAgent(agentId)"
                  :key="m.id"
                  :value="m.id"
                >
                  {{ m.name }} ({{ m.tier }})
                </option>
              </select>
            </div>
          </div>

          <div class="config-row">
            <div class="config-field full">
              <label class="config-label">Skills</label>
              <div class="skills-picker">
                <input
                  type="text"
                  class="skills-search"
                  placeholder="Search skills..."
                  :value="skillSearch[agentId] || ''"
                  @input="skillSearch[agentId] = $event.target.value"
                  @focus="activeSkillPicker = agentId"
                />
                <div v-if="agentConfig[agentId]?.skills?.length" class="skill-tags">
                  <span
                    v-for="s in agentConfig[agentId].skills"
                    :key="s"
                    class="skill-tag"
                    @click="removeSkill(agentId, s)"
                  >{{ s }} &times;</span>
                </div>
                <div v-if="activeSkillPicker === agentId && filteredSkills(agentId).length > 0" class="skills-dropdown">
                  <div
                    v-for="skill in filteredSkills(agentId)"
                    :key="skill.name"
                    class="skill-option"
                    @mousedown.prevent="addSkill(agentId, skill.name)"
                  >
                    <span class="skill-cat" :class="skill.category">{{ skill.category }}</span>
                    <span class="skill-name">{{ skill.name }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="config-row">
            <label class="super-agent-toggle">
              <input
                type="checkbox"
                :checked="agentConfig[agentId]?.is_super_agent || false"
                @change="setAgentConfig(agentId, 'is_super_agent', $event.target.checked)"
              />
              <span class="super-label">Super Agent</span>
              <span class="super-desc">Can generate code, math, and simulations</span>
            </label>
          </div>
        </div>

        <!-- Quick presets -->
        <div class="presets-row" v-if="selectedAgentIds.length >= 2">
          <span class="presets-label">Presets:</span>
          <button class="preset-btn" @click="applyPreset('multimodel')">Multi-Model Debate</button>
          <button class="preset-btn" @click="applyPreset('opus-lead')">Opus Lead + Sonnet</button>
          <button class="preset-btn" @click="applyPreset('all-super')">All Super Agents</button>
        </div>
      </div>

      <button
        class="btn-primary"
        :class="{ 'btn-visual': discussionMode === 'visual' }"
        @click="createAndStart"
        :disabled="!canStart || running"
      >
        {{ running ? 'Starting...' : discussionMode === 'visual' ? 'Open in Agent Office \u2192' : discussionMode === 'orchestrated' ? 'Open Research Console \u2192' : 'Start Discussion' }}
      </button>
    </div>

    <!-- Transcript viewer (during/after simulation) -->
    <div v-else class="transcript-panel">
      <!-- Back button bar -->
      <div class="transcript-toolbar">
        <button class="btn-back" @click="resetSimulation" :disabled="running">
          &#9664; New Discussion
        </button>
        <div class="toolbar-right">
          <button v-if="simStatus?.status === 'completed'" class="btn-whatif" @click="showForkPanel = !showForkPanel">
            What If?
          </button>
          <span v-if="simStatus" class="toolbar-status">
            {{ simStatus.status === 'running' ? 'In progress...' : simStatus.status }}
          </span>
        </div>
      </div>

      <!-- Round navigation -->
      <div class="round-nav" v-if="maxRound > 0">
        <button
          v-for="r in maxRound"
          :key="r"
          class="round-btn"
          :class="{ active: selectedRound === r || selectedRound === null }"
          @click="selectedRound = selectedRound === r ? null : r"
        >
          R{{ r }}
        </button>
        <button class="round-btn" :class="{ active: selectedRound === null }" @click="selectedRound = null">
          All
        </button>
      </div>

      <!-- Fork Panel ("What If?") -->
      <div v-if="showForkPanel" class="fork-panel">
        <div class="fork-header">Fork Simulation</div>
        <div class="fork-group">
          <label>Fork from Round</label>
          <input v-model.number="forkForm.from_round" type="range"
                 :min="1" :max="simStatus?.current_round || 3" class="fork-slider" />
          <span class="fork-round-label">Round {{ forkForm.from_round }}</span>
        </div>
        <div class="fork-group">
          <label>Change Format</label>
          <select v-model="forkForm.format" class="fork-select">
            <option value="">Keep current</option>
            <option v-for="fmt in formats" :key="fmt.id" :value="fmt.id">{{ fmt.name }}</option>
          </select>
        </div>
        <div class="fork-group">
          <label>Max Rounds</label>
          <input v-model.number="forkForm.max_rounds" type="number" min="1" max="20" class="fork-input" />
        </div>
        <button class="btn-fork" @click="executeFork" :disabled="forkLoading">
          {{ forkLoading ? 'Forking...' : 'Fork & Start' }}
        </button>
      </div>

      <!-- Turns -->
      <div class="turns-list" ref="turnsList">
        <div
          v-for="turn in filteredTranscript"
          :key="turn.turn_id"
          class="turn-card"
          :class="[turn.turn_type, { highlight: turn.agent_id === highlightedAgent }]"
        >
          <div class="turn-header">
            <span class="turn-agent-dot" :style="{ background: roleColor(turn.agent_role) }"></span>
            <span class="turn-agent-name clickable" @click="openAgentChat(turn.agent_id, turn.agent_name)">{{ turn.agent_name }}</span>
            <span class="turn-role">{{ turn.agent_role }}</span>
            <span v-if="turn.llm_model" class="turn-model-badge">{{ shortModel(turn.llm_model) }}</span>
            <span class="turn-type-badge">{{ turn.turn_type }}</span>
            <span class="turn-round">R{{ turn.round_num }}</span>
          </div>
          <div class="turn-content" v-html="renderContent(turn.content)"></div>
          <div v-if="turn.cited_dois && turn.cited_dois.length > 0" class="turn-citations">
            <span class="citation-label">Cited:</span>
            <span v-for="doi in turn.cited_dois" :key="doi" class="citation-doi">{{ doi }}</span>
          </div>
        </div>

        <div v-if="filteredTranscript.length === 0" class="empty-transcript">
          <p v-if="simStatus && simStatus.status === 'running'">Discussion in progress...</p>
          <p v-else>No discussion turns yet.</p>
        </div>
      </div>

      <!-- Paper injection (longitudinal only) -->
      <div v-if="isLongitudinal && simStatus && simStatus.status === 'running'" class="inject-bar">
        <input v-model="injectDoi" type="text" class="form-input" placeholder="Inject paper DOI..." />
        <button class="btn-inject" @click="doInjectPaper" :disabled="!injectDoi.trim()">Inject</button>
      </div>

      <!-- Report section (after simulation completes) -->
      <div v-if="simStatus && simStatus.status === 'completed'" class="report-section">
        <div v-if="!report" class="report-generate">
          <button class="btn-primary" @click="generateEvolutionReport" :disabled="generatingReport">
            {{ generatingReport ? 'Generating Report...' : 'Generate Analysis Report' }}
          </button>
          <div v-if="reportTask" class="report-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: (reportTask.progress || 0) + '%' }"></div>
            </div>
            <span class="progress-text">{{ reportTask.message || 'Working...' }}</span>
          </div>
        </div>
        <div v-else class="report-display">
          <div class="report-header">
            <span class="report-title">{{ report.title }}</span>
            <div class="report-header-actions">
              <button class="btn-sm" @click="openReportChat(report.report_id || reportTask?.result?.report_id)">Chat</button>
              <div class="export-dropdown">
                <button class="btn-sm" @click="toggleExportMenu" :disabled="exportLoading">
                  {{ exportLoading ? 'Exporting...' : 'Export' }}
                </button>
                <div v-if="exportMenuOpen" class="export-menu">
                  <button class="export-item" @click="downloadReport('pptx')">PowerPoint</button>
                  <button class="export-item" @click="downloadReport('audio')">Audio (MP3)</button>
                  <button class="export-item" @click="downloadReport('markdown')">Markdown</button>
                  <button class="export-item" @click="downloadReport('json')">JSON</button>
                </div>
              </div>
              <button class="btn-sm" @click="report = null">Close</button>
            </div>
          </div>
          <p class="report-summary">{{ report.summary }}</p>
          <div v-for="(sec, idx) in report.sections" :key="idx" class="report-sec">
            <h4 class="report-sec-title">{{ sec.title }}</h4>
            <div class="report-sec-content" v-html="renderMarkdown(sec.content)"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Chat Panel -->
    <div v-if="chatOpen" class="chat-panel">
      <div class="chat-header">
        <span class="chat-title">
          {{ chatMode === 'agent' ? `Chat with ${chatAgentName}` : 'Chat with Report' }}
        </span>
        <button class="chat-close" @click="chatOpen = false">&times;</button>
      </div>
      <div class="chat-messages" ref="chatMessagesEl">
        <div v-for="(msg, i) in chatMessages" :key="i"
             class="chat-msg" :class="msg.role">
          <div class="chat-msg-bubble">{{ msg.content }}</div>
        </div>
        <div v-if="chatLoading" class="chat-loading">Thinking...</div>
      </div>
      <div class="chat-input-bar">
        <input v-model="chatInput" type="text" class="chat-input"
               :placeholder="chatMode === 'agent' ? 'Ask this agent a question...' : 'Ask about the report...'"
               @keydown.enter="sendChatMessage"
               :disabled="chatLoading" />
        <button class="chat-send" @click="sendChatMessage"
                :disabled="!chatInput.trim() || chatLoading">Send</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  listFormats,
  listAgents,
  listModels,
  listSkills,
  configureAgent,
  createSimulation,
  startSimulation,
  getTranscript,
  pollSimulation,
  injectPaper,
  generateReport,
  getReport,
  pollReport,
  chatWithAgent,
  chatWithReport,
  forkSimulation,
  exportReport,
  downloadFile,
} from '../api/simulation.js'

const props = defineProps({
  topicIds: { type: Array, default: () => [] },
  topicNames: { type: Array, default: () => [] },
  highlightedAgent: { type: String, default: null },
})

const emit = defineEmits(['simulation-started', 'simulation-completed'])

const router = useRouter()

// State
const discussionMode = ref('text')  // 'text', 'visual', or 'orchestrated'
const AGENT_OFFICE_URL = 'http://localhost:5180'
const formats = ref([])
const availableAgents = ref([])
const simulationId = ref(null)
const simStatus = ref(null)
const transcript = ref([])
const selectedRound = ref(null)
const running = ref(false)
const injectDoi = ref('')
const turnsList = ref(null)
const generatingReport = ref(false)
const reportTask = ref(null)
const report = ref(null)
const exportMenuOpen = ref(false)
const exportLoading = ref(false)

// Chat panel state
const chatOpen = ref(false)
const chatAgentId = ref(null)
const chatAgentName = ref('')
const chatMessages = ref([])  // [{role: 'user'|'agent', content: '...'}]
const chatInput = ref('')
const chatLoading = ref(false)
const chatMode = ref('agent')  // 'agent' or 'report'
const currentReportId = ref(null)
const chatMessagesEl = ref(null)

// Fork panel state
const showForkPanel = ref(false)
const forkForm = reactive({
  from_round: 1,
  format: '',
  max_rounds: 0,
})
const forkLoading = ref(false)

// Advanced settings state
const showAdvanced = ref(false)
const providers = ref({})
const allSkills = ref([])
const agentConfig = reactive({})     // agentId -> { llm_provider, llm_model, skills, is_super_agent }
const skillSearch = reactive({})
const activeSkillPicker = ref(null)
const defaultProvider = ref('anthropic')

const setupForm = ref({
  format: 'conference',
  topic: '',
  max_rounds: 5,
})

const selectedAgentIds = ref([])

// Computed
const selectedFormat = computed(() => formats.value.find(f => f.id === setupForm.value.format))

const canStart = computed(() =>
  setupForm.value.topic.trim() && selectedAgentIds.value.length >= 2
)

const maxRound = computed(() => {
  if (transcript.value.length === 0) return 0
  return Math.max(...transcript.value.map(t => t.round_num))
})

const filteredTranscript = computed(() => {
  if (selectedRound.value === null) return transcript.value
  return transcript.value.filter(t => t.round_num === selectedRound.value)
})

const isLongitudinal = computed(() => setupForm.value.format === 'longitudinal')

// Methods
const ROLE_COLORS = {
  professor: 'var(--role-professor)',
  associate_professor: 'var(--role-assoc-professor)',
  assistant_professor: 'var(--role-assoc-professor)',
  postdoc: 'var(--role-postdoc)',
  phd_student: 'var(--role-phd)',
  industry_researcher: 'var(--role-industry)',
  reviewer: 'var(--role-reviewer)',
}

const PROVIDER_LABELS = {
  anthropic: 'Claude',
  openai: 'OpenAI',
  gemini: 'Gemini',
  perplexity: 'Perplexity',
}

function roleColor(role) {
  return ROLE_COLORS[role] || 'var(--text-tertiary)'
}

function providerLabel(prov) {
  return PROVIDER_LABELS[prov] || prov
}

function getAgent(agentId) {
  return availableAgents.value.find(a => a.agent_id === agentId)
}

function shortModel(model) {
  if (!model) return ''
  return model
    .replace('claude-sonnet-4-20250514', 'Sonnet 4')
    .replace('claude-opus-4-20250514', 'Opus 4')
    .replace('claude-haiku-4-5-20251001', 'Haiku 4.5')
    .replace('gpt-4o-mini', '4o-mini')
    .replace('gpt-4o', '4o')
    .replace('gemini-2.5-pro', 'Gem 2.5P')
    .replace('gemini-2.0-flash', 'Gem Flash')
    .replace('sonar-pro', 'Sonar Pro')
}

function modelsForAgent(agentId) {
  const prov = agentConfig[agentId]?.llm_provider || defaultProvider.value
  const info = providers.value[prov]
  return info?.models || []
}

function filteredSkills(agentId) {
  const query = (skillSearch[agentId] || '').toLowerCase()
  const current = agentConfig[agentId]?.skills || []
  return allSkills.value
    .filter(s => !current.includes(s.name))
    .filter(s => !query || s.name.includes(query) || s.description.toLowerCase().includes(query))
    .slice(0, 15)
}

function toggleAgent(agentId) {
  const idx = selectedAgentIds.value.indexOf(agentId)
  if (idx >= 0) {
    selectedAgentIds.value.splice(idx, 1)
  } else {
    selectedAgentIds.value.push(agentId)
    if (!agentConfig[agentId]) {
      agentConfig[agentId] = { llm_provider: '', llm_model: '', skills: [], is_super_agent: false }
    }
  }
}

function setAgentConfig(agentId, field, value) {
  if (!agentConfig[agentId]) {
    agentConfig[agentId] = { llm_provider: '', llm_model: '', skills: [], is_super_agent: false }
  }
  agentConfig[agentId][field] = value
  // Reset model when provider changes
  if (field === 'llm_provider') {
    agentConfig[agentId].llm_model = ''
  }
}

function addSkill(agentId, skillName) {
  if (!agentConfig[agentId]) {
    agentConfig[agentId] = { llm_provider: '', llm_model: '', skills: [], is_super_agent: false }
  }
  if (!agentConfig[agentId].skills.includes(skillName)) {
    agentConfig[agentId].skills.push(skillName)
  }
  skillSearch[agentId] = ''
  activeSkillPicker.value = null
}

function removeSkill(agentId, skillName) {
  if (agentConfig[agentId]?.skills) {
    agentConfig[agentId].skills = agentConfig[agentId].skills.filter(s => s !== skillName)
  }
}

function applyPreset(preset) {
  const ids = selectedAgentIds.value
  if (ids.length < 2) return

  if (preset === 'multimodel') {
    // Assign different providers round-robin
    const provList = Object.keys(providers.value).filter(p => providers.value[p].configured)
    ids.forEach((id, i) => {
      const prov = provList[i % provList.length]
      setAgentConfig(id, 'llm_provider', prov)
      setAgentConfig(id, 'llm_model', '')
    })
  } else if (preset === 'opus-lead') {
    // First agent gets Opus, rest get Sonnet
    ids.forEach((id, i) => {
      setAgentConfig(id, 'llm_provider', 'anthropic')
      setAgentConfig(id, 'llm_model', i === 0 ? 'claude-opus-4-20250514' : 'claude-sonnet-4-20250514')
    })
  } else if (preset === 'all-super') {
    ids.forEach(id => setAgentConfig(id, 'is_super_agent', true))
  }
}

// ── Chat panel methods ──────────────────────────────────────────────

function openAgentChat(agentId, agentName) {
  chatMode.value = 'agent'
  chatAgentId.value = agentId
  chatAgentName.value = agentName
  chatMessages.value = []
  chatInput.value = ''
  chatOpen.value = true
}

function openReportChat(reportId) {
  chatMode.value = 'report'
  currentReportId.value = reportId
  chatMessages.value = []
  chatInput.value = ''
  chatOpen.value = true
}

async function sendChatMessage() {
  if (!chatInput.value.trim() || chatLoading.value) return
  const msg = chatInput.value.trim()
  chatMessages.value.push({ role: 'user', content: msg })
  chatInput.value = ''
  chatLoading.value = true

  try {
    let res
    if (chatMode.value === 'agent') {
      res = await chatWithAgent(simulationId.value, chatAgentId.value, msg)
    } else {
      res = await chatWithReport(currentReportId.value, msg)
    }
    const data = res.data?.data || res.data
    chatMessages.value.push({ role: 'agent', content: data.response })
  } catch (e) {
    chatMessages.value.push({ role: 'agent', content: `Error: ${e.response?.data?.error || e.message}` })
  } finally {
    chatLoading.value = false
    await nextTick()
    if (chatMessagesEl.value) {
      chatMessagesEl.value.scrollTop = chatMessagesEl.value.scrollHeight
    }
  }
}

// ── Fork methods ────────────────────────────────────────────────────

async function executeFork() {
  if (forkLoading.value) return
  forkLoading.value = true
  try {
    const mods = {}
    if (forkForm.format) mods.format = forkForm.format
    if (forkForm.max_rounds > 0) mods.max_rounds = forkForm.max_rounds

    const res = await forkSimulation(simulationId.value, forkForm.from_round, mods)
    const forked = res.data?.data || res.data
    // Switch to the forked simulation
    simulationId.value = forked.simulation_id
    showForkPanel.value = false
    // Start the forked simulation
    await startSimulation(forked.simulation_id)
  } catch (e) {
    console.error('Fork failed:', e)
  } finally {
    forkLoading.value = false
  }
}

function resetSimulation() {
  simulationId.value = null
  simStatus.value = null
  transcript.value = []
  selectedRound.value = null
  running.value = false
  report.value = null
  reportTask.value = null
  generatingReport.value = false
}

// Data fetching
async function fetchFormats() {
  try {
    const res = await listFormats()
    formats.value = res.data?.data || res.data || []
  } catch (e) {
    console.warn('Failed to fetch formats:', e)
  }
}

async function fetchAgents() {
  try {
    const params = props.topicIds.length > 0
      ? { topic_ids: props.topicIds.join(',') }
      : {}
    const res = await listAgents(params)
    availableAgents.value = res.data?.data || res.data || []
  } catch (e) {
    console.warn('Failed to fetch agents:', e)
  }
}

async function fetchProviders() {
  try {
    const res = await listModels()
    providers.value = res.data?.data || res.data || {}
    // Find default provider
    for (const [name, info] of Object.entries(providers.value)) {
      if (info.configured) {
        defaultProvider.value = name
        break
      }
    }
  } catch (e) {
    console.warn('Failed to fetch providers:', e)
  }
}

async function fetchSkills() {
  try {
    const res = await listSkills()
    allSkills.value = res.data?.data || res.data || []
  } catch (e) {
    console.warn('Failed to fetch skills:', e)
  }
}

async function fetchTranscript() {
  if (!simulationId.value) return
  try {
    const res = await getTranscript(simulationId.value)
    transcript.value = res.data?.data || res.data || []
    await nextTick()
    scrollToBottom()
  } catch (e) {
    console.warn('Failed to fetch transcript:', e)
  }
}

function scrollToBottom() {
  if (turnsList.value) {
    turnsList.value.scrollTop = turnsList.value.scrollHeight
  }
}

async function createAndStart() {
  if (!canStart.value) return

  // Visual mode: open Agent Office in new tab with context params
  if (discussionMode.value === 'visual') {
    const params = new URLSearchParams({
      ossr: `${window.location.protocol}//${window.location.hostname}:5002`,
      topic: setupForm.value.topic,
      format: setupForm.value.format,
      rounds: String(setupForm.value.max_rounds),
      agents: selectedAgentIds.value.join(','),
    })
    window.open(`${AGENT_OFFICE_URL}/debate?${params.toString()}`, '_blank')
    return
  }

  // Orchestrated mode: create sim and navigate to Research Console
  if (discussionMode.value === 'orchestrated') {
    running.value = true
    try {
      for (const agentId of selectedAgentIds.value) {
        const cfg = agentConfig[agentId]
        if (cfg && (cfg.llm_provider || cfg.llm_model || cfg.skills?.length || cfg.is_super_agent)) {
          await configureAgent(agentId, cfg)
        }
      }

      const createRes = await createSimulation({
        orchestrated: true,
        format: setupForm.value.format,
        topic: setupForm.value.topic,
        agent_ids: selectedAgentIds.value,
        max_rounds: setupForm.value.max_rounds,
      })
      const simData = createRes.data?.data || createRes.data
      const simId = simData.simulation_id

      await startSimulation(simId)
      emit('simulation-started', simId)

      router.push({ name: 'console', params: { simId } })
    } catch (e) {
      console.error('Orchestrated simulation error:', e)
      alert('Failed to start orchestrated simulation: ' + e.message)
    } finally {
      running.value = false
    }
    return
  }

  // Text mode: run simulation inline
  running.value = true

  try {
    // Apply agent configurations via PATCH before starting
    for (const agentId of selectedAgentIds.value) {
      const cfg = agentConfig[agentId]
      if (cfg && (cfg.llm_provider || cfg.llm_model || cfg.skills?.length || cfg.is_super_agent)) {
        await configureAgent(agentId, cfg)
      }
    }

    const createRes = await createSimulation({
      format: setupForm.value.format,
      topic: setupForm.value.topic,
      agent_ids: selectedAgentIds.value,
      max_rounds: setupForm.value.max_rounds,
    })
    const simData = createRes.data?.data || createRes.data
    simulationId.value = simData.simulation_id

    await startSimulation(simulationId.value)
    emit('simulation-started', simulationId.value)

    const pollInterval = setInterval(fetchTranscript, 3000)

    await pollSimulation(simulationId.value, (status) => {
      simStatus.value = status
    })

    clearInterval(pollInterval)
    await fetchTranscript()
    emit('simulation-completed', simulationId.value)
  } catch (e) {
    console.error('Simulation error:', e)
    simStatus.value = { status: 'failed', error: e.message }
  } finally {
    running.value = false
  }
}

async function doInjectPaper() {
  if (!injectDoi.value.trim() || !simulationId.value) return
  try {
    await injectPaper(simulationId.value, injectDoi.value.trim())
    injectDoi.value = ''
  } catch (e) {
    console.warn('Failed to inject paper:', e)
  }
}

async function generateEvolutionReport() {
  if (!simulationId.value) return
  generatingReport.value = true
  reportTask.value = null
  report.value = null

  try {
    const res = await generateReport(simulationId.value, { type: 'evolution' })
    const taskId = res.data?.task_id

    await pollReport(simulationId.value, taskId, (task) => {
      reportTask.value = task
    })

    const reportId = reportTask.value?.result?.report_id
    if (reportId) {
      const rptRes = await getReport(reportId)
      report.value = rptRes.data?.data || rptRes.data
    }
  } catch (e) {
    console.error('Report generation failed:', e)
    reportTask.value = { message: `Error: ${e.message}`, progress: 0 }
  } finally {
    generatingReport.value = false
  }
}

function toggleExportMenu() {
  exportMenuOpen.value = !exportMenuOpen.value
}

async function downloadReport(format) {
  const reportId = report.value?.report_id || reportTask.value?.result?.report_id
  if (!reportId) return

  exportMenuOpen.value = false
  exportLoading.value = true

  try {
    const res = await exportReport(reportId, format)

    if (format === 'json') {
      const jsonStr = JSON.stringify(res.data?.data || res.data, null, 2)
      downloadFile(jsonStr, `${reportId}.json`, 'application/json')
    } else if (format === 'markdown') {
      downloadFile(res.data, `${reportId}.md`, 'text/markdown')
    } else {
      const ext = format === 'pptx' ? 'pptx' : 'mp3'
      downloadFile(res.data, `${reportId}.${ext}`)
    }
  } catch (e) {
    console.error(`Export ${format} failed:`, e)
    alert(`Export failed: ${e.message || 'Unknown error'}`)
  } finally {
    exportLoading.value = false
  }
}

function renderContent(text) {
  if (!text) return ''
  // Escape HTML
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // Render code blocks
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code class="lang-$1">$2</code></pre>')

  // Render inline code
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')

  // Render LaTeX (basic)
  html = html.replace(/\$\$(.+?)\$\$/g, '<div class="math-block">$1</div>')
  html = html.replace(/\$(.+?)\$/g, '<span class="math-inline">$1</span>')

  // Render bold/italic
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')

  html = html.replace(/\n/g, '<br>')
  return html
}

function renderMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/\n/g, '<br>')
}

// Watchers
watch(() => props.topicIds, () => {
  fetchAgents()
  // Auto-fill topic field with selected topic names
  if (props.topicNames.length > 0 && !simulationId.value) {
    setupForm.value.topic = props.topicNames.join(' + ')
  }
}, { deep: true })

// Close skill dropdown on outside click
function handleGlobalClick(e) {
  if (!e.target.closest('.skills-picker')) {
    activeSkillPicker.value = null
  }
}

// Init
onMounted(async () => {
  document.addEventListener('click', handleGlobalClick)
  await Promise.all([fetchFormats(), fetchAgents(), fetchProviders(), fetchSkills()])
})
</script>

<style scoped>
.agent-debate-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-secondary);
  background: var(--bg-secondary);
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.3px;
}

.header-tools {
  display: flex;
  gap: 8px;
  align-items: center;
}

.status-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  text-transform: uppercase;
}

.status-badge.created { background: var(--bg-tertiary); color: var(--text-secondary); }
.status-badge.running { background: var(--os-brand); color: var(--text-on-brand); }
.status-badge.completed { background: var(--success); color: #FFF; }
.status-badge.failed { background: var(--error); color: #FFF; }

.round-badge {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-tertiary);
}

/* Setup panel */
.setup-panel {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.setup-section {
  margin-bottom: 14px;
}

.form-label {
  display: block;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-tertiary);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.form-select, .form-input {
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

.form-select:focus, .form-input:focus {
  outline: none;
  border-color: var(--os-brand);
  box-shadow: 0 0 0 3px rgba(var(--os-brand-rgb), 0.12);
}

.form-input.small {
  width: 80px;
}

.format-desc {
  margin: 4px 0 0;
  font-size: 10px;
  color: var(--text-tertiary);
}

/* Agent picker */
.agent-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 180px;
  overflow-y: auto;
  padding: 4px 0;
}

.agent-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-pill);
  cursor: pointer;
  font-size: 11px;
  color: var(--text-primary);
  background: var(--bg-primary);
  transition: all var(--transition-fast);
}

.agent-chip:hover {
  border-color: var(--os-brand);
}

.agent-chip.selected {
  background: var(--os-brand);
  color: var(--text-on-brand);
  border-color: var(--os-brand);
}

.agent-role-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.agent-chip.selected .agent-role-dot {
  border: 1px solid rgba(255,255,255,0.6);
}

.agent-chip-name {
  font-weight: 600;
}

.agent-chip-role {
  font-size: 9px;
  color: var(--text-tertiary);
}

.agent-chip.selected .agent-chip-role {
  color: rgba(255,255,255,0.7);
}

.agent-model-tag {
  font-size: 8px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 3px;
  background: rgba(255,255,255,0.25);
  text-transform: uppercase;
}

.super-tag {
  font-size: 8px;
  font-weight: 900;
  width: 14px;
  height: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--warning);
  color: #000;
}

.empty-agents {
  font-size: 11px;
  color: var(--text-tertiary);
  padding: 8px 0;
}

/* Advanced Settings Toggle */
.advanced-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
  margin-bottom: 8px;
  cursor: pointer;
  user-select: none;
}

.toggle-arrow {
  font-size: 10px;
  color: var(--text-tertiary);
  transition: transform 0.2s;
}

.toggle-arrow.open {
  transform: rotate(90deg);
}

.toggle-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.toggle-hint {
  font-size: 10px;
  color: var(--text-tertiary);
  margin-left: 4px;
}

/* Advanced Panel */
.advanced-panel {
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  padding: 10px;
  margin-bottom: 14px;
  background: var(--bg-secondary);
  max-height: 420px;
  overflow-y: auto;
}

.advanced-empty {
  font-size: 11px;
  color: var(--text-tertiary);
  padding: 8px 0;
  text-align: center;
}

.agent-config-card {
  padding: 10px;
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  margin-bottom: 8px;
  background: var(--bg-primary);
}

.config-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.config-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.config-name {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.config-role {
  font-size: 10px;
  color: var(--text-tertiary);
}

.config-row {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
}

.config-field {
  flex: 1;
}

.config-field.full {
  flex: 1 1 100%;
}

.config-label {
  display: block;
  font-size: 9px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  margin-bottom: 2px;
}

.config-select {
  width: 100%;
  padding: 4px 6px;
  font-size: 11px;
  font-family: var(--font-sans);
  border: 1px solid var(--border-primary);
  border-radius: 4px;
  background: var(--bg-primary);
  color: var(--text-primary);
  box-sizing: border-box;
}

.config-select:focus {
  outline: none;
  border-color: var(--os-brand);
}

/* Skills picker */
.skills-picker {
  position: relative;
}

.skills-search {
  width: 100%;
  padding: 4px 6px;
  font-size: 11px;
  font-family: var(--font-sans);
  border: 1px solid var(--border-primary);
  border-radius: 4px;
  background: var(--bg-primary);
  color: var(--text-primary);
  box-sizing: border-box;
}

.skills-search:focus {
  outline: none;
  border-color: var(--os-brand);
}

.skill-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: 4px;
}

.skill-tag {
  font-size: 9px;
  padding: 1px 6px;
  background: var(--os-brand-light);
  color: var(--os-brand);
  border-radius: 3px;
  cursor: pointer;
  font-weight: 500;
}

.skill-tag:hover {
  background: var(--error);
  color: #FFF;
}

.skills-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  max-height: 160px;
  overflow-y: auto;
  background: var(--bg-elevated);
  border: 1px solid var(--border-primary);
  border-radius: 4px;
  box-shadow: var(--shadow-lg);
  z-index: 20;
  margin-top: 2px;
}

.skill-option {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 11px;
  color: var(--text-primary);
}

.skill-option:hover {
  background: var(--bg-hover);
}

.skill-cat {
  font-size: 8px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 2px;
  text-transform: uppercase;
  flex-shrink: 0;
}

.skill-cat.database { background: #E3F2FD; color: #1565C0; }
.skill-cat.package { background: #E8F5E9; color: #2E7D32; }
.skill-cat.analysis { background: #FFF3E0; color: #E65100; }
.skill-cat.integration { background: #F3E5F5; color: #7B1FA2; }

[data-theme="dark"] .skill-cat.database { background: #0D47A120; color: #64B5F6; }
[data-theme="dark"] .skill-cat.package { background: #1B5E2020; color: #81C784; }
[data-theme="dark"] .skill-cat.analysis { background: #BF36000A; color: #FFB74D; }
[data-theme="dark"] .skill-cat.integration { background: #4A148C20; color: #CE93D8; }

.skill-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Super agent toggle */
.super-agent-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 11px;
}

.super-agent-toggle input {
  accent-color: var(--os-brand);
}

.super-label {
  font-weight: 600;
  color: var(--text-primary);
}

.super-desc {
  font-size: 9px;
  color: var(--text-tertiary);
}

/* Presets */
.presets-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-secondary);
}

.presets-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-tertiary);
}

.preset-btn {
  padding: 3px 8px;
  font-size: 10px;
  font-weight: 500;
  font-family: var(--font-sans);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-primary);
  border-radius: 3px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.preset-btn:hover {
  border-color: var(--os-brand);
  color: var(--os-brand);
}

/* Primary button */
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

.btn-primary:hover { background: var(--os-brand-hover); }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-primary.btn-visual { background: #6366f1; }
.btn-primary.btn-visual:hover { background: #4f46e5; }

/* Mode selector */
.mode-selector {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.mode-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 8px;
  border: 2px solid var(--border-secondary);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  cursor: pointer;
  transition: all var(--transition-fast);
  font-family: var(--font-sans);
}

.mode-btn:hover {
  border-color: var(--text-tertiary);
}

.mode-btn.active {
  border-color: var(--os-brand);
  background: color-mix(in srgb, var(--os-brand) 8%, var(--bg-primary));
}

.mode-icon {
  color: var(--text-secondary);
}

.mode-btn.active .mode-icon {
  color: var(--os-brand);
}

.mode-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.mode-desc {
  font-size: 10px;
  color: var(--text-tertiary);
}

/* Transcript toolbar */
.transcript-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-secondary);
  background: var(--bg-secondary);
  flex-shrink: 0;
}

.btn-back {
  padding: 4px 12px;
  font-size: 11px;
  font-weight: 600;
  font-family: var(--font-sans);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.btn-back:hover {
  background: var(--bg-hover);
  border-color: var(--os-brand);
  color: var(--os-brand);
}

.btn-back:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.toolbar-status {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
}

/* Transcript panel */
.transcript-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.round-nav {
  display: flex;
  gap: 4px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-secondary);
  overflow-x: auto;
  flex-shrink: 0;
}

.round-btn {
  padding: 3px 10px;
  font-size: 10px;
  font-weight: 600;
  font-family: var(--font-sans);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-secondary);
  white-space: nowrap;
  transition: all var(--transition-fast);
}

.round-btn.active {
  background: var(--os-brand);
  color: var(--text-on-brand);
  border-color: var(--os-brand);
}

/* Turns list */
.turns-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.turn-card {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  background: var(--bg-primary);
  transition: all var(--transition-fast);
}

.turn-card.highlight {
  background: var(--os-brand-light);
  border-color: var(--os-brand-subtle);
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
}

.turn-agent-name {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.turn-role {
  font-size: 10px;
  color: var(--text-tertiary);
}

.turn-model-badge {
  font-size: 8px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--bg-tertiary);
  color: var(--os-brand);
  border: 1px solid var(--border-primary);
}

.turn-type-badge {
  margin-left: auto;
  font-size: 9px;
  font-weight: 600;
  padding: 1px 6px;
  background: var(--bg-tertiary);
  border-radius: 3px;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.turn-round {
  font-size: 9px;
  font-weight: 600;
  color: var(--text-tertiary);
}

.turn-content {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.turn-content :deep(pre.code-block) {
  margin: 8px 0;
  padding: 10px 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-primary);
}

.turn-content :deep(code.inline-code) {
  padding: 1px 4px;
  background: var(--bg-tertiary);
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: 11px;
}

.turn-content :deep(.math-block) {
  margin: 8px 0;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-left: 3px solid var(--os-brand);
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-primary);
}

.turn-content :deep(.math-inline) {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--os-brand);
}

.turn-citations {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.citation-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-tertiary);
}

.citation-doi {
  font-size: 9px;
  font-family: var(--font-mono);
  padding: 1px 6px;
  background: var(--bg-tertiary);
  border-radius: 3px;
  color: var(--text-secondary);
}

.empty-transcript {
  text-align: center;
  padding: 40px 0;
  color: var(--text-tertiary);
  font-size: 12px;
}

/* Inject bar */
.inject-bar {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid var(--border-secondary);
  flex-shrink: 0;
}

.inject-bar .form-input {
  flex: 1;
}

.btn-inject {
  padding: 6px 14px;
  font-size: 11px;
  font-weight: 600;
  font-family: var(--font-sans);
  background: var(--os-brand);
  color: var(--text-on-brand);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-inject:hover { background: var(--os-brand-hover); }
.btn-inject:disabled { opacity: 0.4; cursor: not-allowed; }

/* Report section */
.report-section {
  border-top: 1px solid var(--border-secondary);
  flex-shrink: 0;
}

.report-generate {
  padding: 12px;
}

.report-progress {
  margin-top: 8px;
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

.report-display {
  max-height: 400px;
  overflow-y: auto;
  padding: 12px;
}

.report-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.report-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.btn-sm {
  padding: 3px 10px;
  font-size: 10px;
  font-weight: 600;
  font-family: var(--font-sans);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.btn-sm:hover {
  background: var(--bg-hover);
  border-color: var(--os-brand);
  color: var(--os-brand);
}

.report-summary {
  font-size: 12px;
  color: var(--text-tertiary);
  font-style: italic;
  margin: 0 0 12px;
}

.report-sec {
  margin-bottom: 16px;
}

.report-sec-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--border-secondary);
}

.report-sec-content {
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.report-sec-content blockquote {
  margin: 8px 0;
  padding: 6px 12px;
  border-left: 3px solid var(--os-brand-subtle);
  color: var(--text-secondary);
  font-style: italic;
}

.report-sec-content li {
  margin-left: 16px;
  list-style: disc;
}

.report-sec-content strong {
  font-weight: 700;
  color: var(--text-primary);
}

.report-header-actions {
  display: flex;
  gap: 6px;
  align-items: center;
  position: relative;
}

.export-dropdown {
  position: relative;
}

.export-menu {
  position: absolute;
  top: 100%;
  right: 0;
  background: var(--bg-secondary, #fff);
  border: 1px solid var(--border-primary, #ddd);
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 100;
  min-width: 140px;
  margin-top: 4px;
}

.export-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 12px;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-primary, #333);
  font-size: 11px;
  font-family: var(--font-sans, inherit);
  transition: background 0.15s;
}

.export-item:hover {
  background: var(--bg-hover, #f0f0f0);
  color: var(--os-brand, #4f8ef7);
}

.export-item:first-child {
  border-radius: 6px 6px 0 0;
}

.export-item:last-child {
  border-radius: 0 0 6px 6px;
}

/* Clickable agent name in transcript */
.turn-agent-name.clickable {
  cursor: pointer;
  transition: color var(--transition-fast);
}

.turn-agent-name.clickable:hover {
  color: var(--os-brand);
  text-decoration: underline;
}

/* Toolbar right group */
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* What If? button */
.btn-whatif {
  padding: 4px 12px;
  font-size: 11px;
  font-weight: 600;
  font-family: var(--font-sans);
  background: var(--bg-tertiary);
  border: 1px solid var(--os-brand);
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--os-brand);
  transition: all var(--transition-fast);
}

.btn-whatif:hover {
  background: var(--os-brand);
  color: var(--text-on-brand);
}

/* Fork Panel */
.fork-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  padding: 16px;
  margin: 12px;
  flex-shrink: 0;
}

.fork-header {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.fork-group {
  margin-bottom: 12px;
}

.fork-group label {
  display: block;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  margin-bottom: 4px;
}

.fork-slider {
  width: 100%;
  accent-color: var(--os-brand);
}

.fork-round-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
  margin-top: 2px;
}

.fork-select {
  width: 100%;
  padding: 6px 8px;
  font-size: 12px;
  font-family: var(--font-sans);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  color: var(--text-primary);
  box-sizing: border-box;
}

.fork-select:focus {
  outline: none;
  border-color: var(--os-brand);
}

.fork-input {
  width: 100%;
  padding: 6px 8px;
  font-size: 12px;
  font-family: var(--font-sans);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  color: var(--text-primary);
  box-sizing: border-box;
}

.fork-input:focus {
  outline: none;
  border-color: var(--os-brand);
}

.btn-fork {
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

.btn-fork:hover {
  background: var(--os-brand-hover);
}

.btn-fork:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Chat Panel */
.chat-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: 350px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  border-left: 1px solid var(--border-secondary);
  box-shadow: var(--shadow-lg);
  z-index: 30;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  border-bottom: 1px solid var(--border-secondary);
  background: var(--bg-secondary);
  flex-shrink: 0;
}

.chat-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.chat-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: var(--text-tertiary);
  line-height: 1;
  padding: 0 4px;
  transition: color var(--transition-fast);
}

.chat-close:hover {
  color: var(--text-primary);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chat-msg {
  display: flex;
  flex-direction: column;
  max-width: 80%;
}

.chat-msg.user {
  align-self: flex-end;
}

.chat-msg.agent {
  align-self: flex-start;
}

.chat-msg-bubble {
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 12px;
  line-height: 1.5;
  word-wrap: break-word;
}

.chat-msg.user .chat-msg-bubble {
  background: var(--os-brand);
  color: var(--text-on-brand);
  border-bottom-right-radius: 4px;
}

.chat-msg.agent .chat-msg-bubble {
  background: var(--bg-tertiary);
  color: var(--text-primary);
  border: 1px solid var(--border-secondary);
  border-bottom-left-radius: 4px;
}

.chat-input-bar {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid var(--border-secondary);
  flex-shrink: 0;
}

.chat-input {
  flex: 1;
  padding: 8px;
  font-size: 12px;
  font-family: var(--font-sans);
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  background: var(--bg-primary);
  color: var(--text-primary);
  box-sizing: border-box;
}

.chat-input:focus {
  outline: none;
  border-color: var(--os-brand);
  box-shadow: 0 0 0 3px rgba(var(--os-brand-rgb), 0.12);
}

.chat-input:disabled {
  opacity: 0.5;
}

.chat-send {
  padding: 8px 16px;
  font-size: 12px;
  font-weight: 600;
  font-family: var(--font-sans);
  background: var(--os-brand);
  color: var(--text-on-brand);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.chat-send:hover {
  background: var(--os-brand-hover);
}

.chat-send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.chat-loading {
  opacity: 0.6;
  padding: 8px;
  font-size: 12px;
  font-style: italic;
  color: var(--text-tertiary);
}
</style>

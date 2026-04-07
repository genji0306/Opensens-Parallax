<script setup lang="ts">
import { ref, computed, onBeforeUnmount, watch, nextTick } from 'vue'
import type {
  FigureAnalysis, TableAnalysis, DiagramResult,
  DeepAnalysisResult, DiagramType, VisualizationCache,
  RenderedFigure, FigureAuditResult,
} from '@/api/paperLab'
import {
  analyzeFigures, analyzeTables, generateDiagram,
  runDeepAnalysis, getVisualizations,
  renderFigures, auditFigures,
} from '@/api/paperLab'
import CodeBlock from './CodeBlock.vue'
import StatementDiff from './StatementDiff.vue'
import ScientificFigureRenderer from './ScientificFigureRenderer.vue'
import FigureQualityAudit from './FigureQualityAudit.vue'
import PaperBananaPanel from './PaperBananaPanel.vue'

const props = defineProps<{ uploadId: string }>()

// ── Active tab ────────────────────────────────────────────────────────────
type Tab = 'figures' | 'tables' | 'diagram' | 'paperbanana' | 'deep' | 'render'
const activeTab = ref<Tab>('figures')

// ── Panel state ───────────────────────────────────────────────────────────
type PanelStatus = 'idle' | 'running' | 'done' | 'error'

const figuresStatus = ref<PanelStatus>('idle')
const figuresData = ref<FigureAnalysis | null>(null)
const expandedFigure = ref<number | null>(null)

const tablesStatus = ref<PanelStatus>('idle')
const tablesData = ref<TableAnalysis | null>(null)
const showCorrected = ref<Record<number, boolean>>({})
const expandedTable = ref<number | null>(null)

const diagramStatus = ref<PanelStatus>('idle')
const diagramData = ref<DiagramResult | null>(null)
const selectedDiagramType = ref<DiagramType>('flowchart')
const diagramContainer = ref<HTMLElement | null>(null)

const deepStatus = ref<PanelStatus>('idle')
const deepData = ref<DeepAnalysisResult | null>(null)

const renderStatus = ref<PanelStatus>('idle')
const renderedFigures = ref<RenderedFigure[]>([])
const auditStatus = ref<PanelStatus>('idle')
const auditData = ref<FigureAuditResult | null>(null)

let pollTimer: ReturnType<typeof setTimeout> | null = null

// ── Severity colour helpers ───────────────────────────────────────────────
function severityColor(sev: string) {
  if (sev === 'critical') return 'var(--error)'
  if (sev === 'major') return 'var(--warning)'
  return 'var(--text-tertiary)'
}
function severityBg(sev: string) {
  if (sev === 'critical') return 'rgba(239,68,68,0.12)'
  if (sev === 'major') return 'rgba(234,179,8,0.12)'
  return 'rgba(128,128,128,0.10)'
}

// ── Poll helper ───────────────────────────────────────────────────────────
async function pollForResults(attempts = 0) {
  if (attempts > 40) return // ~2.7 min max
  const needsPolling =
    figuresStatus.value === 'running' ||
    tablesStatus.value === 'running' ||
    deepStatus.value === 'running'
  if (!needsPolling) return

  try {
    const res = await getVisualizations(props.uploadId)
    const cache: VisualizationCache = res.data?.data ?? {}

    if (figuresStatus.value === 'running' && cache.figures) {
      figuresData.value = cache.figures
      figuresStatus.value = 'done'
    }
    if (tablesStatus.value === 'running' && cache.tables) {
      tablesData.value = cache.tables
      tablesStatus.value = 'done'
    }
    if (deepStatus.value === 'running' && cache.deep_analysis) {
      deepData.value = cache.deep_analysis
      deepStatus.value = 'done'
    }
  } catch { /* still running */ }

  // Continue polling if any still running
  const stillRunning =
    figuresStatus.value === 'running' ||
    tablesStatus.value === 'running' ||
    deepStatus.value === 'running'
  if (stillRunning) {
    pollTimer = setTimeout(() => pollForResults(attempts + 1), 4000)
  }
}

function startPoll() {
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = setTimeout(() => pollForResults(), 2000)
}

onBeforeUnmount(() => { if (pollTimer) clearTimeout(pollTimer) })

// ── Actions ───────────────────────────────────────────────────────────────
async function triggerFigures() {
  figuresStatus.value = 'running'
  figuresData.value = null
  try {
    await analyzeFigures(props.uploadId)
    startPoll()
  } catch { figuresStatus.value = 'error' }
}

async function triggerTables() {
  tablesStatus.value = 'running'
  tablesData.value = null
  try {
    await analyzeTables(props.uploadId)
    startPoll()
  } catch { tablesStatus.value = 'error' }
}

async function triggerDiagram() {
  diagramStatus.value = 'running'
  diagramData.value = null
  try {
    const res = await generateDiagram(props.uploadId, selectedDiagramType.value)
    diagramData.value = res.data?.data ?? null
    diagramStatus.value = diagramData.value?.mermaid_code ? 'done' : 'error'
    if (diagramStatus.value === 'done') {
      await nextTick()
      renderMermaid()
    }
  } catch { diagramStatus.value = 'error' }
}

async function triggerDeep() {
  deepStatus.value = 'running'
  deepData.value = null
  try {
    await runDeepAnalysis(props.uploadId)
    startPoll()
  } catch { deepStatus.value = 'error' }
}

async function triggerRender() {
  if (figuresStatus.value !== 'done') return
  renderStatus.value = 'running'
  try {
    const res = await renderFigures(props.uploadId)
    renderedFigures.value = res.data?.data?.figures ?? []
    renderStatus.value = 'done'
  } catch { renderStatus.value = 'error' }
}

async function triggerAudit() {
  if (figuresStatus.value !== 'done') return
  auditStatus.value = 'running'
  try {
    const res = await auditFigures(props.uploadId)
    auditData.value = res.data?.data ?? null
    auditStatus.value = 'done'
  } catch { auditStatus.value = 'error' }
}

// ── Mermaid rendering ─────────────────────────────────────────────────────
async function renderMermaid() {
  if (!diagramData.value?.mermaid_code || !diagramContainer.value) return
  try {
    const mermaid = (await import('mermaid')).default
    mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      themeVariables: {
        background: 'transparent',
        primaryColor: 'rgba(255, 255, 255, 0.03)',
        primaryTextColor: '#f8fafc',
        primaryBorderColor: 'rgba(204, 255, 0, 0.3)',
        lineColor: '#ccff00',
        secondaryColor: 'rgba(204, 255, 0, 0.05)',
        tertiaryColor: '#111827',
        fontSize: '13px',
      },
    })
    const id = `mermaid-${Date.now()}`
    const { svg } = await mermaid.render(id, diagramData.value.mermaid_code)
    if (diagramContainer.value) {
      diagramContainer.value.innerHTML = svg
    }
  } catch (e) {
    console.warn('Mermaid render error:', e)
    if (diagramContainer.value) {
      diagramContainer.value.innerHTML = `<pre class="mermaid-fallback">${diagramData.value?.mermaid_code ?? ''}</pre>`
    }
  }
}

watch(() => activeTab.value, async (tab) => {
  if (tab === 'diagram' && diagramStatus.value === 'done') {
    await nextTick()
    renderMermaid()
  }
})

function downloadSvg() {
  const svg = diagramContainer.value?.querySelector('svg')
  if (!svg) return
  const blob = new Blob([svg.outerHTML], { type: 'image/svg+xml' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `diagram_${selectedDiagramType.value}.svg`
  a.click()
  URL.revokeObjectURL(url)
}

function downloadMermaid() {
  if (!diagramData.value?.mermaid_code) return
  const blob = new Blob([diagramData.value.mermaid_code], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `diagram_${selectedDiagramType.value}.mmd`
  a.click()
  URL.revokeObjectURL(url)
}

const diagramTypes: { value: DiagramType; label: string; icon: string }[] = [
  { value: 'flowchart', label: 'Workflow', icon: 'account_tree' },
  { value: 'mindmap', label: 'Mind Map', icon: 'hub' },
  { value: 'sequence', label: 'Sequence', icon: 'low_priority' },
  { value: 'timeline', label: 'Timeline', icon: 'schedule' },
  { value: 'quadrant', label: 'Quadrant', icon: 'grid_4x4' },
  { value: 'infographic', label: 'Infographic', icon: 'view_quilt' },
]

// ── Deep analysis helpers ─────────────────────────────────────────────────
const geminiRequired = computed(() =>
  (deepData.value as DeepAnalysisResult & { gemini_required?: boolean } | null)?.gemini_required ||
  (diagramData.value as DiagramResult & { gemini_required?: boolean } | null)?.gemini_required
)
</script>

<template>
  <div class="viz-panel">
    <!-- ── Tab bar ── -->
    <div class="viz-tabs" role="tablist">
      <button
        v-for="tab in [
          { key: 'figures', icon: 'bar_chart', label: 'Figures' },
          { key: 'render', icon: 'insert_chart', label: 'Render' },
          { key: 'tables', icon: 'table_chart', label: 'Tables' },
          { key: 'diagram', icon: 'hub', label: 'Auto Diagram' },
          { key: 'paperbanana', icon: 'palette', label: 'Agentic Illustration' },
          { key: 'deep', icon: 'psychology', label: 'Deep Analysis' },
        ]"
        :key="tab.key"
        class="viz-tab"
        :class="{ 'viz-tab--active': activeTab === tab.key }"
        role="tab"
        @click="activeTab = tab.key as Tab"
      >
        <span class="material-symbols-outlined" style="font-size: 16px">{{ tab.icon }}</span>
        {{ tab.label }}
      </button>
    </div>

    <!-- ── Gemini key warning ── -->
    <div v-if="geminiRequired" class="gemini-warn">
      <span class="material-symbols-outlined" style="font-size: 16px">key</span>
      Add <code>GEMINI_API_KEY</code> to <code>backend/.env</code> to enable Gemini-powered features.
    </div>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- Tab: FIGURES                                                          -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'figures'" class="viz-body">
      <div class="viz-body__header">
        <div>
          <p class="viz-body__desc">
            Detects every figure reference in the manuscript and generates step-by-step
            Python reconstruction code with data requirement flags.
          </p>
        </div>
        <button
          class="viz-action-btn"
          :disabled="figuresStatus === 'running'"
          @click="triggerFigures"
        >
          <span v-if="figuresStatus === 'running'" class="material-symbols-outlined spin" style="font-size: 15px">progress_activity</span>
          <span v-else class="material-symbols-outlined" style="font-size: 15px">search</span>
          {{ figuresStatus === 'running' ? 'Analysing...' : figuresStatus === 'done' ? 'Re-analyse' : 'Analyse Figures' }}
        </button>
      </div>

      <!-- Running -->
      <div v-if="figuresStatus === 'running'" class="viz-loading">
        <span class="material-symbols-outlined spin">progress_activity</span>
        <span>Identifying figures and generating reconstruction code...</span>
      </div>

      <!-- Results -->
      <div v-else-if="figuresStatus === 'done' && figuresData" class="figures-results">
        <div class="viz-summary">
          <span class="viz-count">{{ figuresData.figure_count }} figure{{ figuresData.figure_count !== 1 ? 's' : '' }} detected</span>
          <span class="viz-note">{{ figuresData.overall_notes }}</span>
        </div>

        <div
          v-for="(fig, i) in figuresData.figures"
          :key="fig.ref"
          class="figure-card"
        >
          <!-- Header row -->
          <button class="figure-card__trigger" @click="expandedFigure = expandedFigure === i ? null : i">
            <span class="figure-ref font-mono">{{ fig.ref }}</span>
            <span class="figure-type-badge">{{ fig.inferred_type }}</span>
            <div class="figure-counts">
              <span v-if="fig.issues.length" class="figure-issue-count">{{ fig.issues.length }} issue{{ fig.issues.length !== 1 ? 's' : '' }}</span>
              <span v-if="fig.data_requirements.length" class="figure-req-count">{{ fig.data_requirements.length }} data req</span>
            </div>
            <span class="material-symbols-outlined" style="font-size: 16px; color: var(--text-tertiary); margin-left: auto">
              {{ expandedFigure === i ? 'expand_less' : 'expand_more' }}
            </span>
          </button>

          <Transition name="expand">
          <div v-if="expandedFigure === i" class="figure-card__body">
            <!-- Caption excerpt -->
            <p v-if="fig.caption_excerpt" class="figure-caption">"{{ fig.caption_excerpt }}"</p>

            <!-- Issues -->
            <div v-if="fig.issues.length" class="figure-issues">
              <div v-for="(issue, ii) in fig.issues" :key="ii" class="figure-issue">
                <span class="material-symbols-outlined" style="font-size: 13px; color: var(--warning)">warning</span>
                {{ issue }}
              </div>
            </div>

            <!-- Data requirements -->
            <div v-if="fig.data_requirements.length" class="figure-reqs">
              <p class="figure-reqs__title">Data Requirements</p>
              <ul>
                <li v-for="(req, ri) in fig.data_requirements" :key="ri">{{ req }}</li>
              </ul>
            </div>

            <!-- Reconstruction code -->
            <div class="figure-code-section">
              <p class="figure-reqs__title">Python Reconstruction</p>
              <CodeBlock :code="fig.reconstruction_code" language="python" :filename="`reconstruct_${fig.ref.replace(/\s+/g, '_').toLowerCase()}.py`" />
            </div>
          </div>
          </Transition>
        </div>
      </div>

      <!-- Empty -->
      <div v-else-if="figuresStatus === 'idle'" class="viz-idle">
        <span class="material-symbols-outlined" style="font-size: 32px; opacity: 0.4">bar_chart</span>
        <p>Click "Analyse Figures" to detect and reconstruct all figures in the manuscript.</p>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- Tab: RENDER (Scientific Figure Renderer + Quality Audit)              -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'render'" class="viz-body">
      <div class="viz-body__header">
        <div>
          <p class="viz-body__desc">
            Interactive Vega-Lite rendering of detected figures with quality audit
            based on Rougier's <em>Ten Simple Rules for Better Figures</em>.
          </p>
        </div>
        <div style="display: flex; gap: 8px;">
          <button
            class="viz-action-btn"
            :disabled="figuresStatus !== 'done' || renderStatus === 'running'"
            @click="triggerRender"
          >
            <span class="material-symbols-outlined" style="font-size: 16px">insert_chart</span>
            {{ renderStatus === 'running' ? 'Rendering...' : 'Render Figures' }}
          </button>
          <button
            class="viz-action-btn"
            :disabled="figuresStatus !== 'done' || auditStatus === 'running'"
            @click="triggerAudit"
          >
            <span class="material-symbols-outlined" style="font-size: 16px">fact_check</span>
            {{ auditStatus === 'running' ? 'Auditing...' : 'Audit Quality' }}
          </button>
        </div>
      </div>

      <div v-if="figuresStatus !== 'done'" class="viz-placeholder">
        <span class="material-symbols-outlined" style="font-size: 28px; opacity: 0.3">bar_chart</span>
        <p>Run <strong>Figure Analysis</strong> first (Figures tab), then return here to render and audit.</p>
      </div>

      <div v-else>
        <!-- Rendered figures -->
        <div v-if="renderStatus === 'done' && renderedFigures.length" style="margin-bottom: 16px;">
          <ScientificFigureRenderer :figures="renderedFigures" @audit-request="triggerAudit" />
        </div>

        <!-- Quality audit -->
        <div v-if="auditStatus === 'done' && auditData">
          <FigureQualityAudit :audit="auditData" />
        </div>

        <div v-if="renderStatus === 'idle' && auditStatus === 'idle'" class="viz-placeholder">
          <p>Figure analysis complete. Click <strong>Render Figures</strong> to generate interactive charts, or <strong>Audit Quality</strong> to check against best practices.</p>
        </div>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- Tab: TABLES                                                           -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'tables'" class="viz-body">
      <div class="viz-body__header">
        <p class="viz-body__desc">
          Extracts all tables, audits for statistical errors (missing N, uncorrected p-values,
          unit inconsistencies), and proposes corrected data.
        </p>
        <button
          class="viz-action-btn"
          :disabled="tablesStatus === 'running'"
          @click="triggerTables"
        >
          <span v-if="tablesStatus === 'running'" class="material-symbols-outlined spin" style="font-size: 15px">progress_activity</span>
          <span v-else class="material-symbols-outlined" style="font-size: 15px">search</span>
          {{ tablesStatus === 'running' ? 'Analysing...' : tablesStatus === 'done' ? 'Re-analyse' : 'Analyse Tables' }}
        </button>
      </div>

      <div v-if="tablesStatus === 'running'" class="viz-loading">
        <span class="material-symbols-outlined spin">progress_activity</span>
        <span>Extracting and auditing tables...</span>
      </div>

      <div v-else-if="tablesStatus === 'done' && tablesData" class="tables-results">
        <div class="viz-summary">
          <span class="viz-count">{{ tablesData.table_count }} table{{ tablesData.table_count !== 1 ? 's' : '' }} found</span>
          <span class="viz-note">{{ tablesData.summary }}</span>
        </div>

        <div v-for="(tbl, ti) in tablesData.tables" :key="tbl.ref" class="table-card">
          <button class="table-card__trigger" @click="expandedTable = expandedTable === ti ? null : ti">
            <span class="font-mono" style="font-size: 12px; font-weight: 600; color: var(--text-primary)">{{ tbl.ref }}</span>
            <span style="font-size: 12px; color: var(--text-tertiary); flex: 1; text-align: left; margin-left: 8px">{{ tbl.title }}</span>
            <span v-if="tbl.issues.length" class="table-issue-count">{{ tbl.issues.filter(i => i.severity === 'critical').length }} critical</span>
            <span class="material-symbols-outlined" style="font-size: 16px; color: var(--text-tertiary)">
              {{ expandedTable === ti ? 'expand_less' : 'expand_more' }}
            </span>
          </button>

          <Transition name="expand">
          <div v-if="expandedTable === ti" class="table-card__body">
            <!-- Raw/Corrected toggle -->
            <div class="table-view-toggle">
              <button :class="{ active: !showCorrected[ti] }" @click="showCorrected[ti] = false">Raw</button>
              <button :class="{ active: showCorrected[ti] }" @click="showCorrected[ti] = true">Corrected</button>
            </div>

            <!-- Data table -->
            <div class="table-scroll">
              <table class="data-table">
                <thead>
                  <tr>
                    <th v-for="h in (showCorrected[ti] ? tbl.corrected_data?.headers : tbl.raw_data?.headers) ?? []" :key="h">{{ h }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, ri) in (showCorrected[ti] ? tbl.corrected_data?.rows : tbl.raw_data?.rows) ?? []" :key="ri">
                    <td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Issues -->
            <div v-if="tbl.issues.length" class="table-issues">
              <p class="figure-reqs__title">Issues Found</p>
              <div v-for="(iss, ii) in tbl.issues" :key="ii" class="table-issue">
                <span
                  class="issue-sev"
                  :style="{ color: severityColor(iss.severity), background: severityBg(iss.severity) }"
                >{{ iss.severity }}</span>
                <span class="font-mono" style="font-size: 10px; color: var(--text-tertiary)">{{ iss.cell }}</span>
                <span style="font-size: 12px; color: var(--text-secondary)">{{ iss.description }}</span>
                <span v-if="iss.corrected_value" style="font-size: 11px; color: var(--success)">→ {{ iss.corrected_value }}</span>
              </div>
            </div>

            <!-- Analysis note -->
            <div v-if="tbl.analysis_note" class="table-analysis-note">
              <span class="material-symbols-outlined" style="font-size: 14px; color: var(--os-brand)">insights</span>
              {{ tbl.analysis_note }}
            </div>
            </div>
          </Transition>
        </div>
      </div>

      <div v-else-if="tablesStatus === 'idle'" class="viz-idle">
        <span class="material-symbols-outlined" style="font-size: 32px; opacity: 0.4">table_chart</span>
        <p>Click "Analyse Tables" to extract, audit, and correct all tables in this manuscript.</p>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- Tab: DIAGRAM                                                          -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'diagram'" class="viz-body">
      <div class="viz-body__header">
        <p class="viz-body__desc">
          Generates a Mermaid.js diagram or infographic from the manuscript using Gemini 2.0 Flash.
        </p>
        <div class="diagram-controls">
          <!-- Type selector -->
          <div class="diagram-type-pills">
            <button
              v-for="dt in diagramTypes"
              :key="dt.value"
              class="diagram-type-pill"
              :class="{ 'diagram-type-pill--active': selectedDiagramType === dt.value }"
              @click="selectedDiagramType = dt.value"
            >
              <span class="material-symbols-outlined" style="font-size: 13px">{{ dt.icon }}</span>
              {{ dt.label }}
            </button>
          </div>
          <button
            class="viz-action-btn"
            :disabled="diagramStatus === 'running'"
            @click="triggerDiagram"
          >
            <span v-if="diagramStatus === 'running'" class="material-symbols-outlined spin" style="font-size: 15px">progress_activity</span>
            <span v-else class="material-symbols-outlined" style="font-size: 15px">auto_awesome</span>
            {{ diagramStatus === 'running' ? 'Generating...' : 'Generate' }}
          </button>
        </div>
      </div>

      <div v-if="diagramStatus === 'running'" class="viz-loading">
        <span class="material-symbols-outlined spin">progress_activity</span>
        <span>Gemini 2.0 Flash is composing your diagram...</span>
      </div>

      <div v-else-if="diagramStatus === 'done' && diagramData?.mermaid_code" class="diagram-result">
        <!-- Download bar -->
        <div class="diagram-actions">
          <span class="diagram-engine-badge">✦ gemini-2.0-flash</span>
          <button class="diag-dl-btn" @click="downloadSvg">
            <span class="material-symbols-outlined" style="font-size: 14px">download</span> SVG
          </button>
          <button class="diag-dl-btn" @click="downloadMermaid">
            <span class="material-symbols-outlined" style="font-size: 14px">code</span> .mmd
          </button>
        </div>
        <!-- Rendered diagram -->
        <div ref="diagramContainer" class="mermaid-output" />
      </div>

      <div v-else-if="diagramStatus === 'error'" class="viz-error">
        <span class="material-symbols-outlined" style="font-size: 20px; color: var(--error)">error</span>
        {{ diagramData?.error ?? 'Diagram generation failed.' }}
        <span v-if="diagramData?.gemini_required" style="font-size: 11px; margin-top: 4px">
          Add <code>GEMINI_API_KEY</code> to <code>backend/.env</code> to enable this feature.
        </span>
      </div>

      <div v-else-if="diagramStatus === 'idle'" class="viz-idle">
        <span class="material-symbols-outlined" style="font-size: 32px; opacity: 0.4">hub</span>
        <p>Select a diagram type, then click "Generate" to create an AI-composed Mermaid diagram.</p>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- Tab: DEEP ANALYSIS                                                    -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'deep'" class="viz-body">
      <div class="viz-body__header">
        <p class="viz-body__desc">
          Gemini 2.0 Flash Thinking performs cross-data reasoning to propose simulations,
          cross-dataset strategies, and improved statement rewrites.
        </p>
        <button
          class="viz-action-btn viz-action-btn--thinking"
          :disabled="deepStatus === 'running'"
          @click="triggerDeep"
        >
          <span v-if="deepStatus === 'running'" class="material-symbols-outlined spin" style="font-size: 15px">progress_activity</span>
          <span v-else class="material-symbols-outlined" style="font-size: 15px">psychology</span>
          {{ deepStatus === 'running' ? 'Thinking (30–60s)...' : deepStatus === 'done' ? 'Re-analyse' : 'Run Deep Analysis' }}
        </button>
      </div>

      <div v-if="deepStatus === 'running'" class="viz-loading viz-loading--thinking">
        <span class="material-symbols-outlined spin" style="font-size: 28px">psychology</span>
        <span>Gemini 2.0 Flash Thinking is performing deep cross-data reasoning...</span>
        <span class="thinking-hint">This may take 30–60 seconds for a full paper.</span>
      </div>

      <div v-else-if="deepStatus === 'done' && deepData" class="deep-results">
        <!-- Engine badge -->
        <div style="margin-bottom: 12px">
          <span class="diagram-engine-badge">✦ {{ deepData.engine ?? 'gemini-2.0-flash-thinking' }}</span>
        </div>

        <!-- Overall assessment -->
        <div v-if="deepData.overall_assessment" class="deep-assessment">
          <span class="material-symbols-outlined" style="font-size: 16px; color: var(--os-brand)">analytics</span>
          {{ deepData.overall_assessment }}
        </div>

        <!-- Simulation proposals -->
        <div v-if="deepData.simulation_proposals?.length" class="deep-section">
          <h5 class="deep-section__title">
            <span class="material-symbols-outlined" style="font-size: 16px">science</span>
            Proposed Simulations ({{ deepData.simulation_proposals.length }})
          </h5>
          <div class="sim-list">
            <div v-for="(sim, si) in deepData.simulation_proposals" :key="si" class="sim-card">
              <div class="sim-card__header">
                <span class="sim-card__name">{{ sim.name }}</span>
                <span class="sim-card__method font-mono">{{ sim.method }}</span>
              </div>
              <p class="sim-card__goal">{{ sim.goal }}</p>
              <div v-if="sim.tools?.length" class="sim-card__tools">
                <span v-for="tool in sim.tools" :key="tool" class="tool-tag font-mono">{{ tool }}</span>
              </div>
              <p class="sim-card__outcome">
                <span class="material-symbols-outlined" style="font-size: 12px; vertical-align: middle">trending_up</span>
                {{ sim.expected_outcome }}
              </p>
            </div>
          </div>
        </div>

        <!-- Cross-analysis strategies -->
        <div v-if="deepData.cross_analysis?.length" class="deep-section">
          <h5 class="deep-section__title">
            <span class="material-symbols-outlined" style="font-size: 16px">dataset_linked</span>
            Cross-Data Analysis ({{ deepData.cross_analysis.length }})
          </h5>
          <div class="cross-list">
            <div v-for="(ca, ci) in deepData.cross_analysis" :key="ci" class="cross-card">
              <div class="cross-card__header">
                <span class="cross-card__source">{{ ca.source }}</span>
                <a v-if="ca.access && ca.access.startsWith('http')" :href="ca.access" target="_blank" class="cross-card__link">
                  <span class="material-symbols-outlined" style="font-size: 13px">open_in_new</span>
                </a>
              </div>
              <p class="cross-card__rationale">{{ ca.rationale }}</p>
              <p class="cross-card__insight">
                <span class="material-symbols-outlined" style="font-size: 12px; vertical-align: middle">insights</span>
                {{ ca.expected_insight }}
              </p>
            </div>
          </div>
        </div>

        <!-- Statement improvements -->
        <div v-if="deepData.statement_improvements?.length" class="deep-section">
          <h5 class="deep-section__title">
            <span class="material-symbols-outlined" style="font-size: 16px">edit_note</span>
            Statement Improvements ({{ deepData.statement_improvements.length }})
          </h5>
          <div class="diffs-list">
            <StatementDiff
              v-for="(imp, ii) in deepData.statement_improvements"
              :key="ii"
              :original="imp.original"
              :improved="imp.improved"
              :rationale="imp.rationale"
              :section-hint="imp.section_hint"
            />
          </div>
        </div>
      </div>

      <div v-else-if="deepStatus === 'error'" class="viz-error">
        <span class="material-symbols-outlined" style="color: var(--error)">error</span>
        {{ (deepData as DeepAnalysisResult | null)?.error ?? 'Deep analysis failed.' }}
        <span v-if="(deepData as DeepAnalysisResult | null)?.gemini_required" style="font-size: 11px; margin-top: 4px">
          Add <code>GEMINI_API_KEY</code> to <code>backend/.env</code> to enable this feature.
        </span>
      </div>

      <div v-else-if="deepStatus === 'idle'" class="viz-idle">
        <span class="material-symbols-outlined" style="font-size: 32px; opacity: 0.4">psychology</span>
        <p>Run deep analysis to get simulation proposals, cross-dataset strategies,
          and improved statement rewrites powered by Gemini 2.0 Flash Thinking.</p>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- Tab: PAPERBANANA AGENTIC ILLUSTRATION                                  -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'paperbanana'" class="viz-body">
      <PaperBananaPanel :upload-id="props.uploadId" />
    </div>
  </div>
</template>

<style scoped>
/* ── Shell ── */
.viz-panel {
  display: flex;
  flex-direction: column;
  gap: 0;
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--bg-primary);
}

/* ── Tabs ── */
.viz-tabs {
  display: flex;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-secondary);
  overflow-x: auto;
}

.viz-tab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 10px 16px;
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-tertiary);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--transition-fast);
}

.viz-tab:hover { color: var(--text-primary); background: var(--bg-hover); }
.viz-tab--active {
  color: var(--os-brand);
  border-bottom-color: var(--os-brand);
  background: var(--os-brand-light);
}

/* ── Gemini warning ── */
.gemini-warn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 16px;
  background: rgba(234, 179, 8, 0.08);
  border-bottom: 1px solid rgba(234, 179, 8, 0.2);
  font-size: 11px;
  color: var(--warning);
}

.gemini-warn code {
  font-family: var(--font-mono);
  font-size: 10px;
  background: rgba(234, 179, 8, 0.15);
  padding: 1px 4px;
  border-radius: 3px;
}

/* ── Body ── */
.viz-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.viz-body__header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.viz-body__desc {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.5;
  margin: 0;
  flex: 1;
}

/* ── Action button ── */
.viz-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 7px 14px;
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-on-brand);
  background: var(--os-brand);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--transition-fast);
  flex-shrink: 0;
}

.viz-action-btn:hover:not(:disabled) { background: var(--os-brand-hover); }
.viz-action-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.viz-action-btn--thinking { background: #7c3aed; }
.viz-action-btn--thinking:hover:not(:disabled) { background: #6d28d9; }

/* ── State messages ── */
.viz-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 32px;
  color: var(--text-secondary);
  font-size: 13px;
  text-align: center;
}

.viz-loading--thinking { color: #a78bfa; }

.thinking-hint {
  font-size: 11px;
  color: var(--text-tertiary);
  font-style: italic;
}

.viz-idle {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 36px 24px;
  color: var(--text-tertiary);
  font-size: 12px;
  text-align: center;
}

.viz-idle p { margin: 0; max-width: 340px; }

.viz-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 24px;
  color: var(--error);
  font-size: 12px;
  text-align: center;
}

.viz-error code {
  font-family: var(--font-mono);
  font-size: 10px;
  background: rgba(239, 68, 68, 0.1);
  padding: 1px 4px;
  border-radius: 3px;
}

/* ── Summary bar ── */
.viz-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
}

.viz-count {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
}

.viz-note {
  font-size: 11px;
  color: var(--text-tertiary);
  font-style: italic;
}

/* ── Figure cards ── */
.figures-results { display: flex; flex-direction: column; gap: 8px; }

.figure-card {
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.figure-card__trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 9px 12px;
  background: var(--bg-secondary);
  border: none;
  cursor: pointer;
  font-family: var(--font-sans);
  text-align: left;
  transition: background var(--transition-fast);
}

.figure-card__trigger:hover { background: var(--bg-hover); }

.figure-ref { font-size: 12px; font-weight: 700; color: var(--text-primary); }

.figure-type-badge {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--os-brand);
  background: var(--os-brand-light);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.figure-counts { display: flex; gap: 5px; }

.figure-issue-count {
  font-size: 10px;
  font-weight: 600;
  color: var(--warning);
  background: rgba(234, 179, 8, 0.1);
  padding: 1px 5px;
  border-radius: var(--radius-sm);
}

.figure-req-count {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-tertiary);
  background: var(--bg-tertiary);
  padding: 1px 5px;
  border-radius: var(--radius-sm);
}

.figure-card__body {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  border-top: 1px solid var(--border-secondary);
}

.figure-caption {
  font-size: 12px;
  color: var(--text-tertiary);
  font-style: italic;
  margin: 0;
}

.figure-issues { display: flex; flex-direction: column; gap: 5px; }

.figure-issue {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  font-size: 12px;
  color: var(--warning);
  line-height: 1.4;
}

.figure-reqs ul {
  margin: 4px 0 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.figure-reqs ul li {
  font-size: 12px;
  color: var(--text-secondary);
}

.figure-reqs__title, .figure-code-section > p {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
  margin: 0 0 6px;
}

/* ── Table cards ── */
.tables-results { display: flex; flex-direction: column; gap: 8px; }

.table-card {
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.table-card__trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 9px 12px;
  background: var(--bg-secondary);
  border: none;
  cursor: pointer;
  font-family: var(--font-sans);
  transition: background var(--transition-fast);
}

.table-card__trigger:hover { background: var(--bg-hover); }

.table-issue-count {
  font-size: 10px;
  font-weight: 600;
  color: var(--error);
  background: rgba(239, 68, 68, 0.1);
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  white-space: nowrap;
}

.table-card__body {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-top: 1px solid var(--border-secondary);
}

/* View toggle */
.table-view-toggle {
  display: flex;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  overflow: hidden;
  width: fit-content;
}

.table-view-toggle button {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 500;
  padding: 4px 10px;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-tertiary);
  transition: all var(--transition-fast);
}

.table-view-toggle button.active {
  background: var(--os-brand);
  color: var(--text-on-brand);
}

/* Data table */
.table-scroll { overflow-x: auto; border-radius: var(--radius-sm); border: 1px solid var(--border-secondary); }

.data-table { width: 100%; border-collapse: collapse; font-size: 11px; }
.data-table th {
  text-align: left;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-tertiary);
  padding: 5px 8px;
  border-bottom: 1px solid var(--border-primary);
  background: var(--bg-secondary);
}
.data-table td {
  padding: 5px 8px;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-secondary);
  vertical-align: top;
}

/* Issues */
.table-issues { display: flex; flex-direction: column; gap: 6px; }

.table-issue {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 12px;
  padding: 5px 8px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
}

.issue-sev {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 2px 5px;
  border-radius: var(--radius-sm);
  flex-shrink: 0;
}

.table-analysis-note {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  padding: 7px 10px;
  background: var(--os-brand-light);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: var(--radius-sm);
}

/* ── Diagram ── */
.diagram-controls { display: flex; flex-direction: column; gap: 8px; align-items: flex-end; flex-shrink: 0; }

.diagram-type-pills { display: flex; gap: 4px; flex-wrap: wrap; justify-content: flex-end; }

.diagram-type-pill {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 4px 8px;
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 500;
  color: var(--text-tertiary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.diagram-type-pill:hover { color: var(--text-primary); border-color: var(--border-primary); }
.diagram-type-pill--active { color: var(--os-brand); border-color: var(--os-brand); background: var(--os-brand-light); }

.diagram-result { display: flex; flex-direction: column; gap: 10px; }

.diagram-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.diagram-engine-badge {
  font-size: 10px;
  font-weight: 700;
  color: #a78bfa;
  background: rgba(167, 139, 250, 0.1);
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  margin-right: auto;
}

.diag-dl-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 500;
  color: var(--text-tertiary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  padding: 4px 10px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.diag-dl-btn:hover { color: var(--os-brand); border-color: var(--os-brand); }

.mermaid-output {
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  padding: 20px;
  overflow-x: auto;
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}

:deep(.mermaid-output svg) { max-width: 100%; height: auto; }
.mermaid-fallback { font-family: var(--font-mono); font-size: 11px; color: var(--text-secondary); white-space: pre-wrap; margin: 0; }

/* ── Deep Analysis ── */
.deep-results { display: flex; flex-direction: column; gap: 16px; }

.deep-assessment {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-left: 3px solid var(--os-brand);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.deep-section { display: flex; flex-direction: column; gap: 8px; }

.deep-section__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-tertiary);
  margin: 0;
}

/* Simulations */
.sim-list { display: flex; flex-direction: column; gap: 8px; }

.sim-card {
  padding: 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sim-card__header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

.sim-card__name {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.sim-card__method {
  font-size: 10px;
  color: var(--os-brand);
  background: var(--os-brand-light);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
}

.sim-card__goal {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
}

.sim-card__tools { display: flex; gap: 5px; flex-wrap: wrap; }

.tool-tag {
  font-size: 10px;
  color: var(--text-tertiary);
  background: var(--bg-tertiary);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-secondary);
}

.sim-card__outcome {
  font-size: 11px;
  color: var(--success);
  margin: 0;
  font-style: italic;
}

/* Cross-analysis */
.cross-list { display: flex; flex-direction: column; gap: 8px; }

.cross-card {
  padding: 10px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.cross-card__header { display: flex; align-items: center; gap: 6px; }

.cross-card__source {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.cross-card__link {
  color: var(--os-brand);
  display: inline-flex;
  align-items: center;
}

.cross-card__rationale {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
}

.cross-card__insight {
  font-size: 11px;
  color: var(--text-tertiary);
  font-style: italic;
  margin: 0;
}

/* Statement diffs */
.diffs-list { display: flex; flex-direction: column; gap: 10px; }

/* Spinner */
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Transitions */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  max-height: 2000px; /* Arbitrary large limit */
  opacity: 1;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
  margin: 0;
  padding-top: 0;
  padding-bottom: 0;
}

/* Card Hover State Polish */
.figure-card, .table-card {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.figure-card:hover, .table-card:hover {
  transform: scale(0.995);
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}

.viz-action-btn:active, .table-card__trigger:active, .figure-card__trigger:active {
  transform: scale(0.97);
}
</style>

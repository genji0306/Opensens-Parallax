<script setup lang="ts">
import { computed, ref, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import ActionButton from '@/components/shared/ActionButton.vue'
import { exportDraft, runExperimentDesign, getPipelineStatus, exportLatex, exportBibtex, getDraftVersions } from '@/api/ais'
import type { ExperimentDesignResult, DraftVersion } from '@/api/ais'

const props = defineProps<{
  result: Record<string, unknown>
  runId?: string
}>()

const router = useRouter()
const error = ref<string | null>(null)
const showDraftModal = ref(false)
const draftMarkdown = ref('')
const draftHtml = ref('')
const draftLoading = ref(false)

interface Section {
  heading: string
  content?: string
  complete?: boolean
}

const sections = computed<Section[]>(() => {
  // Try explicit sections array first
  const raw = props.result.sections as Section[] | undefined
  if (raw && Array.isArray(raw) && raw.length > 0) return raw

  // Fallback: parse section_titles from draft metadata
  const titles = props.result.section_titles as string[] | undefined
  if (titles && Array.isArray(titles)) {
    return titles.map(t => ({ heading: t, complete: true }))
  }

  // Fallback: use section_count from backend to show at least the number
  const count = (props.result.section_count ?? props.result.total_sections) as number | undefined
  if (count && count > 0) {
    // No individual titles available — show generic section entries
    return Array.from({ length: count }, (_, i) => ({
      heading: `Section ${i + 1}`,
      complete: true,
    }))
  }

  return []
})

const citationCount = computed(() => {
  const citations = props.result.citations as unknown[] | undefined
  if (citations && Array.isArray(citations)) return citations.length
  return (props.result.citation_count as number) ?? 0
})

const futureDiscussion = computed(() => {
  const raw = props.result.future_discussion as unknown[] | undefined
  return Array.isArray(raw) ? raw : []
})

const exportPath = computed(() => {
  return (props.result.export_path as string) ?? null
})

const reviewScore = computed(() => {
  return (props.result.review_overall as number) ?? null
})

function scoreColor(score: number): string {
  if (score >= 7) return 'var(--success)'
  if (score >= 4) return 'var(--warning)'
  return 'var(--error)'
}

async function handleViewFullDraft() {
  if (!props.runId) return
  draftLoading.value = true
  showDraftModal.value = true
  try {
    const res = await exportDraft(props.runId, 'markdown')
    const md = res.data?.data
    if (typeof md === 'string') {
      draftMarkdown.value = md
      // Simple markdown → HTML conversion (headings, bold, italic, code, lists, paragraphs)
      draftHtml.value = renderMarkdown(md)
    }
  } catch (err) {
    draftHtml.value = '<p style="color: var(--error)">Failed to load draft</p>'
  } finally {
    draftLoading.value = false
  }
}

function renderMarkdown(md: string): string {
  let html = md
    // Escape HTML
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // Headers
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Bold and italic
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Horizontal rules
    .replace(/^---+$/gm, '<hr>')
    // Line breaks → paragraphs
    .replace(/\n\n+/g, '</p><p>')

  html = '<p>' + html + '</p>'
  // Clean empty paragraphs
  html = html.replace(/<p>\s*<\/p>/g, '')
  // Fix headers inside paragraphs
  html = html.replace(/<p>(<h[1-4]>)/g, '$1').replace(/(<\/h[1-4]>)<\/p>/g, '$1')
  html = html.replace(/<p>(<hr>)<\/p>/g, '$1')

  return html
}

function closeDraftModal() {
  showDraftModal.value = false
  draftMarkdown.value = ''
  draftHtml.value = ''
}

async function handleExportMarkdown() {
  if (!props.runId) return
  try {
    const res = await exportDraft(props.runId, 'markdown')
    const markdown = res.data?.data
    if (typeof markdown === 'string') {
      const blob = new Blob([markdown], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `draft-${props.runId}.md`
      a.click()
      URL.revokeObjectURL(url)
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Export failed'
    console.error('Export failed:', err)
  }
}

function handleSendToPaperLab() {
  if (!props.runId) {
    router.push({ name: 'paper-lab' })
    return
  }
  router.push({ name: 'paper-lab', query: { run_id: props.runId } })
}

// ── LaTeX/BibTeX Export ───────────────────────────────────────────────
function handleExportLatex() {
  if (!props.runId) return
  window.open(exportLatex(props.runId), '_blank')
}

function handleExportBibtex() {
  if (!props.runId) return
  window.open(exportBibtex(props.runId), '_blank')
}

// ── Version History ──────────────────────────────────────────────────
const versions = ref<DraftVersion[]>([])
const showVersions = ref(false)

async function fetchVersions() {
  if (!props.runId) return
  try {
    const res = await getDraftVersions(props.runId)
    const data = res.data?.data as unknown as Record<string, unknown>
    versions.value = (data?.versions ?? []) as DraftVersion[]
    showVersions.value = true
  } catch {
    // Version history is optional
  }
}

// ── Experiment Design ──────────────────────────────────────────────────
const experimentLoading = ref(false)
const experimentError = ref<string | null>(null)
const experimentResult = ref<ExperimentDesignResult | null>(null)
let experimentPollTimer: ReturnType<typeof setInterval> | null = null

function clearExperimentPoll() {
  if (experimentPollTimer) {
    clearInterval(experimentPollTimer)
    experimentPollTimer = null
  }
}

onUnmounted(() => clearExperimentPoll())

async function handleRunExperimentDesign() {
  if (!props.runId) return
  experimentLoading.value = true
  experimentError.value = null
  experimentResult.value = null
  clearExperimentPoll()

  try {
    await runExperimentDesign(props.runId)

    let pollCount = 0
    experimentPollTimer = setInterval(async () => {
      pollCount++
      if (pollCount >= 60) {
        experimentError.value = 'Experiment design timed out after 3 minutes'
        experimentLoading.value = false
        clearExperimentPoll()
        return
      }
      try {
        const res = await getPipelineStatus(props.runId!)
        const stageResults = res.data?.data?.stage_results
        if (stageResults?.experiment_design) {
          experimentResult.value = stageResults.experiment_design as ExperimentDesignResult
          experimentLoading.value = false
          clearExperimentPoll()
        }
      } catch {
        // keep polling
      }
    }, 3000)
  } catch (err) {
    experimentLoading.value = false
    experimentError.value = err instanceof Error ? err.message : 'Experiment design failed'
  }
}

function readinessColor(score: number): string {
  if (score >= 7) return 'var(--success)'
  if (score >= 4) return 'var(--warning)'
  return 'var(--error)'
}

function severityColor(severity: string): string {
  if (severity === 'critical') return 'var(--error)'
  if (severity === 'major') return 'var(--warning)'
  return 'var(--info)'
}

// ── Weakness Tracking ─────────────────────────────────────────────────
const reviewStrengths = computed<string[]>(() => {
  const raw = props.result.review_strengths as string[] | undefined
  return Array.isArray(raw) ? raw : []
})

const reviewWeaknesses = computed<string[]>(() => {
  const raw = props.result.review_weaknesses as string[] | undefined
  return Array.isArray(raw) ? raw : []
})

const reviewSuggestions = computed<string[]>(() => {
  const raw = props.result.review_suggestions as string[] | undefined
  return Array.isArray(raw) ? raw : []
})

const hasWeaknessData = computed(() =>
  reviewStrengths.value.length > 0 || reviewWeaknesses.value.length > 0,
)

const hasData = computed(() =>
  sections.value.length > 0
    || citationCount.value > 0
    || reviewScore.value !== null
    || futureDiscussion.value.length > 0
    || exportPath.value !== null,
)
</script>

<template>
  <div class="draft-detail">
    <div v-if="error" class="draft-detail__error">
      <span class="material-symbols-outlined" style="font-size: 16px; color: var(--error)">error</span>
      <span>{{ error }}</span>
    </div>
    <template v-if="hasData">
      <!-- Top Metrics -->
      <div class="draft-detail__metrics">
        <div class="draft-metric">
          <span class="material-symbols-outlined" style="font-size: 18px; color: var(--os-brand)">format_list_numbered</span>
          <div class="draft-metric__content">
            <span class="draft-metric__value font-mono">{{ sections.length }}</span>
            <span class="draft-metric__label">Sections</span>
          </div>
        </div>
        <div class="draft-metric">
          <span class="material-symbols-outlined" style="font-size: 18px; color: var(--info)">link</span>
          <div class="draft-metric__content">
            <span class="draft-metric__value font-mono">{{ citationCount }}</span>
            <span class="draft-metric__label">Citations</span>
          </div>
        </div>
        <div v-if="reviewScore !== null" class="draft-metric">
          <span class="material-symbols-outlined" style="font-size: 18px" :style="{ color: scoreColor(reviewScore) }">grade</span>
          <div class="draft-metric__content">
            <span
              class="draft-metric__value font-mono"
              :style="{ color: scoreColor(reviewScore) }"
            >
              {{ reviewScore.toFixed(1) }}/10
            </span>
            <span class="draft-metric__label">Review Score</span>
          </div>
        </div>
      </div>

      <!-- Section List -->
      <div v-if="sections.length > 0" class="sections-list">
        <h5 class="detail-heading">Sections</h5>
        <div
          v-for="(section, i) in sections"
          :key="i"
          class="section-item"
        >
          <span
            class="material-symbols-outlined section-item__icon"
            :style="{ color: section.complete !== false ? 'var(--success)' : 'var(--text-tertiary)' }"
          >
            {{ section.complete !== false ? 'check_circle' : 'radio_button_unchecked' }}
          </span>
          <span class="section-item__heading">{{ section.heading }}</span>
        </div>
      </div>

      <div v-if="futureDiscussion.length > 0" class="sections-list">
        <h5 class="detail-heading">Future Discussion</h5>
        <div
          v-for="(item, i) in futureDiscussion"
          :key="i"
          class="section-item"
        >
          <span class="material-symbols-outlined section-item__icon" style="color: var(--warning)">forum</span>
          <span class="section-item__heading">{{ String(item) }}</span>
        </div>
      </div>

      <div v-if="exportPath" class="draft-detail__hint">
        <span class="material-symbols-outlined" style="font-size: 16px; color: var(--text-tertiary)">folder</span>
        <span class="font-mono">{{ exportPath }}</span>
      </div>

      <!-- Actions -->
      <div class="draft-detail__actions">
        <ActionButton
          v-if="runId"
          variant="secondary"
          size="sm"
          icon="visibility"
          @click="handleViewFullDraft"
        >
          View Full Draft
        </ActionButton>
        <ActionButton
          v-if="runId"
          variant="ghost"
          size="sm"
          icon="download"
          @click="handleExportMarkdown"
        >
          Export Markdown
        </ActionButton>
        <ActionButton
          v-if="runId"
          variant="ghost"
          size="sm"
          icon="article"
          @click="handleExportLatex"
        >
          LaTeX
        </ActionButton>
        <ActionButton
          v-if="runId"
          variant="ghost"
          size="sm"
          icon="format_quote"
          @click="handleExportBibtex"
        >
          BibTeX
        </ActionButton>
        <ActionButton
          v-if="runId"
          variant="ghost"
          size="sm"
          icon="history"
          @click="fetchVersions"
        >
          Versions
        </ActionButton>
        <ActionButton
          variant="ghost"
          size="sm"
          icon="healing"
          @click="handleSendToPaperLab"
        >
          Send to Paper Lab
        </ActionButton>
        <ActionButton
          v-if="runId"
          variant="secondary"
          size="sm"
          icon="science"
          :disabled="experimentLoading"
          @click="handleRunExperimentDesign"
        >
          {{ experimentLoading ? 'Running...' : 'Run Experiment Design' }}
        </ActionButton>
      </div>

      <!-- ── Experiment Design Section ── -->
      <div v-if="experimentLoading" class="experiment-loading">
        <span class="material-symbols-outlined experiment-loading__spinner">sync</span>
        <span>Running experiment design analysis...</span>
      </div>

      <div v-if="experimentError" class="draft-detail__error">
        <span class="material-symbols-outlined" style="font-size: 16px; color: var(--error)">error</span>
        <span>{{ experimentError }}</span>
      </div>

      <div v-if="experimentResult" class="experiment-design">
        <h5 class="detail-heading">Experiment Design</h5>

        <!-- Readiness + Summary -->
        <div class="experiment-design__header">
          <span
            class="experiment-design__readiness"
            :style="{ background: readinessColor(experimentResult.overall_readiness), color: '#fff' }"
          >
            {{ experimentResult.overall_readiness.toFixed(1) }}/10
          </span>
          <span class="experiment-design__readiness-label">Publication Readiness</span>
        </div>
        <p v-if="experimentResult.summary" class="experiment-design__summary">{{ experimentResult.summary }}</p>

        <!-- Evidence Gaps -->
        <div v-if="experimentResult.gaps && experimentResult.gaps.length > 0" class="experiment-design__gaps">
          <h5 class="detail-heading">Evidence Gaps ({{ experimentResult.gaps.length }})</h5>
          <div
            v-for="(gap, i) in experimentResult.gaps"
            :key="'gap-' + i"
            class="gap-card"
          >
            <div class="gap-card__header">
              <span class="gap-card__severity" :style="{ background: severityColor(gap.severity) }">{{ gap.severity }}</span>
              <span class="gap-card__section">{{ gap.section }}</span>
              <span class="gap-card__type">{{ gap.gap_type }}</span>
            </div>
            <p class="gap-card__description">{{ gap.description }}</p>
            <blockquote v-if="gap.claim" class="gap-card__claim">{{ gap.claim }}</blockquote>
          </div>
        </div>

        <!-- Proposed Experiments -->
        <div v-if="experimentResult.experiments && experimentResult.experiments.length > 0" class="experiment-design__experiments">
          <h5 class="detail-heading">Proposed Experiments ({{ experimentResult.experiments.length }})</h5>
          <div
            v-for="(exp, i) in experimentResult.experiments"
            :key="'exp-' + i"
            class="exp-card"
          >
            <div class="exp-card__title">
              <span class="material-symbols-outlined" style="font-size: 16px; color: var(--os-brand)">science</span>
              <strong>{{ exp.name }}</strong>
              <span v-if="exp.estimated_duration" class="exp-card__duration">{{ exp.estimated_duration }}</span>
            </div>
            <p class="exp-card__objective">{{ exp.objective }}</p>

            <div v-if="exp.equipment && exp.equipment.length > 0" class="exp-card__list-section">
              <span class="exp-card__list-label">Equipment</span>
              <ul class="exp-card__list">
                <li v-for="(item, j) in exp.equipment" :key="'eq-' + j">{{ item }}</li>
              </ul>
            </div>

            <div v-if="exp.controls && exp.controls.length > 0" class="exp-card__list-section">
              <span class="exp-card__list-label">Controls</span>
              <ul class="exp-card__list">
                <li v-for="(item, j) in exp.controls" :key="'ctrl-' + j">{{ item }}</li>
              </ul>
            </div>

            <div v-if="exp.calibration && exp.calibration.length > 0" class="exp-card__list-section">
              <span class="exp-card__list-label">Calibration</span>
              <ul class="exp-card__list">
                <li v-for="(item, j) in exp.calibration" :key="'cal-' + j">{{ item }}</li>
              </ul>
            </div>

            <div v-if="exp.procedure_steps && exp.procedure_steps.length > 0" class="exp-card__list-section">
              <span class="exp-card__list-label">Procedure</span>
              <ol class="exp-card__list exp-card__list--ordered">
                <li v-for="(step, j) in exp.procedure_steps" :key="'step-' + j">{{ step }}</li>
              </ol>
            </div>

            <div v-if="exp.expected_measurements && exp.expected_measurements.length > 0" class="exp-card__list-section">
              <span class="exp-card__list-label">Measurements</span>
              <table class="exp-card__table">
                <thead>
                  <tr>
                    <th>Parameter</th>
                    <th>Unit</th>
                    <th>Range</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(m, j) in exp.expected_measurements" :key="'meas-' + j">
                    <td>{{ m.parameter }}</td>
                    <td class="font-mono">{{ m.unit }}</td>
                    <td class="font-mono">{{ m.range }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Weakness Tracking Section ── -->
      <div v-if="hasWeaknessData" class="weakness-tracking">
        <h5 class="detail-heading">Strengths &amp; Weaknesses</h5>
        <div class="weakness-tracking__columns">
          <div v-if="reviewStrengths.length > 0" class="weakness-tracking__col weakness-tracking__col--strengths">
            <h6 class="weakness-tracking__col-title">Strengths</h6>
            <div
              v-for="(item, i) in reviewStrengths"
              :key="'str-' + i"
              class="weakness-tracking__item"
            >
              <span class="material-symbols-outlined" style="font-size: 14px; color: var(--success)">check</span>
              <span>{{ item }}</span>
            </div>
          </div>
          <div v-if="reviewWeaknesses.length > 0" class="weakness-tracking__col weakness-tracking__col--weaknesses">
            <h6 class="weakness-tracking__col-title">Weaknesses</h6>
            <div
              v-for="(item, i) in reviewWeaknesses"
              :key="'wk-' + i"
              class="weakness-tracking__item"
            >
              <span class="material-symbols-outlined" style="font-size: 14px; color: var(--error)">close</span>
              <span>{{ item }}</span>
            </div>
          </div>
        </div>
        <div v-if="reviewSuggestions.length > 0" class="weakness-tracking__suggestions">
          <h6 class="weakness-tracking__col-title">Suggestions</h6>
          <div
            v-for="(item, i) in reviewSuggestions"
            :key="'sug-' + i"
            class="weakness-tracking__item"
          >
            <span class="material-symbols-outlined" style="font-size: 14px; color: var(--info)">lightbulb</span>
            <span>{{ item }}</span>
          </div>
        </div>
      </div>
    </template>

    <!-- ── Version History Panel ── -->
    <div v-if="showVersions && versions.length > 0" class="version-history">
      <h5 class="detail-heading">Draft Version History ({{ versions.length }})</h5>
      <div class="version-history__list">
        <div v-for="v in versions" :key="v.version_id" class="version-history__item">
          <div class="version-history__header">
            <span class="version-history__num font-mono">v{{ v.version_num }}</span>
            <span class="version-history__title">{{ v.title }}</span>
            <span v-if="v.review_score != null" class="version-history__score font-mono" :style="{ color: scoreColor(v.review_score) }">{{ v.review_score.toFixed(1) }}/10</span>
          </div>
          <div class="version-history__meta">
            <span class="font-mono">{{ v.word_count }} words</span>
            <span v-if="v.change_summary">{{ v.change_summary }}</span>
            <span class="version-history__date">{{ v.created_at?.slice(0, 16).replace('T', ' ') }}</span>
          </div>
        </div>
      </div>
    </div>
    <div v-else-if="showVersions && versions.length === 0" class="version-history__empty">
      <span>No version history yet — versions are saved when the draft is generated or revised.</span>
    </div>

    <div v-else class="draft-detail__empty">
      <span class="material-symbols-outlined" style="font-size: 24px; color: var(--text-tertiary)">edit_document</span>
      <span>No draft data available yet</span>
    </div>

    <!-- ── Draft Viewer Modal ── -->
    <Teleport to="body">
      <div v-if="showDraftModal" class="draft-modal-overlay" @click.self="closeDraftModal">
        <div class="draft-modal">
          <div class="draft-modal__header">
            <h3 class="draft-modal__title">Paper Draft</h3>
            <div class="draft-modal__actions">
              <ActionButton variant="ghost" size="sm" icon="download" @click="handleExportMarkdown">
                Download .md
              </ActionButton>
              <button class="draft-modal__close" @click="closeDraftModal">
                <span class="material-symbols-outlined">close</span>
              </button>
            </div>
          </div>
          <div class="draft-modal__body">
            <div v-if="draftLoading" class="draft-modal__loading">
              <span class="material-symbols-outlined experiment-loading__spinner">sync</span>
              Loading draft...
            </div>
            <div v-else class="draft-modal__content" v-html="draftHtml" />
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.draft-detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 14px;
}

.detail-heading {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin: 0 0 8px;
}

/* ── Metrics ── */
.draft-detail__metrics {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.draft-metric {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-secondary);
}

.draft-metric__content {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.draft-metric__value {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.draft-metric__label {
  font-size: 10px;
  font-weight: 500;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

/* ── Section List ── */
.sections-list {
  display: flex;
  flex-direction: column;
}

.section-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast);
}

.section-item:hover {
  background: var(--bg-hover);
}

.section-item__icon {
  font-size: 16px;
  flex-shrink: 0;
}

.section-item__heading {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}

/* ── Actions ── */
.draft-detail__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.draft-detail__hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-size: 12px;
  overflow-wrap: anywhere;
}

/* ── Version History ── */
.version-history { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }
.version-history__list { display: flex; flex-direction: column; gap: 6px; }
.version-history__item {
  padding: 10px 12px; background: var(--bg-secondary);
  border: 1px solid var(--border-secondary); border-radius: var(--radius-md);
}
.version-history__header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.version-history__num {
  font-size: 11px; font-weight: 700; padding: 2px 6px;
  background: var(--bg-tertiary); border-radius: var(--radius-pill); color: var(--os-brand);
}
.version-history__title { flex: 1; font-size: 12px; font-weight: 600; color: var(--text-primary); }
.version-history__score { font-size: 12px; font-weight: 700; }
.version-history__meta { display: flex; gap: 12px; font-size: 11px; color: var(--text-tertiary); }
.version-history__date { margin-left: auto; }
.version-history__empty { font-size: 12px; color: var(--text-tertiary); padding: 12px; text-align: center; }

.draft-detail__empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 20px;
  color: var(--text-tertiary);
  font-size: 13px;
  justify-content: center;
}

.draft-detail__error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  font-size: 12px;
  color: var(--error);
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: var(--radius-md);
}

/* ── Experiment Loading ── */
.experiment-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
}

.experiment-loading__spinner {
  font-size: 18px;
  color: var(--os-brand);
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ── Experiment Design ── */
.experiment-design {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.experiment-design__header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.experiment-design__readiness {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 700;
  font-family: var(--font-mono, monospace);
}

.experiment-design__readiness-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.experiment-design__summary {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
}

/* ── Gap Cards ── */
.experiment-design__gaps {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.gap-card {
  padding: 10px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.gap-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.gap-card__severity {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #fff;
}

.gap-card__section {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  background: var(--bg-hover);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
}

.gap-card__type {
  font-size: 10px;
  font-weight: 500;
  color: var(--text-tertiary);
}

.gap-card__description {
  font-size: 12px;
  color: var(--text-primary);
  line-height: 1.5;
  margin: 0;
}

.gap-card__claim {
  font-size: 11px;
  color: var(--text-tertiary);
  font-style: italic;
  margin: 2px 0 0;
  padding-left: 10px;
  border-left: 2px solid var(--border-secondary);
  line-height: 1.5;
}

/* ── Experiment Cards ── */
.experiment-design__experiments {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.exp-card {
  padding: 12px 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.exp-card__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-primary);
}

.exp-card__duration {
  margin-left: auto;
  font-size: 10px;
  font-weight: 500;
  padding: 2px 8px;
  background: var(--bg-hover);
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  font-family: var(--font-mono, monospace);
}

.exp-card__objective {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
}

.exp-card__list-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.exp-card__list-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
}

.exp-card__list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: var(--text-primary);
  line-height: 1.6;
}

.exp-card__list--ordered {
  list-style-type: decimal;
}

.exp-card__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}

.exp-card__table th {
  text-align: left;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
  padding: 4px 8px;
  border-bottom: 1px solid var(--border-secondary);
}

.exp-card__table td {
  padding: 4px 8px;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border-secondary);
}

.exp-card__table tr:last-child td {
  border-bottom: none;
}

/* ── Weakness Tracking ── */
.weakness-tracking {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.weakness-tracking__columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

@media (max-width: 600px) {
  .weakness-tracking__columns {
    grid-template-columns: 1fr;
  }
}

.weakness-tracking__col {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-secondary);
}

.weakness-tracking__col--strengths {
  border-left: 3px solid var(--success);
}

.weakness-tracking__col--weaknesses {
  border-left: 3px solid var(--error);
}

.weakness-tracking__col-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  margin: 0 0 4px;
}

.weakness-tracking__item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
  color: var(--text-primary);
  line-height: 1.5;
}

.weakness-tracking__suggestions {
  padding: 10px 12px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-secondary);
  border-left: 3px solid var(--info);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* ── Draft Viewer Modal ── */
.draft-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.draft-modal {
  background: var(--bg-primary, #0a0a0a);
  border: 1px solid var(--border-primary, #333);
  border-radius: 12px;
  width: 100%;
  max-width: 800px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.draft-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-primary, #333);
  flex-shrink: 0;
}

.draft-modal__title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary, #fff);
  margin: 0;
}

.draft-modal__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.draft-modal__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary, #888);
  cursor: pointer;
}

.draft-modal__close:hover {
  background: var(--bg-hover, #222);
  color: var(--text-primary, #fff);
}

.draft-modal__body {
  overflow-y: auto;
  padding: 24px 32px;
  flex: 1;
  min-height: 0;
}

.draft-modal__loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-secondary, #888);
  justify-content: center;
  padding: 40px;
}

.draft-modal__content {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary, #e5e5e5);
}

.draft-modal__content :deep(h1) {
  font-size: 22px;
  font-weight: 700;
  margin: 24px 0 12px;
  color: var(--text-primary, #fff);
  border-bottom: 1px solid var(--border-primary, #333);
  padding-bottom: 8px;
}

.draft-modal__content :deep(h2) {
  font-size: 18px;
  font-weight: 700;
  margin: 20px 0 10px;
  color: var(--text-primary, #fff);
}

.draft-modal__content :deep(h3) {
  font-size: 15px;
  font-weight: 600;
  margin: 16px 0 8px;
  color: var(--text-primary, #fff);
}

.draft-modal__content :deep(p) {
  margin: 0 0 12px;
}

.draft-modal__content :deep(code) {
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  font-size: 12px;
  padding: 2px 6px;
  background: var(--bg-tertiary, #1a1a1a);
  border-radius: 4px;
  color: var(--os-brand, #3b82f6);
}

.draft-modal__content :deep(strong) {
  font-weight: 700;
  color: var(--text-primary, #fff);
}

.draft-modal__content :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-primary, #333);
  margin: 20px 0;
}
</style>

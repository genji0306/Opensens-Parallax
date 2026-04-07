<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { usePipelineStore } from '@/stores/pipeline'
import { useProjectsStore } from '@/stores/projects'
import type { ProjectSummary, StageId } from '@/types/pipeline'
import { classifyRunKind } from '@/utils/runKind'
import { resolveRunDestination } from '@/utils/runDestination'
import {
  STAGE_ORDER,
  STAGE_LABELS,
  STAGE_SHORT_LABELS,
  STAGE_DESCRIPTIONS,
  STAGE_ICONS,
  STATUS_DISPLAY,
  statusToBadgeStatus,
} from '@/types/pipeline'
import PipelineTracker from '@/components/pipeline/PipelineTracker.vue'
import GlassPanel from '@/components/shared/GlassPanel.vue'
import ActionButton from '@/components/shared/ActionButton.vue'
import StatusBadge from '@/components/shared/StatusBadge.vue'
import MetricCard from '@/components/shared/MetricCard.vue'
import NextStepBanner from '@/components/pipeline/NextStepBanner.vue'

const router = useRouter()
const pipeline = usePipelineStore()
const projects = useProjectsStore()
const showNewProjectModal = ref(false)
const selectedProject = ref<ProjectSummary | null>(null)
const newProjectForm = ref({ topic: '', sources: ['arxiv', 'semantic_scholar'], maxPapers: 50 })
const creating = ref(false)

// ── Templates ──
interface TemplateOption {
  template_id: string
  name: string
  description: string
  config: Record<string, unknown>
  step_settings: Record<string, unknown>
  sources: string[]
  category: string
}
const templates = ref<TemplateOption[]>([])
const selectedTemplateId = ref<string | null>(null)
const templatesLoaded = ref(false)

async function fetchTemplates() {
  if (templatesLoaded.value) return
  try {
    const { getTemplates } = await import('@/api/ais')
    const res = await getTemplates()
    const data = res.data?.data as unknown as Record<string, unknown>
    templates.value = ((data?.templates ?? []) as TemplateOption[])
    templatesLoaded.value = true
  } catch { /* templates are optional */ }
}

function applyTemplate(tplId: string) {
  const tpl = templates.value.find(t => t.template_id === tplId)
  if (!tpl) {
    selectedTemplateId.value = null
    return
  }
  selectedTemplateId.value = tplId
  if (tpl.sources?.length) newProjectForm.value.sources = [...tpl.sources]
  if (tpl.config.max_papers) newProjectForm.value.maxPapers = tpl.config.max_papers as number
}

function openNewProjectModal() {
  showNewProjectModal.value = true
  fetchTemplates()
}

// ── Computed ────────────────────────────────────────────────────────────

const stagesArray = computed(() =>
  STAGE_ORDER.map((id) => ({
    id,
    label: STAGE_LABELS[id],
    shortLabel: STAGE_SHORT_LABELS[id],
    description: STAGE_DESCRIPTIONS[id],
    icon: STAGE_ICONS[id],
    status: pipeline.stages[id]?.status ?? 'pending',
    metric: pipeline.stages[id]?.metric,
  }))
)

const hasActiveProject = computed(() => !!selectedProject.value)

// ── Lifecycle ───────────────────────────────────────────────────────────

onMounted(() => {
  // Fire-and-forget — don't block render. AppShell handles system polling.
  projects.fetchRecent(10)
})

// ── Actions ─────────────────────────────────────────────────────────────

function isPaperProject(project: ProjectSummary): boolean {
  return project.type === 'paper' || project.type === 'paper_rehab'
}

function openProject(project: ProjectSummary) {
  const destination = resolveRunDestination({
    runId: project.run_id,
    type: project.type,
    uploadId: project.upload_id,
    reportBaseUrl: import.meta.env.VITE_API_BASE_URL || '',
  })

  if (destination.kind === 'external') {
    window.open(destination.href, '_blank')
    return
  }

  router.push(destination.to)
}

async function selectProject(project: ProjectSummary) {
  if (isPaperProject(project) || project.type === 'report') {
    openProject(project)
    return
  }

  const runKind = classifyRunKind({
    type: project.type,
    runId: project.run_id,
  })
  if (runKind !== 'ais') {
    openProject(project)
    return
  }

  selectedProject.value = project
  await pipeline.loadProject(project.run_id)
}

function handleStageClick(stageId: StageId) {
  if (selectedProject.value) {
    router.push({
      name: 'project',
      params: { runId: selectedProject.value.run_id },
      query: { stage: stageId },
    })
  }
}

async function createProject() {
  if (!newProjectForm.value.topic.trim()) return
  creating.value = true
  try {
    const { startPipeline } = await import('@/api/ais')
    const tpl = selectedTemplateId.value ? templates.value.find(t => t.template_id === selectedTemplateId.value) : null
    const res = await startPipeline({
      research_idea: newProjectForm.value.topic,
      sources: newProjectForm.value.sources,
      max_papers: newProjectForm.value.maxPapers,
      ...(tpl?.step_settings ? { step_settings: tpl.step_settings } : {}),
    })
    const runId = res.data?.data?.run_id
    if (runId) {
      // Close modal immediately — don't wait for route transition
      showNewProjectModal.value = false
      creating.value = false
      router.push({ name: 'project', params: { runId } })
      return
    }
  } catch (err) {
    console.error('Failed to create project:', err)
  } finally {
    creating.value = false
  }
}

// Pre-warm the ais module so createProject doesn't pay the import cost on click
import('@/api/ais').catch(() => {})

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function typeColor(type: string): string {
  const map: Record<string, string> = {
    ais: 'var(--os-brand)',
    debate: 'var(--info)',
    paper: 'var(--warning)',
    paper_rehab: 'var(--warning)',
    report: 'var(--role-phd)',
  }
  return map[type] ?? 'var(--text-tertiary)'
}

function statusForBadge(status: string): 'done' | 'active' | 'pending' | 'failed' {
  return statusToBadgeStatus(status)
}
</script>

<template>
  <div class="command-center">
    <!-- ── Active Project Panel ── -->
    <section v-if="hasActiveProject" class="command-center__active">
      <GlassPanel elevated padding="24px">
        <div class="active-header">
          <div class="active-header__info">
            <h2 class="active-header__title">{{ selectedProject!.title }}</h2>
            <span class="active-header__topic">{{ selectedProject!.topic }}</span>
          </div>
          <ActionButton
            variant="secondary"
            size="sm"
            icon="open_in_new"
            @click="openProject(selectedProject!)"
          >
            Full View
          </ActionButton>
        </div>

        <NextStepBanner
          :project="selectedProject"
          :pipeline="pipeline"
          class="active-next-step"
          @action="openProject(selectedProject!)"
        />

        <PipelineTracker
          :stages="stagesArray"
          :active-stage="pipeline.activeStage?.id"
          class="active-tracker"
          @stage-click="handleStageClick"
        />

        <div class="active-grid">
          <MetricCard
            label="Progress"
            :value="`${pipeline.progressPercent}%`"
            icon="donut_large"
          />
          <MetricCard
            label="Stages Done"
            :value="pipeline.completedStageCount"
            icon="check_circle"
          />
          <MetricCard
            v-if="pipeline.costEstimate"
            label="Cost"
            :value="`$${pipeline.costEstimate.total.toFixed(2)}`"
            icon="payments"
          />
        </div>
      </GlassPanel>
    </section>

    <!-- ── Welcome Banner (compact — no project selected) ── -->
    <section v-else class="command-center__welcome">
      <GlassPanel elevated padding="20px 24px">
        <div class="welcome">
          <div class="welcome__left">
            <span class="material-symbols-outlined welcome__icon">explore</span>
            <div class="welcome__text">
              <h1 class="welcome__title">Command Center</h1>
              <p class="welcome__subtitle">
                Select a project below or start a new one.
              </p>
            </div>
          </div>
          <ActionButton
            variant="primary"
            icon="add"
            @click="openNewProjectModal"
          >
            New Project
          </ActionButton>
        </div>
      </GlassPanel>
    </section>

    <!-- ── Recent Projects ── -->
    <section class="command-center__recent">
      <div class="section-header">
        <h3 class="section-header__title">Recent Projects</h3>
        <ActionButton
          variant="ghost"
          size="sm"
          icon="add"
          @click="openNewProjectModal"
        >
          New Project
        </ActionButton>
      </div>

      <div v-if="projects.loading" class="loading-row">
        <span class="material-symbols-outlined spin">progress_activity</span>
        <span>Loading projects...</span>
      </div>

      <div v-else-if="projects.error" class="error-state">
        <span class="material-symbols-outlined error-state__icon">cloud_off</span>
        <p class="error-state__msg">{{ projects.error }}</p>
        <p class="error-state__hint">
          Run <code>cd platform/OSSR && source .venv/bin/activate && python backend/run.py</code>
        </p>
        <ActionButton variant="secondary" size="sm" icon="refresh" @click="projects.fetchRecent(10)">
          Retry
        </ActionButton>
      </div>

      <div v-else-if="projects.recent.length === 0" class="empty-state">
        <span class="material-symbols-outlined empty-state__icon">folder_open</span>
        <p>No projects yet. Create your first research project to begin.</p>
      </div>

      <div v-else class="project-grid">
        <button
          v-for="project in projects.recent"
          :key="project.run_id"
          class="project-card"
          :class="{ 'project-card--selected': selectedProject?.run_id === project.run_id }"
          @click="selectProject(project)"
          @dblclick="openProject(project)"
        >
          <div class="project-card__header">
            <span
              class="project-card__type-badge"
              :style="{ color: typeColor(project.type), borderColor: typeColor(project.type) }"
            >
              {{ project.type.replace('_', ' ') }}
            </span>
            <StatusBadge
              :status="statusForBadge(project.status)"
              :label="STATUS_DISPLAY[project.status] ?? project.status"
              size="sm"
            />
          </div>
          <h4 class="project-card__title">{{ project.title || project.topic }}</h4>
          <p class="project-card__topic">{{ project.topic }}</p>
          <div class="project-card__footer">
            <span class="project-card__date">{{ formatDate(project.created_at) }}</span>
            <span v-if="project.current_stage" class="project-card__stage">
              <span class="material-symbols-outlined" style="font-size: 14px">
                {{ STAGE_ICONS[project.current_stage as StageId] || 'circle' }}
              </span>
              {{ STAGE_LABELS[project.current_stage as StageId] || project.current_stage }}
            </span>
          </div>
        </button>
      </div>
    </section>

    <!-- ── New Project Modal ── -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showNewProjectModal" class="modal-overlay" @click.self="showNewProjectModal = false">
          <GlassPanel elevated padding="32px" class="modal-content">
            <div class="modal-header">
              <h2 class="modal-header__title">New Research Project</h2>
              <button class="modal-close" @click="showNewProjectModal = false">
                <span class="material-symbols-outlined">close</span>
              </button>
            </div>

            <form class="modal-form" @submit.prevent="createProject">
              <!-- Template Selector -->
              <div v-if="templates.length > 0" class="form-field">
                <span class="form-field__label">Template</span>
                <div class="template-grid">
                  <button
                    type="button"
                    class="template-card"
                    :class="{ 'template-card--active': selectedTemplateId === null }"
                    @click="selectedTemplateId = null"
                  >
                    <span class="template-card__name">Custom</span>
                    <span class="template-card__desc">Configure manually</span>
                  </button>
                  <button
                    v-for="tpl in templates"
                    :key="tpl.template_id"
                    type="button"
                    class="template-card"
                    :class="{ 'template-card--active': selectedTemplateId === tpl.template_id }"
                    @click="applyTemplate(tpl.template_id)"
                  >
                    <span class="template-card__name">{{ tpl.name }}</span>
                    <span class="template-card__desc">{{ tpl.description.slice(0, 60) }}{{ tpl.description.length > 60 ? '...' : '' }}</span>
                  </button>
                </div>
              </div>

              <label class="form-field">
                <span class="form-field__label">Research Topic</span>
                <textarea
                  v-model="newProjectForm.topic"
                  class="form-field__input form-field__textarea"
                  placeholder="Describe the research idea or topic you want to investigate..."
                  rows="4"
                  required
                />
              </label>

              <label class="form-field">
                <span class="form-field__label">Max Papers</span>
                <input
                  v-model.number="newProjectForm.maxPapers"
                  type="number"
                  class="form-field__input"
                  min="10"
                  max="200"
                />
              </label>

              <div class="form-field">
                <span class="form-field__label">Sources</span>
                <div class="source-chips">
                  <label
                    v-for="src in ['arxiv', 'semantic_scholar', 'openalex', 'crossref', 'pubmed', 'biorxiv', 'core', 'europe_pmc', 'doaj', 'openreview', 'ieee', 'springer']"
                    :key="src"
                    class="source-chip"
                    :class="{ 'source-chip--active': newProjectForm.sources.includes(src) }"
                  >
                    <input
                      v-model="newProjectForm.sources"
                      type="checkbox"
                      :value="src"
                      class="sr-only"
                    />
                    {{ src.replace('_', ' ') }}
                  </label>
                </div>
              </div>

              <div class="modal-actions">
                <ActionButton
                  variant="ghost"
                  type="button"
                  @click="showNewProjectModal = false"
                >
                  Cancel
                </ActionButton>
                <ActionButton
                  variant="primary"
                  type="submit"
                  icon="rocket_launch"
                  :loading="creating"
                  :disabled="!newProjectForm.topic.trim()"
                >
                  Start Pipeline
                </ActionButton>
              </div>
            </form>
          </GlassPanel>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.command-center {
  display: flex;
  flex-direction: column;
  gap: 28px;
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

/* ── Active Project ── */
.active-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.active-next-step {
  margin-bottom: 24px;
}

.active-header__title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.active-header__topic {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
  display: block;
}

.active-tracker {
  margin-bottom: 20px;
}

.active-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

/* ── Welcome ── */
.welcome {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.welcome__left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.welcome__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.welcome__icon {
  font-size: 32px;
  color: var(--os-brand);
  font-variation-settings: 'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 32;
  flex-shrink: 0;
}

.welcome__title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.02em;
}

.welcome__subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.4;
  margin: 0;
}

/* ── Section Header ── */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-header__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

/* ── Project Grid ── */
.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}

.project-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-lg);
  cursor: pointer;
  text-align: left;
  font-family: var(--font-sans);
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}

.project-card:hover {
  border-color: var(--os-brand);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.project-card:active {
  transform: translateY(0);
}

.project-card--selected {
  border-color: var(--os-brand);
  box-shadow: 0 0 0 2px rgba(var(--os-brand-rgb), 0.2), var(--shadow-md);
  background: var(--bg-active);
}

.project-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.project-card__type-badge {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 2px 8px;
  border: 1px solid;
  border-radius: var(--radius-pill);
}

.project-card__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.project-card__topic {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.project-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px solid var(--border-secondary);
}

.project-card__date {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-tertiary);
}

.project-card__stage {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-secondary);
}

/* ── Loading / Empty ── */
.loading-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 24px;
  color: var(--text-secondary);
  font-size: 13px;
}

.spin {
  animation: btn-spin 1s linear infinite;
}

@keyframes btn-spin {
  to { transform: rotate(360deg); }
}

.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 32px 24px;
  text-align: center;
  background: rgba(239, 68, 68, 0.04);
  border: 1px solid rgba(239, 68, 68, 0.15);
  border-radius: var(--radius-lg);
}

.error-state__icon {
  font-size: 36px;
  color: var(--error);
}

.error-state__msg {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.error-state__hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0;
}

.error-state__hint code {
  font-family: var(--font-mono);
  font-size: 11px;
  background: var(--bg-tertiary);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 24px;
  color: var(--text-tertiary);
  text-align: center;
}

.empty-state__icon {
  font-size: 36px;
}

.empty-state p {
  font-size: 13px;
  max-width: 320px;
  margin: 0;
}

/* ── Modal ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
  /* No backdrop-filter — causes GPU stall on full-screen blur */
}

.modal-content {
  width: 90%;
  max-width: 520px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.modal-header__title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.modal-close {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-tertiary);
  padding: 4px;
  border-radius: var(--radius-sm);
  transition: color var(--transition-fast), background var(--transition-fast);
}

.modal-close:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.modal-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.form-field__input {
  font-family: var(--font-sans);
  font-size: 14px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-md);
  outline: none;
}

.form-field__input:focus {
  border-color: var(--os-brand);
}

.form-field__textarea {
  resize: vertical;
  min-height: 80px;
}

.source-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.source-chip {
  font-size: 12px;
  font-weight: 500;
  padding: 5px 12px;
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-pill);
  cursor: pointer;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  text-transform: capitalize;
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast),
    color var(--transition-fast);
}

.source-chip--active {
  background: var(--os-brand-light);
  border-color: var(--os-brand);
  color: var(--os-brand);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* ── Template Grid ── */
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px;
}

.template-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.template-card:hover { border-color: var(--os-brand); background: var(--bg-hover); }
.template-card--active { border-color: var(--os-brand); background: var(--os-brand-light); }
.template-card__name { font-size: 12px; font-weight: 600; color: var(--text-primary); }
.template-card__desc { font-size: 10px; color: var(--text-tertiary); line-height: 1.4; }

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}

/* ── Modal Transition ── */
.modal-enter-active { transition: opacity 0.12s ease; }
.modal-leave-active { transition: opacity 0.08s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>

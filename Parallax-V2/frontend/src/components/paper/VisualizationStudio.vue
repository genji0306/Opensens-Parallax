<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type {
  VisualizationArtifact,
  VisualizationPlan,
  VisualizationPlanItem,
} from '@/api/paperLab'
import {
  listVisualizationArtifacts,
  getVisualizationPlan,
  createVisualizationArtifact,
  updateVisualizationArtifact,
  renderVisualizationArtifact,
  auditVisualizationArtifact,
  exportVisualizationArtifact,
  generateGraphicalAbstract,
  generateSlideStarter,
  generatePosterStarter,
} from '@/api/paperLab'
import VisualizationPanel from './VisualizationPanel.vue'
import ArtifactInventory from './ArtifactInventory.vue'
import ArtifactDetailPanel from './ArtifactDetailPanel.vue'
import FigurePlanPanel from './FigurePlanPanel.vue'
import ManuscriptRefinementPanel from './ManuscriptRefinementPanel.vue'
import ActionButton from '@/components/shared/ActionButton.vue'

const props = defineProps<{ uploadId: string }>()

const artifacts = ref<VisualizationArtifact[]>([])
const plan = ref<VisualizationPlan | null>(null)
const loadingArtifacts = ref(false)
const loadingPlan = ref(false)
const selectedArtifact = ref<VisualizationArtifact | null>(null)
const feedback = ref<string | null>(null)
const exportBlockers = ref<string[]>([])
const savingArtifact = ref(false)

function selectLatestArtifactOfType(type: VisualizationArtifact['type'], nextArtifacts: VisualizationArtifact[]) {
  const matches = nextArtifacts.filter(artifact => artifact.type === type)
  if (!matches.length) return null
  return [...matches].sort((left, right) => {
    const leftTime = Date.parse(left.updated_at ?? left.created_at ?? '') || 0
    const rightTime = Date.parse(right.updated_at ?? right.created_at ?? '') || 0
    return rightTime - leftTime
  })[0] ?? null
}

async function loadArtifacts() {
  loadingArtifacts.value = true
  try {
    const res = await listVisualizationArtifacts(props.uploadId)
    const nextArtifacts = res.data?.data ?? []
    artifacts.value = nextArtifacts
    if (selectedArtifact.value) {
      selectedArtifact.value = nextArtifacts.find(artifact => artifact.artifact_id === selectedArtifact.value?.artifact_id) ?? selectedArtifact.value
    }
    return nextArtifacts
  } finally {
    loadingArtifacts.value = false
  }
}

async function loadPlan() {
  loadingPlan.value = true
  try {
    const res = await getVisualizationPlan(props.uploadId)
    plan.value = res.data?.data ?? null
  } finally {
    loadingPlan.value = false
  }
}

async function createFromPlan(item: VisualizationPlanItem) {
  const res = await createVisualizationArtifact(props.uploadId, {
    type: item.type,
    intent: item.intent,
    title: item.title,
    status: item.required_data.length ? 'needs_input' : 'draft',
    payload: {
      source_refs: item.source_refs,
      source_sections: item.source_sections,
      linked_review_findings: item.linked_review_findings,
      data_contract: {
        mode: item.data_mode,
        fields: item.required_data.map(req => ({ name: req, type: 'text', required: true })),
      },
      assumptions: item.required_data,
      recommended_engine: item.recommended_engine,
      content_description: item.content_description,
      layout_modes: item.layout_modes,
    },
  })
  selectedArtifact.value = res.data?.data ?? null
  feedback.value = `Created artifact: ${item.title}`
  const nextArtifacts = await loadArtifacts()
  selectedArtifact.value = nextArtifacts?.find(artifact => artifact.artifact_id === selectedArtifact.value?.artifact_id) ?? selectedArtifact.value
}

async function handleRender(artifact: VisualizationArtifact) {
  const res = await renderVisualizationArtifact(props.uploadId, artifact.artifact_id)
  selectedArtifact.value = res.data?.data ?? null
  feedback.value = `Rendered ${artifact.title}`
  await loadArtifacts()
}

async function handleAudit(artifact: VisualizationArtifact) {
  const res = await auditVisualizationArtifact(props.uploadId, artifact.artifact_id)
  selectedArtifact.value = res.data?.data ?? null
  feedback.value = `Audited ${artifact.title}`
  await loadArtifacts()
}

async function handleExport(artifact: VisualizationArtifact) {
  const res = await exportVisualizationArtifact(props.uploadId, artifact.artifact_id)
  const ready = Boolean(res.data?.data?.ready)
  exportBlockers.value = ready ? [] : ((res.data?.data?.blocked_by as string[] | undefined) ?? [])
  feedback.value = ready
    ? `Export package prepared for ${artifact.title}`
    : `${artifact.title} is blocked until assumptions are resolved`
}

async function saveSelectedArtifact(payload: {
  title: string
  assumptions: string[]
  dataMode: string
  contentDescription?: string
  layoutMode?: string
  slides?: Array<{ title: string; summary: string }>
  panels?: Array<{ name: string; content: string[] }>
  renderingSpec?: unknown
}) {
  if (!selectedArtifact.value) return
  savingArtifact.value = true
  try {
    const currentPayload = selectedArtifact.value.payload ?? {}
    const currentContract = (currentPayload.data_contract as Record<string, unknown> | undefined) ?? {}
    const currentRendering = (currentPayload.rendering as Record<string, unknown> | undefined) ?? {}
    const res = await updateVisualizationArtifact(props.uploadId, selectedArtifact.value.artifact_id, {
      title: payload.title,
      payload: {
        ...currentPayload,
        assumptions: payload.assumptions,
        content_description: payload.contentDescription ?? currentPayload.content_description,
        layout_mode: payload.layoutMode ?? currentPayload.layout_mode,
        slides: payload.slides ?? currentPayload.slides,
        panels: payload.panels ?? currentPayload.panels,
        data_contract: {
          ...currentContract,
          mode: payload.dataMode,
        },
        rendering: payload.renderingSpec === undefined
          ? currentPayload.rendering
          : {
              ...currentRendering,
              spec: payload.renderingSpec,
            },
      },
      status: payload.assumptions.length ? 'needs_input' : 'draft',
    })
    selectedArtifact.value = res.data?.data ?? null
    exportBlockers.value = payload.assumptions
    feedback.value = `Saved ${payload.title}`
    await loadArtifacts()
  } finally {
    savingArtifact.value = false
  }
}

async function createCommunication(kind: 'graphical' | 'slides' | 'poster') {
  if (kind === 'graphical') {
    await generateGraphicalAbstract(props.uploadId)
    feedback.value = 'Generated graphical abstract artifact'
  } else if (kind === 'slides') {
    await generateSlideStarter(props.uploadId)
    feedback.value = 'Generated scientific slide starter'
  } else {
    await generatePosterStarter(props.uploadId)
    feedback.value = 'Generated poster starter'
  }
  const nextArtifacts = await loadArtifacts()
  const targetType: VisualizationArtifact['type'] = kind === 'graphical'
    ? 'graphical_abstract'
    : kind === 'slides'
      ? 'slide'
      : 'poster_panel'
  selectedArtifact.value = selectLatestArtifactOfType(targetType, nextArtifacts ?? []) ?? selectedArtifact.value
}

onMounted(async () => {
  await Promise.all([loadArtifacts(), loadPlan()])
})
</script>

<template>
  <div class="viz-studio">
    <div class="viz-studio__header">
      <div>
        <p class="viz-studio__eyebrow">Visualization Studio</p>
        <h3>Artifacts, planning, rendering, and communication outputs</h3>
      </div>
      <div class="viz-studio__actions">
        <ActionButton variant="secondary" size="sm" icon="gallery_thumbnail" @click="createCommunication('graphical')">Graphical Abstract</ActionButton>
        <ActionButton variant="secondary" size="sm" icon="slideshow" @click="createCommunication('slides')">Slide Starter</ActionButton>
        <ActionButton variant="secondary" size="sm" icon="view_quilt" @click="createCommunication('poster')">Poster Starter</ActionButton>
      </div>
    </div>

    <div v-if="feedback" class="viz-studio__feedback">{{ feedback }}</div>
    <div v-if="exportBlockers.length" class="viz-studio__blockers">
      <strong>Export blockers:</strong> {{ exportBlockers.join(' | ') }}
    </div>

    <div class="viz-studio__grid">
      <ArtifactInventory
        :artifacts="artifacts"
        :loading="loadingArtifacts"
        @refresh="loadArtifacts"
        @select="selectedArtifact = $event"
        @render="handleRender"
        @audit="handleAudit"
        @export="handleExport"
      />

      <FigurePlanPanel
        :plan="plan"
        :loading="loadingPlan"
        @generate="loadPlan"
        @create="createFromPlan"
      />
    </div>

    <ArtifactDetailPanel
      :artifact="selectedArtifact"
      :saving="savingArtifact"
      @save="saveSelectedArtifact"
      @render="selectedArtifact && handleRender(selectedArtifact)"
      @audit="selectedArtifact && handleAudit(selectedArtifact)"
      @export="selectedArtifact && handleExport(selectedArtifact)"
    />

    <ManuscriptRefinementPanel :uploadId="uploadId" :visualizationPlan="plan" />

    <div class="legacy-lab">
      <h4>Legacy Analysis Lab</h4>
      <p>Existing figure/table/diagram analysis stays available here while the persisted studio takes over the workflow.</p>
      <VisualizationPanel :uploadId="uploadId" />
    </div>
  </div>
</template>

<style scoped>
.viz-studio {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.viz-studio__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.viz-studio__eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--os-brand);
}

.viz-studio h3,
.legacy-lab h4,
.selected-artifact h4 {
  margin: 0;
  color: var(--text-primary);
}

.viz-studio__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.viz-studio__feedback {
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: rgba(204, 255, 0, 0.08);
  border: 1px solid rgba(204, 255, 0, 0.18);
  font-size: 12px;
  color: var(--text-secondary);
}

.viz-studio__blockers {
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.18);
  font-size: 12px;
  color: var(--text-secondary);
}

.viz-studio__grid {
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  gap: 16px;
}

.legacy-lab {
  padding: 16px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-secondary);
  background: var(--bg-secondary);
}

.legacy-lab p {
  margin: 6px 0 14px;
  font-size: 12px;
  color: var(--text-secondary);
}

@media (max-width: 1080px) {
  .viz-studio__grid {
    grid-template-columns: 1fr;
  }
}
</style>

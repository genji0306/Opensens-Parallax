<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import DOMPurify from 'dompurify'
import type { VisualizationArtifact } from '@/api/paperLab'
import ActionButton from '@/components/shared/ActionButton.vue'

const props = defineProps<{
  artifact: VisualizationArtifact | null
  saving?: boolean
}>()

const emit = defineEmits<{
  save: [payload: {
    title: string
    assumptions: string[]
    dataMode: string
    contentDescription?: string
    layoutMode?: string
    slides?: Array<{ title: string; summary: string }>
    panels?: Array<{ name: string; content: string[] }>
    renderingSpec?: unknown
  }]
  render: []
  audit: []
  export: []
}>()

const title = ref('')
const assumptionsText = ref('')
const dataMode = ref('inferred')
const contentDescription = ref('')
const layoutMode = ref('')
const slidesText = ref('')
const panelsText = ref('')
const specText = ref('')
const chartMark = ref('bar')
const chartXAxis = ref('')
const chartYAxis = ref('')
const chartColor = ref('')
const gaProblem = ref('')
const gaMethod = ref('')
const gaResult = ref('')

watch(
  () => props.artifact,
  (artifact) => {
    title.value = artifact?.title ?? ''
    const payload = artifact?.payload ?? {}
    const assumptions = Array.isArray(payload.assumptions) ? payload.assumptions : []
    assumptionsText.value = assumptions.join('\n')
    const contract = payload.data_contract as { mode?: string } | undefined
    dataMode.value = contract?.mode ?? 'inferred'
    contentDescription.value = String(payload.content_description ?? '')
    layoutMode.value = String(payload.layout_mode ?? '')
    const slides = Array.isArray(payload.slides) ? payload.slides as Array<Record<string, unknown>> : []
    slidesText.value = slides
      .map(slide => `${String(slide.title ?? 'Slide')}: ${String(slide.summary ?? '')}`)
      .join('\n')
    const panels = Array.isArray(payload.panels) ? payload.panels as Array<Record<string, unknown>> : []
    panelsText.value = panels
      .map((panel) => {
        const name = String(panel.name ?? 'Panel')
        const content = Array.isArray(panel.content) ? panel.content.map(String).join(' | ') : String(panel.content ?? '')
        return `${name}: ${content}`
      })
      .join('\n')
    const rawSpec = (payload.rendering as { spec?: unknown } | undefined)?.spec
    specText.value = rawSpec == null
      ? ''
      : typeof rawSpec === 'string'
        ? rawSpec
        : JSON.stringify(rawSpec, null, 2)
    const chartSpec = rawSpec && typeof rawSpec === 'object' ? rawSpec as Record<string, unknown> : {}
    chartMark.value = String(chartSpec.mark ?? 'bar')
    const encoding = (chartSpec.encoding as Record<string, unknown> | undefined) ?? {}
    const xField = (encoding.x as Record<string, unknown> | undefined)?.field
    const yField = (encoding.y as Record<string, unknown> | undefined)?.field
    const colorField = (encoding.color as Record<string, unknown> | undefined)?.field
    chartXAxis.value = String(xField ?? '')
    chartYAxis.value = String(yField ?? '')
    chartColor.value = String(colorField ?? '')
    if (artifact?.type === 'graphical_abstract' && typeof rawSpec === 'string') {
      gaProblem.value = (rawSpec.match(/<h2>Problem<\/h2><p>(.*?)<\/p>/)?.[1] ?? '').replace(/&amp;/g, '&')
      gaMethod.value = (rawSpec.match(/<h2>Method<\/h2><p>(.*?)<\/p>/)?.[1] ?? '').replace(/&amp;/g, '&')
      gaResult.value = (rawSpec.match(/<h2>Result<\/h2><p>(.*?)<\/p>/)?.[1] ?? '').replace(/&amp;/g, '&')
    } else {
      gaProblem.value = ''
      gaMethod.value = ''
      gaResult.value = ''
    }
  },
  { immediate: true },
)

const assumptions = computed(() =>
  assumptionsText.value
    .split('\n')
    .map(item => item.trim())
    .filter(Boolean),
)

const payload = computed(() => props.artifact?.payload ?? {})
const rendering = computed(() => (payload.value.rendering as Record<string, unknown> | undefined) ?? {})
const renderingSpec = computed(() => rendering.value.spec)
const isHtmlArtifact = computed(() =>
  props.artifact?.type === 'graphical_abstract'
  || rendering.value.engine === 'html'
  || typeof renderingSpec.value === 'string',
)
const sanitizedHtml = computed(() =>
  isHtmlArtifact.value && typeof renderingSpec.value === 'string'
    ? DOMPurify.sanitize(renderingSpec.value)
    : '',
)
const slideItems = computed(() => Array.isArray(payload.value.slides) ? payload.value.slides as Array<Record<string, unknown>> : [])
const posterPanels = computed(() => Array.isArray(payload.value.panels) ? payload.value.panels as Array<Record<string, unknown>> : [])
const dataFields = computed(() => {
  const contract = payload.value.data_contract as { fields?: Array<{ name?: string; type?: string; required?: boolean }> } | undefined
  return contract?.fields ?? []
})
const layoutModes = computed(() => Array.isArray(payload.value.layout_modes) ? payload.value.layout_modes as string[] : [])
const sourceRefs = computed(() => Array.isArray(payload.value.source_refs) ? payload.value.source_refs as string[] : [])
const sourceSections = computed(() => Array.isArray(payload.value.source_sections) ? payload.value.source_sections as string[] : [])
const linkedFindings = computed(() => Array.isArray(payload.value.linked_review_findings) ? payload.value.linked_review_findings as string[] : [])
const provenanceEntries = computed(() => Object.entries(props.artifact?.provenance ?? {}))
const readinessState = computed(() => {
  if (assumptions.value.length) return 'blocked'
  if (props.artifact?.audit?.consistency_status === 'fail') return 'blocked'
  if (props.artifact?.audit?.ready === false) return 'needs review'
  return props.artifact?.status === 'ready' ? 'ready' : 'in progress'
})
const confidenceLabel = computed(() => {
  const confidence = props.artifact?.audit?.confidence
  if (typeof confidence !== 'number') return 'unknown'
  return `${Math.round(confidence * 100)}%`
})
const prettySpec = computed(() => {
  if (typeof renderingSpec.value === 'string') return renderingSpec.value
  if (renderingSpec.value && typeof renderingSpec.value === 'object') return JSON.stringify(renderingSpec.value, null, 2)
  return JSON.stringify(payload.value, null, 2)
})

function parseSlides(text: string): Array<{ title: string; summary: string }> {
  return text
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [titlePart, ...rest] = line.split(':')
      return {
        title: titlePart?.trim() || 'Slide',
        summary: rest.join(':').trim(),
      }
    })
}

function parsePanels(text: string): Array<{ name: string; content: string[] }> {
  return text
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [namePart, ...rest] = line.split(':')
      return {
        name: namePart?.trim() || 'Panel',
        content: rest.join(':').split('|').map(item => item.trim()).filter(Boolean),
      }
    })
}

function parseRenderingSpec(text: string): unknown {
  const trimmed = text.trim()
  if (!trimmed) return undefined
  try {
    return JSON.parse(trimmed)
  } catch {
    return trimmed
  }
}

function buildChartSpec(): Record<string, unknown> {
  const spec: Record<string, unknown> = {
    mark: chartMark.value || 'bar',
    encoding: {
      x: { field: chartXAxis.value || 'x', type: 'nominal' },
      y: { field: chartYAxis.value || 'y', type: 'quantitative' },
    },
  }
  if (chartColor.value.trim()) {
    ;(spec.encoding as Record<string, unknown>).color = { field: chartColor.value.trim(), type: 'nominal' }
  }
  return spec
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function buildGraphicalAbstractHtml(): string {
  const mode = layoutMode.value || 'process_summary'
  return `
<section class="ga ga--${escapeHtml(mode)}">
  <header><h1>${escapeHtml(title.value || props.artifact?.title || 'Graphical Abstract')}</h1><p>${escapeHtml(mode.replace(/_/g, ' '))}</p></header>
  <div class="ga__grid">
    <article><h2>Problem</h2><p>${escapeHtml(gaProblem.value || 'Summarize the research problem here.')}</p></article>
    <article><h2>Method</h2><p>${escapeHtml(gaMethod.value || 'Outline the key method steps here.')}</p></article>
    <article><h2>Result</h2><p>${escapeHtml(gaResult.value || 'State the most important result here.')}</p></article>
  </div>
</section>
  `.trim()
}

function handleSave() {
  const artifactType = props.artifact?.type ?? ''
  const renderingSpec = artifactType === 'chart'
    ? buildChartSpec()
    : artifactType === 'graphical_abstract'
      ? buildGraphicalAbstractHtml()
      : ['diagram'].includes(artifactType)
        ? parseRenderingSpec(specText.value)
        : undefined
  emit('save', {
    title: title.value.trim() || props.artifact?.title || 'Untitled Artifact',
    assumptions: assumptions.value,
    dataMode: dataMode.value,
    contentDescription: contentDescription.value.trim() || undefined,
    layoutMode: layoutMode.value || undefined,
    slides: props.artifact?.type === 'slide' ? parseSlides(slidesText.value) : undefined,
    panels: props.artifact?.type === 'poster_panel' ? parsePanels(panelsText.value) : undefined,
    renderingSpec,
  })
}
</script>

<template>
  <section class="artifact-detail">
    <div v-if="!artifact" class="artifact-detail__empty">
      Select an artifact to inspect its data grounding, assumptions, and export readiness.
    </div>

    <template v-else>
      <div class="artifact-detail__header">
        <div>
          <p class="artifact-detail__eyebrow">{{ artifact.type }} · {{ artifact.intent }}</p>
          <h4>Artifact Workspace</h4>
        </div>
        <div class="artifact-detail__badges">
          <span class="badge">Status: {{ artifact.status }}</span>
          <span class="badge">v{{ artifact.version }}</span>
          <span class="badge">Audit: {{ artifact.audit?.consistency_status ?? 'unknown' }}</span>
        </div>
      </div>

      <div class="artifact-detail__grid">
        <label class="field">
          <span>Title</span>
          <input v-model="title" type="text" />
        </label>

        <label class="field">
          <span>Data grounding mode</span>
          <select v-model="dataMode">
            <option value="inferred">Inferred from manuscript</option>
            <option value="table_extracted">Extracted from tables</option>
            <option value="user_supplied">User supplied</option>
            <option value="mixed">Mixed</option>
          </select>
        </label>
      </div>

      <label class="field">
        <span>Assumptions / export blockers</span>
        <textarea
          v-model="assumptionsText"
          rows="5"
          placeholder="One blocker or assumption per line"
        />
      </label>

      <div class="artifact-detail__grid">
        <label class="field">
          <span>Content description</span>
          <textarea
            v-model="contentDescription"
            rows="3"
            placeholder="Describe what this artifact should communicate"
          />
        </label>

        <label v-if="layoutModes.length" class="field">
          <span>Layout mode</span>
          <select v-model="layoutMode">
            <option value="">Default</option>
            <option v-for="mode in layoutModes" :key="mode" :value="mode">{{ mode }}</option>
          </select>
        </label>
      </div>

      <div class="artifact-detail__summary">
        <p><strong>Readiness:</strong> {{ readinessState }}</p>
        <p><strong>Confidence:</strong> {{ confidenceLabel }}</p>
        <p><strong>Provenance:</strong> {{ artifact.provenance?.generated_by || 'unknown' }}</p>
        <p><strong>Issues:</strong> {{ artifact.audit?.issues?.join(' | ') || 'none' }}</p>
      </div>

      <div v-if="sourceRefs.length || sourceSections.length || linkedFindings.length" class="artifact-detail__context">
        <p v-if="sourceRefs.length"><strong>Source refs:</strong> {{ sourceRefs.join(' | ') }}</p>
        <p v-if="sourceSections.length"><strong>Source sections:</strong> {{ sourceSections.join(' | ') }}</p>
        <p v-if="linkedFindings.length"><strong>Linked findings:</strong> {{ linkedFindings.join(' | ') }}</p>
      </div>

      <div v-if="provenanceEntries.length" class="artifact-detail__provenance">
        <h5>Provenance Details</h5>
        <dl>
          <div v-for="[key, value] in provenanceEntries" :key="key" class="artifact-detail__provenance-row">
            <dt>{{ key }}</dt>
            <dd>{{ typeof value === 'object' ? JSON.stringify(value) : String(value) }}</dd>
          </div>
        </dl>
      </div>

      <label v-if="artifact.type === 'slide'" class="field">
        <span>Slides</span>
        <textarea
          v-model="slidesText"
          rows="5"
          placeholder="One slide per line. Format: Title: Summary"
        />
      </label>

      <label v-if="artifact.type === 'poster_panel'" class="field">
        <span>Poster panels</span>
        <textarea
          v-model="panelsText"
          rows="5"
          placeholder="One panel per line. Format: Panel name: item one | item two"
        />
      </label>

      <div v-if="artifact.type === 'chart'" class="artifact-detail__grid">
        <label class="field">
          <span>Chart mark</span>
          <select v-model="chartMark">
            <option value="bar">Bar</option>
            <option value="line">Line</option>
            <option value="point">Point</option>
            <option value="area">Area</option>
          </select>
        </label>
        <label class="field">
          <span>X field</span>
          <input v-model="chartXAxis" type="text" placeholder="e.g. condition" />
        </label>
        <label class="field">
          <span>Y field</span>
          <input v-model="chartYAxis" type="text" placeholder="e.g. performance" />
        </label>
        <label class="field">
          <span>Color field</span>
          <input v-model="chartColor" type="text" placeholder="optional grouping field" />
        </label>
      </div>

      <div v-if="artifact.type === 'graphical_abstract'" class="artifact-detail__grid">
        <label class="field">
          <span>Problem block</span>
          <textarea v-model="gaProblem" rows="4" placeholder="Problem summary" />
        </label>
        <label class="field">
          <span>Method block</span>
          <textarea v-model="gaMethod" rows="4" placeholder="Method summary" />
        </label>
        <label class="field">
          <span>Result block</span>
          <textarea v-model="gaResult" rows="4" placeholder="Result summary" />
        </label>
      </div>

      <label v-if="artifact.type === 'diagram'" class="field">
        <span>Rendering spec</span>
        <textarea
          v-model="specText"
          rows="10"
          placeholder="JSON spec or HTML payload"
        />
      </label>

      <div class="artifact-detail__preview">
        <h5>Preview</h5>

        <div v-if="isHtmlArtifact && sanitizedHtml" class="artifact-preview artifact-preview--html" v-html="sanitizedHtml" />

        <div v-else-if="artifact.type === 'slide' && slideItems.length" class="artifact-preview artifact-preview--slides">
          <article v-for="(slide, index) in slideItems" :key="index" class="slide-card">
            <p class="slide-card__index">Slide {{ index + 1 }}</p>
            <h6>{{ slide.title || `Slide ${index + 1}` }}</h6>
            <p>{{ slide.summary || 'No summary available.' }}</p>
          </article>
        </div>

        <div v-else-if="artifact.type === 'poster_panel' && posterPanels.length" class="artifact-preview artifact-preview--poster">
          <article v-for="(panel, index) in posterPanels" :key="index" class="poster-card">
            <h6>{{ panel.name || `Panel ${index + 1}` }}</h6>
            <p>{{ Array.isArray(panel.content) ? panel.content.join(' | ') : (panel.content || 'No content yet.') }}</p>
          </article>
        </div>

        <div v-else class="artifact-preview artifact-preview--spec">
          <div v-if="dataFields.length" class="data-fields">
            <p class="data-fields__title">Data contract</p>
            <ul>
              <li v-for="field in dataFields" :key="field.name">
                {{ field.name || 'field' }} · {{ field.type || 'text' }}<span v-if="field.required"> · required</span>
              </li>
            </ul>
          </div>
          <pre>{{ prettySpec }}</pre>
        </div>
      </div>

      <div class="artifact-detail__actions">
        <ActionButton variant="secondary" size="sm" icon="save" :loading="saving" @click="handleSave">Save Artifact</ActionButton>
        <ActionButton variant="ghost" size="sm" icon="insert_chart" @click="emit('render')">Render</ActionButton>
        <ActionButton variant="ghost" size="sm" icon="fact_check" @click="emit('audit')">Audit</ActionButton>
        <ActionButton variant="ghost" size="sm" icon="download" @click="emit('export')">Export</ActionButton>
      </div>
    </template>
  </section>
</template>

<style scoped>
.artifact-detail {
  padding: 16px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-secondary);
  background: var(--bg-secondary);
}

.artifact-detail__empty {
  font-size: 12px;
  color: var(--text-secondary);
}

.artifact-detail__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.artifact-detail__eyebrow {
  margin: 0 0 4px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--os-brand);
}

.artifact-detail h4 {
  margin: 0;
  color: var(--text-primary);
}

.artifact-detail__badges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.badge {
  padding: 6px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-secondary);
  font-size: 11px;
  color: var(--text-secondary);
}

.artifact-detail__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field span,
.artifact-detail__summary p {
  font-size: 12px;
  color: var(--text-secondary);
}

.field input,
.field select,
.field textarea {
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  background: rgba(0, 0, 0, 0.2);
  color: var(--text-primary);
  padding: 10px 12px;
  font: inherit;
}

.artifact-detail__summary {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 14px 0;
}

.artifact-detail__summary p,
.artifact-detail__context p {
  margin: 0;
}

.artifact-detail__context {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0 0 14px;
}

.artifact-detail__provenance {
  margin: 0 0 14px;
  padding: 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-secondary);
  background: rgba(255, 255, 255, 0.02);
}

.artifact-detail__provenance h5 {
  margin: 0 0 10px;
  color: var(--text-primary);
}

.artifact-detail__provenance dl {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.artifact-detail__provenance-row {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 10px;
}

.artifact-detail__provenance-row dt,
.artifact-detail__provenance-row dd {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.artifact-detail__provenance-row dt {
  color: var(--text-primary);
}

.artifact-detail__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.artifact-detail__preview {
  margin: 16px 0;
  padding: 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-secondary);
  background: rgba(255, 255, 255, 0.03);
}

.artifact-detail__preview h5,
.slide-card h6,
.poster-card h6 {
  margin: 0;
  color: var(--text-primary);
}

.artifact-preview--html {
  overflow: auto;
  border-radius: var(--radius-md);
  background: white;
  color: #111827;
  padding: 14px;
}

.artifact-preview--slides,
.artifact-preview--poster {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.slide-card,
.poster-card {
  padding: 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-secondary);
  background: rgba(0, 0, 0, 0.18);
}

.slide-card__index,
.slide-card p,
.poster-card p,
.data-fields__title,
.data-fields li {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.artifact-preview--spec pre {
  margin: 10px 0 0;
  padding: 12px;
  border-radius: var(--radius-md);
  overflow: auto;
  font-size: 11px;
  background: rgba(0, 0, 0, 0.22);
  color: var(--text-secondary);
}

.data-fields ul {
  margin: 8px 0 0;
  padding-left: 18px;
}

@media (max-width: 900px) {
  .artifact-detail__grid {
    grid-template-columns: 1fr;
  }
}
</style>

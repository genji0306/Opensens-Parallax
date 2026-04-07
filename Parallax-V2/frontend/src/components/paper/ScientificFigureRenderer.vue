<script setup lang="ts">
import { ref, watch, onMounted, nextTick, computed, type ComponentPublicInstance } from 'vue'

interface RenderedFigure {
  ref: string
  title: string
  caption: string
  chart_type: string
  vega_lite_spec: Record<string, unknown> | null
  renderable: boolean
  reason?: string
  data_requirements: string[]
  issues: string[]
}

const props = defineProps<{
  figures: RenderedFigure[]
}>()

const emit = defineEmits<{
  (e: 'audit-request'): void
}>()

const containerRefs = ref<Record<string, HTMLElement | null>>({})
const activeIndex = ref(0)
const theme = ref<'light' | 'dark'>('light')

const activeFigure = computed(() => props.figures[activeIndex.value])
const renderableCount = computed(() => props.figures.filter(f => f.renderable).length)

function setContainerRef(figRef: string) {
  return (el: Element | ComponentPublicInstance | null) => {
    containerRefs.value[figRef] = el as HTMLElement | null
  }
}

async function renderSpec(figure: RenderedFigure) {
  if (!figure.renderable || !figure.vega_lite_spec) return

  const el = containerRefs.value[figure.ref]
  if (!el) return

  try {
    const vegaEmbed = (await import('vega-embed')).default
    const spec = { ...figure.vega_lite_spec } as Record<string, unknown>

    // Apply dark theme config
    if (theme.value === 'dark') {
      spec.config = {
        ...(spec.config as Record<string, unknown> || {}),
        background: '#161B22',
        axis: {
          gridColor: '#2A3544',
          domainColor: '#2A3544',
          tickColor: '#2A3544',
          labelColor: '#8B9DB3',
          titleColor: '#E6ECF1',
        },
        title: {
          color: '#E6ECF1',
          subtitleColor: '#8B9DB3',
        },
        legend: {
          labelColor: '#8B9DB3',
          titleColor: '#E6ECF1',
        },
        view: { stroke: '#2A3544' },
      }
    }

    await vegaEmbed(el, spec as never, {
      actions: { export: true, source: false, compiled: false, editor: false },
      renderer: 'svg',
    })
  } catch (err) {
    console.error(`Failed to render ${figure.ref}:`, err)
  }
}

async function renderActive() {
  await nextTick()
  const fig = activeFigure.value
  if (fig) await renderSpec(fig)
}

watch(activeIndex, renderActive)
watch(theme, renderActive)

onMounted(() => {
  // Detect system theme
  const html = document.documentElement
  if (html.getAttribute('data-theme') === 'dark') {
    theme.value = 'dark'
  }
  renderActive()
})

function downloadSpec(figure: RenderedFigure) {
  if (!figure.vega_lite_spec) return
  const blob = new Blob([JSON.stringify(figure.vega_lite_spec, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${figure.ref.replace(/\s+/g, '_')}_vegalite.json`
  a.click()
  URL.revokeObjectURL(url)
}

const chartTypeLabels: Record<string, string> = {
  scatter: 'Scatter Plot',
  bar: 'Bar Chart',
  line: 'Line Chart',
  heatmap: 'Heatmap',
  box: 'Box Plot',
  other: 'Other',
}
</script>

<template>
  <div class="sci-viz-renderer">
    <!-- Header -->
    <div class="sci-viz-header">
      <div class="sci-viz-title">
        <span class="material-symbols-outlined" style="font-size: 18px">insert_chart</span>
        Interactive Figures
        <span class="sci-viz-count">{{ renderableCount }}/{{ figures.length }} renderable</span>
      </div>
      <div class="sci-viz-actions">
        <button class="sci-viz-btn ghost" @click="theme = theme === 'light' ? 'dark' : 'light'">
          <span class="material-symbols-outlined" style="font-size: 16px">
            {{ theme === 'light' ? 'dark_mode' : 'light_mode' }}
          </span>
        </button>
        <button class="sci-viz-btn ghost" @click="emit('audit-request')">
          <span class="material-symbols-outlined" style="font-size: 16px">checklist</span>
          Audit
        </button>
      </div>
    </div>

    <!-- Figure tabs -->
    <div v-if="figures.length > 1" class="sci-viz-tabs">
      <button
        v-for="(fig, i) in figures"
        :key="fig.ref"
        class="sci-viz-tab"
        :class="{ active: activeIndex === i, unrenderable: !fig.renderable }"
        @click="activeIndex = i"
      >
        {{ fig.ref }}
        <span class="tab-type">{{ chartTypeLabels[fig.chart_type] || fig.chart_type }}</span>
      </button>
    </div>

    <!-- Active figure -->
    <div v-if="activeFigure" class="sci-viz-figure">
      <div v-if="activeFigure.renderable" class="sci-viz-chart-wrap" :class="theme">
        <div :ref="setContainerRef(activeFigure.ref)" class="sci-viz-chart" />
      </div>
      <div v-else class="sci-viz-unsupported">
        <span class="material-symbols-outlined" style="font-size: 32px; opacity: 0.4">image_not_supported</span>
        <p>{{ activeFigure.reason || 'Chart type not supported for browser rendering' }}</p>
        <p class="hint">The Python reconstruction code is available in the Figures analysis tab.</p>
      </div>

      <!-- Meta info -->
      <div class="sci-viz-meta">
        <div v-if="activeFigure.caption" class="meta-row">
          <span class="meta-label">Caption</span>
          <span class="meta-value">{{ activeFigure.caption }}</span>
        </div>

        <div v-if="activeFigure.data_requirements.length" class="meta-row">
          <span class="meta-label">Data Requirements</span>
          <ul class="meta-list">
            <li v-for="req in activeFigure.data_requirements" :key="req">{{ req }}</li>
          </ul>
        </div>

        <div v-if="activeFigure.issues.length" class="meta-row">
          <span class="meta-label">Issues</span>
          <ul class="meta-list issues">
            <li v-for="issue in activeFigure.issues" :key="issue">
              <span class="material-symbols-outlined" style="font-size: 14px; color: var(--warning)">warning</span>
              {{ issue }}
            </li>
          </ul>
        </div>

        <div v-if="activeFigure.renderable" class="meta-actions">
          <button class="sci-viz-btn ghost small" @click="downloadSpec(activeFigure)">
            <span class="material-symbols-outlined" style="font-size: 14px">download</span>
            Vega-Lite JSON
          </button>
        </div>
      </div>
    </div>

    <div v-else class="sci-viz-empty">
      <p>No figures to render. Run figure analysis first.</p>
    </div>
  </div>
</template>

<style scoped>
.sci-viz-renderer {
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.sci-viz-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-secondary);
  background: var(--bg-secondary);
}

.sci-viz-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.sci-viz-count {
  font-weight: 400;
  font-size: 11px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
}

.sci-viz-actions {
  display: flex;
  gap: 6px;
}

.sci-viz-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border-secondary);
  overflow-x: auto;
}

.sci-viz-tab {
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--transition-fast);
}

.sci-viz-tab:hover { color: var(--text-primary); background: var(--bg-hover); }
.sci-viz-tab.active { color: var(--os-brand); border-bottom-color: var(--os-brand); }
.sci-viz-tab.unrenderable { opacity: 0.5; }

.tab-type {
  font-size: 10px;
  font-weight: 400;
  color: var(--text-tertiary);
  margin-left: 4px;
}

.sci-viz-chart-wrap {
  padding: 16px;
  background: var(--bg-primary);
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sci-viz-chart-wrap.dark {
  background: #161B22;
}

.sci-viz-chart {
  width: 100%;
  max-width: 560px;
}

.sci-viz-unsupported {
  padding: 40px 16px;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
}

.sci-viz-unsupported .hint {
  font-size: 11px;
  margin-top: 4px;
  opacity: 0.7;
}

.sci-viz-meta {
  padding: 12px 14px;
  border-top: 1px solid var(--border-secondary);
  background: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.meta-row {
  display: flex;
  gap: 8px;
  font-size: 12px;
}

.meta-label {
  font-weight: 500;
  color: var(--text-secondary);
  min-width: 110px;
  flex-shrink: 0;
}

.meta-value {
  color: var(--text-primary);
  font-style: italic;
}

.meta-list {
  margin: 0;
  padding-left: 16px;
  color: var(--text-primary);
}

.meta-list li { margin-bottom: 2px; }

.meta-list.issues li {
  display: flex;
  align-items: center;
  gap: 4px;
}

.meta-actions {
  display: flex;
  gap: 6px;
  padding-top: 4px;
}

.sci-viz-empty {
  padding: 40px 16px;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
}

.sci-viz-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  border-radius: var(--radius-md);
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.sci-viz-btn.ghost {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-primary);
}

.sci-viz-btn.ghost:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.sci-viz-btn.small { padding: 4px 8px; font-size: 11px; }
</style>

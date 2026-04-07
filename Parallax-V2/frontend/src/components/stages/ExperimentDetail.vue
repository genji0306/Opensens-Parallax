<script setup lang="ts">
import { computed, ref } from 'vue'
import MetricCard from '@/components/shared/MetricCard.vue'
import ActionButton from '@/components/shared/ActionButton.vue'
import StatusBadge from '@/components/shared/StatusBadge.vue'
import BFTSTreeView from './BFTSTreeView.vue'
import { getExperimentResult } from '@/api/ais'
import type { BFTSTreeStructure, BFTSNode, V2TokenUsage } from '@/api/ais'

const props = defineProps<{
  result: Record<string, unknown>
  runId?: string
}>()

const error = ref<string | null>(null)
const experimentResults = ref<Record<string, unknown> | null>(null)
const loadingResults = ref(false)
const selectedBFTSNode = ref<BFTSNode | null>(null)

const templateName = computed(() => (props.result.template as string) ?? 'Unknown')
const status = computed(() => (props.result.status as string) ?? 'pending')
const statusMessage = computed(() => (props.result.message as string) ?? (props.result.status_message as string) ?? null)
const gpuMemory = computed(() => (props.result.gpu_memory as string) ?? null)
const gpuUtil = computed(() => (props.result.gpu_utilization as number) ?? null)
const finalLoss = computed(() => (props.result.final_loss as number) ?? null)
const epochs = computed(() => (props.result.epochs as number) ?? null)

function statusForBadge(s: string): 'done' | 'active' | 'pending' | 'failed' {
  if (s === 'completed') return 'done'
  if (s === 'running') return 'active'
  if (s === 'failed') return 'failed'
  return 'pending'
}

// Parse loss history for chart (metrics.loss_history or metrics.train_losses)
const lossHistory = computed<number[]>(() => {
  const metrics = props.result.metrics as Record<string, unknown> | undefined
  if (!metrics) return []
  const hist = (metrics.loss_history ?? metrics.train_losses ?? metrics.losses) as number[] | undefined
  if (Array.isArray(hist)) return hist.filter(v => typeof v === 'number' && isFinite(v))
  // Try to extract from experimentResults
  if (experimentResults.value) {
    const rm = experimentResults.value.metrics as Record<string, unknown> | undefined
    if (rm) {
      const rh = (rm.loss_history ?? rm.train_losses ?? rm.losses) as number[] | undefined
      if (Array.isArray(rh)) return rh.filter(v => typeof v === 'number' && isFinite(v))
    }
  }
  return []
})

// SVG sparkline path
const chartPath = computed(() => {
  const data = lossHistory.value
  if (data.length < 2) return ''
  const w = 400, h = 100, pad = 4
  const minV = Math.min(...data), maxV = Math.max(...data)
  const range = maxV - minV || 1
  const xStep = (w - pad * 2) / (data.length - 1)
  return data.map((v, i) => {
    const x = pad + i * xStep
    const y = pad + (1 - (v - minV) / range) * (h - pad * 2)
    return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`
  }).join(' ')
})

const chartMinMax = computed(() => {
  const data = lossHistory.value
  if (data.length < 2) return null
  const last = data.at(-1)
  if (last == null) return null
  return {
    min: Math.min(...data).toFixed(4),
    max: Math.max(...data).toFixed(4),
    last: last.toFixed(4),
  }
})

// Experiment design agent outputs (gaps, proposed experiments, readiness)
interface EvidenceGap {
  claim: string
  section: string
  gap_type: string
  severity: string
  description: string
}
interface ProposedExperiment {
  objective: string
  methodology: string
  controls: string[]
  calibration: string
  expected_measurements: Array<{ parameter: string; unit: string; range: string }>
  estimated_duration: string
}

const evidenceGaps = computed<EvidenceGap[]>(() => {
  const gaps = props.result.evidence_gaps ?? props.result.gaps
  return Array.isArray(gaps) ? gaps as EvidenceGap[] : []
})

const proposedExperiments = computed<ProposedExperiment[]>(() => {
  const exps = props.result.proposed_experiments ?? props.result.experiments
  return Array.isArray(exps) ? exps as ProposedExperiment[] : []
})

const readinessScore = computed(() => {
  const score = props.result.readiness_score ?? props.result.readiness
  return typeof score === 'number' ? score : null
})

const hasDesignData = computed(() =>
  evidenceGaps.value.length > 0 || proposedExperiments.value.length > 0 || readinessScore.value !== null,
)

// ── V2 Detection ────────────────────────────────────────────────────

const isV2 = computed(() => {
  if (props.result.is_v2) return true
  const tree = props.result.tree_structure as BFTSTreeStructure | undefined
  return !!(tree && Array.isArray(tree.nodes) && tree.nodes.length > 0)
})

const treeStructure = computed<BFTSTreeStructure | null>(() => {
  const tree = props.result.tree_structure as BFTSTreeStructure | undefined
  if (tree && Array.isArray(tree.nodes) && tree.nodes.length > 0) return tree
  // Try from fetched results
  const fetched = experimentResults.value
  if (fetched) {
    const ft = (fetched as Record<string, unknown>).tree_structure as BFTSTreeStructure | undefined
    if (ft && Array.isArray(ft.nodes) && ft.nodes.length > 0) return ft
  }
  return null
})

const tokenUsage = computed<V2TokenUsage | null>(() => {
  const tu = props.result.token_usage as V2TokenUsage | undefined
  if (tu && tu.total_cost_usd > 0) return tu
  return null
})

const selfReview = computed(() => (props.result.self_review as string) ?? '')
const paperPath = computed(() => (props.result.paper_path as string) ?? null)

function modelCost(data: unknown): string {
  const d = data as Record<string, unknown> | undefined
  const cost = d?.cost_usd
  return typeof cost === 'number' ? cost.toFixed(2) : '0.00'
}

const hasData = computed(() =>
  props.result.template || props.result.status || finalLoss.value !== null || statusMessage.value || hasDesignData.value || isV2.value,
)

function severityColor(sev: string): string {
  if (sev === 'critical') return 'var(--error)'
  if (sev === 'major') return 'var(--warning)'
  return 'var(--text-secondary)'
}

async function handleViewResults() {
  if (!props.runId) return
  loadingResults.value = true
  error.value = null
  try {
    const res = await getExperimentResult(props.runId)
    experimentResults.value = (res.data?.data ?? null) as unknown as Record<string, unknown> | null
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to fetch experiment results'
    console.error('Failed to fetch experiment results:', err)
  } finally {
    loadingResults.value = false
  }
}
</script>

<template>
  <div class="experiment-detail">
    <template v-if="hasData">
      <div class="experiment-detail__top">
        <div class="experiment-detail__info">
          <span class="detail-heading">Template</span>
          <span class="template-name">{{ templateName }}</span>
        </div>
        <StatusBadge :status="statusForBadge(status)" :label="status" />
      </div>

      <div class="experiment-detail__metrics">
        <MetricCard
          v-if="finalLoss !== null"
          label="Final Loss"
          :value="finalLoss.toFixed(4)"
          icon="show_chart"
        />
        <MetricCard
          v-if="epochs !== null"
          label="Epochs"
          :value="epochs"
          icon="repeat"
        />
        <MetricCard
          v-if="gpuMemory"
          label="GPU Memory"
          :value="gpuMemory"
          icon="memory"
        />
        <MetricCard
          v-if="gpuUtil !== null"
          label="GPU Util"
          :value="`${gpuUtil}%`"
          icon="speed"
        />
      </div>

      <p v-if="statusMessage" class="experiment-detail__message">{{ statusMessage }}</p>

      <!-- Loss Chart -->
      <div v-if="lossHistory.length >= 2" class="loss-chart">
        <div class="loss-chart__header">
          <span class="detail-heading">Training Loss</span>
          <div v-if="chartMinMax" class="loss-chart__range font-mono">
            <span>min: {{ chartMinMax.min }}</span>
            <span>last: {{ chartMinMax.last }}</span>
          </div>
        </div>
        <svg class="loss-chart__svg" viewBox="0 0 400 100" preserveAspectRatio="none">
          <rect x="0" y="0" width="400" height="100" fill="none" />
          <path :d="chartPath" fill="none" stroke="var(--os-brand)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <div class="loss-chart__footer font-mono">
          <span>Epoch 1</span>
          <span>{{ lossHistory.length }} epochs</span>
        </div>
      </div>
      <div v-else class="chart-placeholder">
        <span class="material-symbols-outlined" style="font-size: 32px; color: var(--text-tertiary)">show_chart</span>
        <span class="chart-placeholder__text">Loss chart</span>
        <span class="chart-placeholder__sub">Training loss curve will appear when experiment metrics are available</span>
      </div>

      <div v-if="error" class="experiment-detail__error">
        <span class="material-symbols-outlined" style="font-size: 16px; color: var(--error)">error</span>
        <span>{{ error }}</span>
      </div>

      <!-- Experiment Design: Readiness Score -->
      <div v-if="readinessScore !== null" class="readiness-section">
        <h5 class="detail-heading">Publication Readiness</h5>
        <div class="readiness-score" :class="{ 'readiness-score--high': readinessScore >= 7, 'readiness-score--low': readinessScore < 4 }">
          <span class="readiness-score__value font-mono">{{ readinessScore.toFixed(1) }}</span>
          <span class="readiness-score__label">/10</span>
        </div>
      </div>

      <!-- Experiment Design: Evidence Gaps -->
      <div v-if="evidenceGaps.length > 0" class="gaps-section">
        <h5 class="detail-heading">Evidence Gaps ({{ evidenceGaps.length }})</h5>
        <div v-for="(gap, i) in evidenceGaps" :key="i" class="gap-card">
          <div class="gap-card__header">
            <span class="gap-card__severity" :style="{ color: severityColor(gap.severity) }">{{ gap.severity }}</span>
            <span class="gap-card__section font-mono">{{ gap.section }}</span>
          </div>
          <p class="gap-card__claim">{{ gap.claim }}</p>
          <p class="gap-card__desc">{{ gap.description }}</p>
        </div>
      </div>

      <!-- Experiment Design: Proposed Experiments -->
      <div v-if="proposedExperiments.length > 0" class="experiments-section">
        <h5 class="detail-heading">Proposed Experiments ({{ proposedExperiments.length }})</h5>
        <div v-for="(exp, i) in proposedExperiments" :key="i" class="exp-card">
          <h6 class="exp-card__title">{{ exp.objective }}</h6>
          <p class="exp-card__method">{{ exp.methodology }}</p>
          <div v-if="exp.controls?.length" class="exp-card__controls">
            <span class="exp-card__label">Controls:</span>
            <span v-for="ctrl in exp.controls" :key="ctrl" class="exp-card__chip">{{ ctrl }}</span>
          </div>
          <div v-if="exp.expected_measurements?.length" class="exp-card__measurements">
            <span class="exp-card__label">Measurements:</span>
            <div v-for="m in exp.expected_measurements" :key="m.parameter" class="exp-card__measurement font-mono">
              {{ m.parameter }} ({{ m.unit }}): {{ m.range }}
            </div>
          </div>
          <span v-if="exp.estimated_duration" class="exp-card__duration font-mono">{{ exp.estimated_duration }}</span>
        </div>
      </div>

      <!-- V2: BFTS Tree Visualization -->
      <div v-if="isV2" class="v2-badge">
        <span class="material-symbols-outlined" style="font-size: 14px">account_tree</span>
        <span>AI Scientist V2 (BFTS Tree Search)</span>
      </div>

      <BFTSTreeView
        v-if="treeStructure"
        :tree="treeStructure"
        @select-node="(n: BFTSNode) => selectedBFTSNode = n"
      />

      <!-- V2: Selected node detail -->
      <div v-if="selectedBFTSNode" class="bfts-node-detail">
        <h5 class="detail-heading">Node: {{ selectedBFTSNode.node_id }}</h5>
        <div class="bfts-node-detail__row">
          <span class="bfts-node-detail__label">Status:</span>
          <span :style="{ color: selectedBFTSNode.status === 'success' ? 'var(--success)' : selectedBFTSNode.status === 'failed' ? 'var(--error)' : 'var(--text-secondary)' }">
            {{ selectedBFTSNode.status }}
          </span>
        </div>
        <div class="bfts-node-detail__row">
          <span class="bfts-node-detail__label">Depth:</span>
          <span class="font-mono">{{ selectedBFTSNode.depth }}</span>
        </div>
        <div v-if="Object.keys(selectedBFTSNode.metrics).length" class="bfts-node-detail__metrics">
          <span v-for="(val, key) in selectedBFTSNode.metrics" :key="String(key)" class="bfts-node-detail__chip font-mono">
            {{ key }}: {{ typeof val === 'number' ? (val as number).toFixed(4) : val }}
          </span>
        </div>
      </div>

      <!-- V2: Token Usage / Cost -->
      <div v-if="tokenUsage" class="v2-cost-section">
        <h5 class="detail-heading">V2 Cost Breakdown</h5>
        <div class="v2-cost-section__row">
          <MetricCard label="Total Cost" :value="`$${tokenUsage.total_cost_usd.toFixed(2)}`" icon="payments" />
          <MetricCard label="Input Tokens" :value="tokenUsage.total_input_tokens.toLocaleString()" icon="input" />
          <MetricCard label="Output Tokens" :value="tokenUsage.total_output_tokens.toLocaleString()" icon="output" />
        </div>
        <div v-if="Object.keys(tokenUsage.by_model).length" class="v2-cost-section__models">
          <div v-for="(data, model) in tokenUsage.by_model" :key="String(model)" class="v2-cost-section__model font-mono">
            <span class="v2-cost-section__model-name">{{ model }}</span>
            <span>${{ modelCost(data) }}</span>
          </div>
        </div>
      </div>

      <!-- V2: Self Review -->
      <div v-if="selfReview" class="v2-review-section">
        <h5 class="detail-heading">Self Review</h5>
        <pre class="v2-review-section__text font-mono">{{ selfReview }}</pre>
      </div>

      <!-- V2: View Paper button -->
      <div v-if="paperPath" class="v2-paper-section">
        <ActionButton variant="secondary" size="sm" icon="description">
          View Generated Paper
        </ActionButton>
      </div>

      <!-- Fetched Experiment Results (raw) -->
      <div v-if="experimentResults && !isV2" class="experiment-results">
        <h5 class="detail-heading">Experiment Results</h5>
        <pre class="experiment-results__json font-mono">{{ JSON.stringify(experimentResults, null, 2) }}</pre>
      </div>

      <div class="experiment-detail__actions">
        <ActionButton
          v-if="runId"
          variant="secondary"
          size="sm"
          icon="analytics"
          :loading="loadingResults"
          @click="handleViewResults"
        >
          View Results
        </ActionButton>
      </div>
    </template>

    <div v-else class="experiment-detail__empty">
      <span class="material-symbols-outlined" style="font-size: 24px; color: var(--text-tertiary)">science</span>
      <span>No experiment data available yet</span>
    </div>
  </div>
</template>

<style scoped>
.experiment-detail {
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
}

.experiment-detail__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.experiment-detail__info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.template-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.experiment-detail__metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
}

.experiment-detail__message {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

/* ── Loss Chart ── */
.loss-chart {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
}

.loss-chart__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.loss-chart__range {
  display: flex;
  gap: 12px;
  font-size: 10px;
  color: var(--text-tertiary);
}

.loss-chart__svg {
  width: 100%;
  height: 80px;
}

.loss-chart__footer {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: var(--text-tertiary);
}

/* ── Chart Placeholder ── */
.chart-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 32px 16px;
  background: var(--bg-secondary);
  border: 1px dashed var(--border-primary);
  border-radius: var(--radius-md);
}

.chart-placeholder__text {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

.chart-placeholder__sub {
  font-size: 11px;
  color: var(--text-tertiary);
}

.experiment-detail__actions {
  display: flex;
  gap: 8px;
}

.experiment-detail__empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 20px;
  color: var(--text-tertiary);
  font-size: 13px;
  justify-content: center;
}

.experiment-detail__error {
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

/* ── Readiness Score ── */
.readiness-section { display: flex; flex-direction: column; gap: 6px; }
.readiness-score { display: flex; align-items: baseline; gap: 4px; }
.readiness-score__value { font-size: 28px; font-weight: 700; color: var(--text-primary); }
.readiness-score__label { font-size: 14px; color: var(--text-tertiary); }
.readiness-score--high .readiness-score__value { color: var(--success); }
.readiness-score--low .readiness-score__value { color: var(--error); }

/* ── Evidence Gaps ── */
.gaps-section { display: flex; flex-direction: column; gap: 8px; }
.gap-card {
  padding: 10px 12px; background: var(--bg-secondary);
  border: 1px solid var(--border-secondary); border-radius: var(--radius-md);
}
.gap-card__header { display: flex; gap: 8px; align-items: center; margin-bottom: 4px; }
.gap-card__severity { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
.gap-card__section { font-size: 10px; color: var(--text-tertiary); }
.gap-card__claim { margin: 0 0 4px; font-size: 12px; font-weight: 600; color: var(--text-primary); }
.gap-card__desc { margin: 0; font-size: 12px; color: var(--text-secondary); line-height: 1.5; }

/* ── Proposed Experiments ── */
.experiments-section { display: flex; flex-direction: column; gap: 8px; }
.exp-card {
  padding: 12px 14px; background: var(--bg-secondary);
  border: 1px solid var(--border-secondary); border-radius: var(--radius-md);
}
.exp-card__title { margin: 0 0 6px; font-size: 13px; font-weight: 600; color: var(--text-primary); }
.exp-card__method { margin: 0 0 8px; font-size: 12px; color: var(--text-secondary); line-height: 1.5; }
.exp-card__controls { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-bottom: 6px; }
.exp-card__label { font-size: 10px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.04em; }
.exp-card__chip {
  font-size: 11px; padding: 2px 8px; background: var(--bg-tertiary);
  border-radius: var(--radius-pill); color: var(--text-primary);
}
.exp-card__measurements { display: flex; flex-direction: column; gap: 2px; margin-bottom: 6px; }
.exp-card__measurement { font-size: 11px; color: var(--text-secondary); }
.exp-card__duration { font-size: 11px; color: var(--text-tertiary); }

.experiment-results__json {
  margin: 0;
  padding: 12px;
  font-size: 11px;
  line-height: 1.5;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  overflow-x: auto;
  max-height: 300px;
  overflow-y: auto;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── V2 Sections ── */
.v2-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 600;
  color: var(--os-brand);
  background: var(--os-brand-light);
  border: 1px solid var(--os-brand-subtle);
  border-radius: var(--radius-pill);
}

.bfts-node-detail {
  padding: 12px 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bfts-node-detail__row {
  display: flex;
  gap: 8px;
  font-size: 12px;
}

.bfts-node-detail__label {
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 60px;
}

.bfts-node-detail__metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.bfts-node-detail__chip {
  font-size: 10px;
  padding: 2px 8px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-pill);
  color: var(--text-secondary);
}

.v2-cost-section { display: flex; flex-direction: column; gap: 8px; }
.v2-cost-section__row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px;
}
.v2-cost-section__models { display: flex; flex-direction: column; gap: 4px; }
.v2-cost-section__model {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  padding: 4px 10px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
}
.v2-cost-section__model-name { font-weight: 500; }

.v2-review-section { display: flex; flex-direction: column; gap: 6px; }
.v2-review-section__text {
  margin: 0;
  padding: 12px;
  font-size: 11px;
  line-height: 1.5;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-secondary);
}

.v2-paper-section { display: flex; gap: 8px; }
</style>

<script setup lang="ts">
import { computed } from 'vue'
import type { BFTSNode, BFTSTreeStructure } from '@/api/ais'
import MetricCard from '@/components/shared/MetricCard.vue'

const props = defineProps<{
  tree: BFTSTreeStructure
}>()

const emit = defineEmits<{
  (e: 'select-node', node: BFTSNode): void
}>()

// ── Computed ────────────────────────────────────────────────────────

const nodes = computed(() => props.tree.nodes ?? [])
const bestNode = computed<BFTSNode | null>(() => nodes.value.find(n => n.is_best) ?? null)

const successRate = computed(() => {
  if (!props.tree.total_explored) return '0%'
  return `${Math.round((props.tree.successful / props.tree.total_explored) * 100)}%`
})

function statusColor(status: string): string {
  switch (status) {
    case 'success': return 'var(--success)'
    case 'failed': return 'var(--error)'
    case 'debugging': return 'var(--warning)'
    default: return 'var(--text-tertiary)'
  }
}

function statusIcon(status: string): string {
  switch (status) {
    case 'success': return 'check_circle'
    case 'failed': return 'cancel'
    case 'debugging': return 'bug_report'
    default: return 'radio_button_unchecked'
  }
}

// ── SVG Tree Layout ─────────────────────────────────────────────────

interface LayoutNode {
  node: BFTSNode
  x: number
  y: number
}

const nodeSize = 36
const hGap = 60
const vGap = 56

const layout = computed<LayoutNode[]>(() => {
  if (!nodes.value.length) return []

  const byDepth: Map<number, BFTSNode[]> = new Map()
  for (const n of nodes.value) {
    const arr = byDepth.get(n.depth) ?? []
    arr.push(n)
    byDepth.set(n.depth, arr)
  }

  const result: LayoutNode[] = []
  for (const [depth, depthNodes] of byDepth.entries()) {
    const totalWidth = (depthNodes.length - 1) * hGap
    const startX = -totalWidth / 2
    for (let i = 0; i < depthNodes.length; i++) {
      result.push({
        node: depthNodes[i]!,
        x: startX + i * hGap,
        y: depth * vGap,
      })
    }
  }
  return result
})

const edges = computed(() => {
  const posMap = new Map<string, LayoutNode>()
  for (const ln of layout.value) {
    posMap.set(ln.node.node_id, ln)
  }

  const result: Array<{ x1: number; y1: number; x2: number; y2: number }> = []
  for (const ln of layout.value) {
    if (ln.node.parent_id && posMap.has(ln.node.parent_id)) {
      const parent = posMap.get(ln.node.parent_id)!
      result.push({
        x1: parent.x,
        y1: parent.y + nodeSize / 2,
        x2: ln.x,
        y2: ln.y - nodeSize / 2,
      })
    }
  }
  return result
})

const svgWidth = computed(() => {
  if (!layout.value.length) return 200
  const xs = layout.value.map(l => l.x)
  return Math.max(200, Math.max(...xs) - Math.min(...xs) + hGap * 2)
})

const svgHeight = computed(() => {
  if (!layout.value.length) return 100
  return (props.tree.max_depth + 1) * vGap + nodeSize
})

const svgOffsetX = computed(() => svgWidth.value / 2)
const svgOffsetY = computed(() => nodeSize)
</script>

<template>
  <div class="bfts-tree">
    <!-- Summary metrics -->
    <div class="bfts-tree__metrics">
      <MetricCard label="Explored" :value="tree.total_explored" icon="account_tree" />
      <MetricCard label="Successful" :value="tree.successful" icon="check_circle" />
      <MetricCard label="Failed" :value="tree.failed" icon="cancel" />
      <MetricCard label="Max Depth" :value="tree.max_depth" icon="layers" />
      <MetricCard label="Success Rate" :value="successRate" icon="percent" />
    </div>

    <!-- Best node highlight -->
    <div v-if="bestNode" class="bfts-tree__best">
      <span class="material-symbols-outlined" style="color: var(--success); font-size: 18px">star</span>
      <div class="bfts-tree__best-info">
        <span class="bfts-tree__best-label">Best Node</span>
        <span class="bfts-tree__best-id font-mono">{{ bestNode.node_id }}</span>
      </div>
      <div v-if="tree.best_metrics" class="bfts-tree__best-metrics font-mono">
        <span v-for="(val, key) in tree.best_metrics" :key="String(key)" class="bfts-tree__metric-chip">
          {{ key }}: {{ typeof val === 'number' ? (val as number).toFixed(4) : val }}
        </span>
      </div>
    </div>

    <!-- SVG Tree -->
    <div class="bfts-tree__canvas">
      <svg
        :viewBox="`0 0 ${svgWidth} ${svgHeight}`"
        :width="svgWidth"
        :height="svgHeight"
        class="bfts-tree__svg"
      >
        <g :transform="`translate(${svgOffsetX}, ${svgOffsetY})`">
          <!-- Edges -->
          <line
            v-for="(edge, i) in edges"
            :key="`e-${i}`"
            :x1="edge.x1"
            :y1="edge.y1"
            :x2="edge.x2"
            :y2="edge.y2"
            stroke="var(--border-primary)"
            stroke-width="1.5"
          />
          <!-- Nodes -->
          <g
            v-for="ln in layout"
            :key="ln.node.node_id"
            :transform="`translate(${ln.x}, ${ln.y})`"
            class="bfts-tree__node"
            @click="emit('select-node', ln.node)"
          >
            <circle
              :r="nodeSize / 2 - 2"
              :fill="ln.node.is_best ? 'var(--os-brand-light)' : 'var(--bg-elevated)'"
              :stroke="statusColor(ln.node.status)"
              stroke-width="2"
            />
            <text
              class="bfts-tree__node-icon"
              text-anchor="middle"
              dominant-baseline="central"
              :fill="statusColor(ln.node.status)"
              font-size="16"
              font-family="Material Symbols Outlined"
            >{{ statusIcon(ln.node.status) }}</text>
          </g>
        </g>
      </svg>
    </div>

    <!-- Node list (compact) -->
    <div class="bfts-tree__list">
      <div
        v-for="n in nodes"
        :key="n.node_id"
        class="bfts-tree__list-item"
        :class="{ 'bfts-tree__list-item--best': n.is_best }"
        @click="emit('select-node', n)"
      >
        <span class="material-symbols-outlined" :style="{ color: statusColor(n.status), fontSize: '14px' }">
          {{ statusIcon(n.status) }}
        </span>
        <span class="bfts-tree__list-id font-mono">{{ n.node_id }}</span>
        <span class="bfts-tree__list-depth font-mono">d={{ n.depth }}</span>
        <span v-if="n.is_best" class="bfts-tree__list-badge">best</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bfts-tree {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.bfts-tree__metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 8px;
}

/* ── Best node ── */
.bfts-tree__best {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--bg-active);
  border: 1px solid var(--os-brand-subtle);
  border-radius: var(--radius-md);
}

.bfts-tree__best-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.bfts-tree__best-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.bfts-tree__best-id {
  font-size: 12px;
  color: var(--text-primary);
}

.bfts-tree__best-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-left: auto;
}

.bfts-tree__metric-chip {
  font-size: 10px;
  padding: 2px 6px;
  background: var(--bg-secondary);
  border-radius: var(--radius-pill);
  color: var(--text-secondary);
}

/* ── SVG Canvas ── */
.bfts-tree__canvas {
  overflow-x: auto;
  padding: 8px 0;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
}

.bfts-tree__svg {
  display: block;
  margin: 0 auto;
}

.bfts-tree__node {
  cursor: pointer;
}

.bfts-tree__node:hover circle {
  stroke-width: 3;
}

/* ── Node list ── */
.bfts-tree__list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 200px;
  overflow-y: auto;
}

.bfts-tree__list-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 12px;
}

.bfts-tree__list-item:hover {
  background: var(--bg-hover);
}

.bfts-tree__list-item--best {
  background: var(--bg-active);
}

.bfts-tree__list-id {
  color: var(--text-primary);
}

.bfts-tree__list-depth {
  color: var(--text-tertiary);
  font-size: 10px;
}

.bfts-tree__list-badge {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--success);
  padding: 1px 6px;
  background: rgba(34, 197, 94, 0.1);
  border-radius: var(--radius-pill);
  margin-left: auto;
}
</style>

<script setup lang="ts">
/**
 * ClaimGraphView — D3 force-directed claim-evidence graph (Sprint 5.2).
 *
 * Nodes: claims (blue), evidence (green), gaps (red).
 * Links: supports (green), contradicts (red), extends (blue), gap_for (orange).
 */

import { ref, watch, onMounted, nextTick } from 'vue'
import { getClaimGraph } from '@/api/ais'
import type { ClaimGraphData } from '@/api/ais'
import * as d3 from 'd3'

const props = defineProps<{ runId: string }>()

const container = ref<HTMLElement | null>(null)
const graphData = ref<ClaimGraphData | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const selectedNode = ref<Record<string, unknown> | null>(null)

const NODE_COLORS: Record<string, string> = {
  claim: 'var(--os-brand, #6366f1)',
  evidence: 'var(--success, #22c55e)',
  gap: 'var(--danger, #ef4444)',
}

const LINK_COLORS: Record<string, string> = {
  supports: '#22c55e',
  contradicts: '#ef4444',
  extends: '#6366f1',
  gap_for: '#f59e0b',
}

async function fetchGraph() {
  if (!props.runId) return
  loading.value = true
  error.value = null
  try {
    const res = await getClaimGraph(props.runId)
    graphData.value = res.data?.data ?? null
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load claim graph'
  } finally {
    loading.value = false
  }
}

function renderGraph() {
  if (!container.value || !graphData.value) return

  const el = container.value
  el.innerHTML = ''

  const width = el.clientWidth || 600
  const height = 400

  const svg = d3.select(el)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)

  const g = svg.append('g')

  // Zoom
  svg.call(
    d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on('zoom', (event) => g.attr('transform', event.transform)) as any
  )

  const nodes = graphData.value.nodes.map(d => ({ ...d }))
  const links = graphData.value.links.map(d => ({ ...d }))

  const simulation = d3.forceSimulation(nodes as any)
    .force('link', d3.forceLink(links as any).id((d: any) => d.id).distance(80))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(25))

  // Links
  const link = g.selectAll('.link')
    .data(links)
    .join('line')
    .attr('class', 'link')
    .attr('stroke', (d: any) => LINK_COLORS[d.type] || '#666')
    .attr('stroke-width', 1.5)
    .attr('stroke-opacity', 0.6)

  // Nodes
  const node = g.selectAll('.node')
    .data(nodes)
    .join('circle')
    .attr('class', 'node')
    .attr('r', (d: any) => d.type === 'claim' ? 10 : d.type === 'gap' ? 8 : 6)
    .attr('fill', (d: any) => NODE_COLORS[d.type] || '#888')
    .attr('stroke', '#fff')
    .attr('stroke-width', 1.5)
    .style('cursor', 'pointer')
    .on('click', (_event: any, d: any) => {
      selectedNode.value = d
    })
    .call(d3.drag<any, any>()
      .on('start', (event: any, d: any) => {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
      })
      .on('drag', (event: any, d: any) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on('end', (event: any, d: any) => {
        if (!event.active) simulation.alphaTarget(0)
        d.fx = null
        d.fy = null
      })
    )

  // Labels
  g.selectAll('.label')
    .data(nodes)
    .join('text')
    .attr('class', 'label')
    .attr('font-size', 9)
    .attr('fill', 'var(--text-secondary, #888)')
    .attr('text-anchor', 'middle')
    .attr('dy', -14)
    .text((d: any) => d.label.slice(0, 20))

  simulation.on('tick', () => {
    link
      .attr('x1', (d: any) => d.source.x)
      .attr('y1', (d: any) => d.source.y)
      .attr('x2', (d: any) => d.target.x)
      .attr('y2', (d: any) => d.target.y)

    node
      .attr('cx', (d: any) => d.x)
      .attr('cy', (d: any) => d.y)

    g.selectAll('.label')
      .attr('x', (_d: any, i: number) => (nodes[i] as any).x)
      .attr('y', (_d: any, i: number) => (nodes[i] as any).y)
  })
}

watch(() => props.runId, fetchGraph, { immediate: true })
watch(graphData, () => { nextTick(() => renderGraph()) })
onMounted(() => { if (graphData.value) nextTick(() => renderGraph()) })
</script>

<template>
  <div class="claim-graph">
    <div v-if="loading" class="claim-graph__loading">
      <span class="material-symbols-outlined claim-graph__spinner">progress_activity</span>
      Loading claim graph...
    </div>

    <div v-else-if="error" class="claim-graph__error">
      <span class="material-symbols-outlined">error_outline</span>
      {{ error }}
    </div>

    <template v-else-if="graphData">
      <div class="claim-graph__stats">
        <span class="claim-graph__stat">
          <span class="claim-graph__dot" style="background: var(--os-brand)"></span>
          {{ graphData.stats.claims }} claims
        </span>
        <span class="claim-graph__stat">
          <span class="claim-graph__dot" style="background: var(--success, #22c55e)"></span>
          {{ graphData.stats.evidence }} evidence
        </span>
        <span class="claim-graph__stat">
          <span class="claim-graph__dot" style="background: var(--danger, #ef4444)"></span>
          {{ graphData.stats.gaps }} gaps
        </span>
        <span class="claim-graph__stat claim-graph__stat--muted">
          {{ graphData.stats.links }} links
        </span>
      </div>

      <div ref="container" class="claim-graph__canvas"></div>

      <div v-if="selectedNode" class="claim-graph__detail">
        <div class="claim-graph__detail-header">
          <span class="claim-graph__detail-type" :data-type="selectedNode.type">
            {{ selectedNode.type }}
          </span>
          <button class="claim-graph__close" @click="selectedNode = null">
            <span class="material-symbols-outlined" style="font-size: 14px">close</span>
          </button>
        </div>
        <p class="claim-graph__detail-text">{{ selectedNode.full_text }}</p>
      </div>
    </template>

    <div v-else class="claim-graph__empty">
      No knowledge artifact found. Build one first.
    </div>
  </div>
</template>

<style scoped>
.claim-graph { display: flex; flex-direction: column; gap: 12px; }
.claim-graph__loading, .claim-graph__error, .claim-graph__empty {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 24px; font-size: 12px; color: var(--text-tertiary);
}
.claim-graph__error { color: var(--danger, #ef4444); }
.claim-graph__spinner { font-size: 18px; animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.claim-graph__stats {
  display: flex; gap: 12px; flex-wrap: wrap; font-size: 11px; color: var(--text-secondary);
}
.claim-graph__stat { display: flex; align-items: center; gap: 4px; }
.claim-graph__stat--muted { color: var(--text-tertiary); }
.claim-graph__dot { width: 8px; height: 8px; border-radius: 50%; }
.claim-graph__canvas {
  width: 100%; min-height: 400px; background: var(--bg-secondary);
  border: 1px solid var(--border-secondary); border-radius: var(--radius-md);
}

.claim-graph__detail {
  padding: 10px 12px; background: var(--bg-secondary);
  border: 1px solid var(--border-secondary); border-radius: var(--radius-md);
}
.claim-graph__detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.claim-graph__detail-type {
  font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
  padding: 2px 6px; border-radius: var(--radius-pill, 999px);
}
.claim-graph__detail-type[data-type="claim"] { color: var(--os-brand); background: color-mix(in srgb, var(--os-brand) 12%, transparent); }
.claim-graph__detail-type[data-type="evidence"] { color: var(--success, #22c55e); background: color-mix(in srgb, var(--success, #22c55e) 12%, transparent); }
.claim-graph__detail-type[data-type="gap"] { color: var(--danger, #ef4444); background: color-mix(in srgb, var(--danger, #ef4444) 12%, transparent); }
.claim-graph__detail-text { font-size: 12px; line-height: 1.5; color: var(--text-primary); margin: 0; }
.claim-graph__close { background: none; border: none; cursor: pointer; color: var(--text-tertiary); padding: 2px; }
</style>

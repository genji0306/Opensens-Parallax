<template>
  <div class="knowledge-graph" ref="container">
    <svg ref="graphSvg" class="graph-svg"></svg>

    <!-- Graph legend -->
    <div class="graph-legend">
      <div class="legend-title">Node Types</div>
      <div class="legend-items">
        <div v-for="nt in visibleNodeTypes" :key="nt.type" class="legend-item" @click="toggleType(nt.type)">
          <span class="legend-shape" :style="{ background: nt.color, opacity: hiddenTypes.has(nt.type) ? 0.2 : 1 }"></span>
          <span class="legend-label" :class="{ dimmed: hiddenTypes.has(nt.type) }">{{ nt.label }} ({{ nt.count }})</span>
        </div>
      </div>
    </div>

    <!-- Zoom indicator -->
    <div class="zoom-level">{{ zoomPercent }}%</div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  graphSnapshot: { type: Object, default: null },
  selectedRound: { type: Number, default: 0 },
})

const emit = defineEmits(['node-selected'])

const container = ref(null)
const graphSvg = ref(null)
const currentZoom = ref(1)
const hiddenTypes = ref(new Set())

let simulation = null
let resizeObserver = null
let themeObserver = null

const zoomPercent = computed(() => Math.round(currentZoom.value * 100))

// Node type definitions
const NODE_TYPES = {
  paper:          { color: 'var(--mf-paper)',         label: 'Paper',     shape: 'circle' },
  author:         { color: 'var(--mf-author)',        label: 'Author',    shape: 'diamond' },
  institution:    { color: 'var(--mf-institution)',   label: 'Institution', shape: 'circle' },
  method:         { color: 'var(--mf-method)',        label: 'Method',    shape: 'triangle' },
  claim:          { color: 'var(--mf-claim)',         label: 'Claim',     shape: 'square' },
  dataset:        { color: 'var(--mf-dataset)',       label: 'Dataset',   shape: 'square' },
  experiment:     { color: 'var(--mf-experiment)',    label: 'Experiment', shape: 'star' },
  critique:       { color: 'var(--mf-critique)',      label: 'Critique',  shape: 'cross' },
  open_question:  { color: 'var(--mf-open-question)', label: 'Question', shape: 'star' },
  agent_persona:  { color: 'var(--mf-agent)',         label: 'Agent',     shape: 'circle' },
  evidence_block: { color: 'var(--mf-evidence)',      label: 'Evidence',  shape: 'square' },
  option:         { color: 'var(--mf-option)',        label: 'Option',    shape: 'triangle' },
}

// Edge style definitions
const EDGE_STYLES = {
  cites:           { stroke: 'var(--mf-edge-default)',    width: 1,   dash: null },
  supports:        { stroke: 'var(--mf-edge-supports)',   width: 2,   dash: null },
  contradicts:     { stroke: 'var(--mf-edge-contradicts)', width: 2,  dash: '6,3' },
  extends:         { stroke: 'var(--mf-edge-extends)',    width: 1.5, dash: null },
  critiques:       { stroke: 'var(--mf-edge-critiques)',  width: 1.5, dash: '3,2' },
  depends_on:      { stroke: 'var(--mf-edge-default)',    width: 1,   dash: null },
  uses_dataset:    { stroke: 'var(--mf-edge-default)',    width: 1,   dash: '2,2' },
  shares_method:   { stroke: 'var(--mf-edge-default)',    width: 1,   dash: '6,3' },
  agrees_with:     { stroke: 'var(--mf-edge-supports)',   width: 1,   dash: null },
  disputes:        { stroke: 'var(--mf-edge-contradicts)', width: 1,  dash: '6,3' },
  proposes_option: { stroke: 'var(--mf-edge-extends)',    width: 2,   dash: null },
  shifts_toward:   { stroke: 'var(--mf-edge-extends)',    width: 2,   dash: null },
  influenced_by:   { stroke: 'var(--mf-edge-default)',    width: 1,   dash: '4,4' },
}

const visibleNodeTypes = computed(() => {
  if (!props.graphSnapshot) return []
  const nodes = props.graphSnapshot.nodes || []
  const counts = {}
  for (const n of nodes) {
    const t = n.node_type || n.type || 'unknown'
    counts[t] = (counts[t] || 0) + 1
  }
  return Object.entries(counts)
    .map(([type, count]) => ({
      type,
      count,
      color: NODE_TYPES[type]?.color || '#999',
      label: NODE_TYPES[type]?.label || type,
    }))
    .sort((a, b) => b.count - a.count)
})

function toggleType(type) {
  const s = new Set(hiddenTypes.value)
  if (s.has(type)) s.delete(type)
  else s.add(type)
  hiddenTypes.value = s
  applyVisibility()
}

function getCSSVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function getNodeColor(node) {
  const t = node.node_type || node.type
  const def = NODE_TYPES[t]
  if (!def) return '#999'
  // Resolve CSS variable
  return getCSSVar(def.color.replace('var(', '').replace(')', '')) || def.color
}

function getNodeRadius(node) {
  const t = node.node_type || node.type
  const base = {
    option: 14, agent_persona: 12, claim: 10, method: 9,
    paper: 7, experiment: 8, dataset: 7, critique: 7,
    author: 6, institution: 6, evidence_block: 6, open_question: 8,
  }
  const r = base[t] || 6
  const w = node.weight || 1
  return r * Math.min(Math.sqrt(w), 2)
}

function getNodeShape(node) {
  const t = node.node_type || node.type
  return NODE_TYPES[t]?.shape || 'circle'
}

function getEdgeStyle(edge) {
  const rel = edge.relation || edge.type || 'cites'
  return EDGE_STYLES[rel] || EDGE_STYLES.cites
}

function renderGraph() {
  if (!graphSvg.value || !container.value || !props.graphSnapshot) return

  const width = container.value.clientWidth
  const height = container.value.clientHeight
  if (width === 0 || height === 0) return

  const svg = d3.select(graphSvg.value)
  svg.selectAll('*').remove()
  svg.attr('width', width).attr('height', height)

  const rawNodes = props.graphSnapshot.nodes || []
  const rawLinks = props.graphSnapshot.links || props.graphSnapshot.edges || []

  if (rawNodes.length === 0) return

  // Copy data for D3 mutation
  const nodes = rawNodes.map(n => ({ ...n, id: n.node_id || n.id }))
  const nodeIds = new Set(nodes.map(n => n.id))

  const links = rawLinks
    .map(e => ({
      ...e,
      source: e.source_id || (typeof e.source === 'object' ? e.source.id : e.source),
      target: e.target_id || (typeof e.target === 'object' ? e.target.id : e.target),
      relation: e.relation || e.type,
    }))
    .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))

  // Arrow markers
  const defs = svg.append('defs')
  defs.append('marker')
    .attr('id', 'arrowhead')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 20)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', getCSSVar('--text-tertiary') || '#999')

  // Zoom group
  const g = svg.append('g')
  const zoom = d3.zoom()
    .scaleExtent([0.1, 8])
    .on('zoom', (event) => {
      g.attr('transform', event.transform)
      currentZoom.value = event.transform.k
    })
  svg.call(zoom)

  // Force simulation
  if (simulation) simulation.stop()
  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(d => {
      const rel = d.relation
      if (rel === 'supports' || rel === 'contradicts') return 80
      if (rel === 'proposes_option' || rel === 'shifts_toward') return 60
      return 100
    }))
    .force('charge', d3.forceManyBody().strength(d => {
      const t = d.node_type || d.type
      if (t === 'option' || t === 'agent_persona') return -200
      if (t === 'claim') return -120
      return -60
    }))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(d => getNodeRadius(d) + 3))
    .force('x', d3.forceX(width / 2).strength(0.03))
    .force('y', d3.forceY(height / 2).strength(0.03))

  // Render edges
  const link = g.append('g').attr('class', 'edges')
    .selectAll('line')
    .data(links)
    .join('line')
    .each(function (d) {
      const style = getEdgeStyle(d)
      const el = d3.select(this)
      el.attr('stroke', style.stroke)
        .attr('stroke-width', style.width)
        .attr('stroke-opacity', 0.6)
      if (style.dash) el.attr('stroke-dasharray', style.dash)
      if (d.relation === 'proposes_option' || d.relation === 'depends_on') {
        el.attr('marker-end', 'url(#arrowhead)')
      }
    })

  // Render nodes
  const node = g.append('g').attr('class', 'nodes')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .call(d3.drag()
      .on('start', dragStarted)
      .on('drag', dragged)
      .on('end', dragEnded))
    .on('click', (event, d) => {
      event.stopPropagation()
      emit('node-selected', d)
    })

  // Node shapes
  node.each(function (d) {
    const el = d3.select(this)
    const r = getNodeRadius(d)
    const color = getNodeColor(d)
    const shape = getNodeShape(d)

    if (shape === 'square') {
      el.append('rect')
        .attr('x', -r).attr('y', -r)
        .attr('width', r * 2).attr('height', r * 2)
        .attr('rx', 2)
        .attr('fill', color)
        .attr('stroke', getCSSVar('--bg-primary') || '#fff')
        .attr('stroke-width', 1.5)
    } else if (shape === 'diamond') {
      el.append('path')
        .attr('d', `M0,${-r} L${r},0 L0,${r} L${-r},0 Z`)
        .attr('fill', color)
        .attr('stroke', getCSSVar('--bg-primary') || '#fff')
        .attr('stroke-width', 1.5)
    } else if (shape === 'triangle') {
      const h = r * 1.2
      el.append('path')
        .attr('d', `M0,${-h} L${h},${h * 0.6} L${-h},${h * 0.6} Z`)
        .attr('fill', color)
        .attr('stroke', getCSSVar('--bg-primary') || '#fff')
        .attr('stroke-width', 1.5)
    } else if (shape === 'star') {
      const points = 5
      const outerR = r
      const innerR = r * 0.5
      let path = ''
      for (let i = 0; i < points * 2; i++) {
        const radius = i % 2 === 0 ? outerR : innerR
        const angle = (i * Math.PI) / points - Math.PI / 2
        const x = Math.cos(angle) * radius
        const y = Math.sin(angle) * radius
        path += (i === 0 ? 'M' : 'L') + `${x},${y}`
      }
      path += 'Z'
      el.append('path')
        .attr('d', path)
        .attr('fill', color)
        .attr('stroke', getCSSVar('--bg-primary') || '#fff')
        .attr('stroke-width', 1.5)
    } else if (shape === 'cross') {
      const w = r * 0.35
      el.append('path')
        .attr('d', `M${-w},${-r} L${w},${-r} L${w},${-w} L${r},${-w} L${r},${w} L${w},${w} L${w},${r} L${-w},${r} L${-w},${w} L${-r},${w} L${-r},${-w} L${-w},${-w} Z`)
        .attr('fill', color)
        .attr('stroke', getCSSVar('--bg-primary') || '#fff')
        .attr('stroke-width', 1)
    } else {
      // Default circle
      el.append('circle')
        .attr('r', r)
        .attr('fill', color)
        .attr('stroke', getCSSVar('--bg-primary') || '#fff')
        .attr('stroke-width', 1.5)
    }
  })

  // Labels
  node.append('text')
    .text(d => {
      const label = d.label || d.id
      return label.length > 20 ? label.substring(0, 18) + '..' : label
    })
    .attr('dx', d => getNodeRadius(d) + 4)
    .attr('dy', '0.35em')
    .attr('font-size', d => {
      const t = d.node_type || d.type
      return (t === 'option' || t === 'agent_persona') ? '11px' : '9px'
    })
    .attr('fill', getCSSVar('--text-secondary') || '#666')
    .attr('font-family', getCSSVar('--font-sans') || 'sans-serif')
    .attr('pointer-events', 'none')

  // Tick
  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y)

    node.attr('transform', d => `translate(${d.x},${d.y})`)
  })

  // Click background to deselect
  svg.on('click', () => emit('node-selected', null))

  applyVisibility()
}

function applyVisibility() {
  if (!graphSvg.value) return
  const svg = d3.select(graphSvg.value)

  svg.selectAll('.nodes g').each(function () {
    const el = d3.select(this)
    const d = el.datum()
    const t = d.node_type || d.type
    const hidden = hiddenTypes.value.has(t)
    el.attr('opacity', hidden ? 0.08 : 1)
      .style('pointer-events', hidden ? 'none' : 'all')
  })

  svg.selectAll('.edges line').each(function () {
    const el = d3.select(this)
    const d = el.datum()
    const srcType = typeof d.source === 'object' ? (d.source.node_type || d.source.type) : null
    const tgtType = typeof d.target === 'object' ? (d.target.node_type || d.target.type) : null
    const hidden = (srcType && hiddenTypes.value.has(srcType)) || (tgtType && hiddenTypes.value.has(tgtType))
    el.attr('opacity', hidden ? 0.05 : 0.6)
  })
}

function dragStarted(event, d) {
  if (!event.active) simulation.alphaTarget(0.3).restart()
  d.fx = d.x
  d.fy = d.y
}

function dragged(event, d) {
  d.fx = event.x
  d.fy = event.y
}

function dragEnded(event, d) {
  if (!event.active) simulation.alphaTarget(0)
  d.fx = null
  d.fy = null
}

// Watch for data changes
watch(() => props.graphSnapshot, () => {
  nextTick(renderGraph)
}, { deep: false })

onMounted(() => {
  nextTick(renderGraph)

  resizeObserver = new ResizeObserver(() => nextTick(renderGraph))
  if (container.value) resizeObserver.observe(container.value)

  themeObserver = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.attributeName === 'data-theme') {
        nextTick(renderGraph)
        break
      }
    }
  })
  themeObserver.observe(document.documentElement, { attributes: true })
})

onUnmounted(() => {
  if (simulation) simulation.stop()
  if (resizeObserver) resizeObserver.disconnect()
  if (themeObserver) themeObserver.disconnect()
})
</script>

<style scoped>
.knowledge-graph {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  background: var(--bg-primary);
}

.graph-svg {
  width: 100%;
  height: 100%;
  cursor: grab;
}
.graph-svg:active { cursor: grabbing; }

.graph-legend {
  position: absolute;
  top: 8px;
  left: 8px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  padding: 8px 10px;
  box-shadow: var(--shadow-sm);
  max-width: 180px;
}

.legend-title {
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

.legend-items {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  padding: 1px 0;
}

.legend-shape {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
  transition: opacity var(--transition-fast);
}

.legend-label {
  font-size: 10px;
  color: var(--text-secondary);
  transition: opacity var(--transition-fast);
}
.legend-label.dimmed { opacity: 0.4; }

.zoom-level {
  position: absolute;
  bottom: 8px;
  right: 8px;
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--text-tertiary);
  background: var(--bg-elevated);
  border: 1px solid var(--border-secondary);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}
</style>

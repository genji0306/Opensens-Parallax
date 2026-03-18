<template>
  <div class="topic-graph-panel">
    <div class="panel-header">
      <span class="panel-title">Research Topic Map</span>
      <div class="header-tools">
        <button class="tool-btn" @click="handleRefresh" :disabled="loading" title="Refresh map">
          <span class="icon-refresh" :class="{ 'spinning': loading }">&#8635;</span>
          <span class="btn-text">Refresh</span>
        </button>
        <button class="tool-btn" :class="{ active: showLabels }" @click="showLabels = !showLabels" title="Toggle labels">
          <span>Aa</span>
        </button>
        <button class="tool-btn" :class="{ active: visualStyle === 'neural' }" @click="toggleVisualStyle" title="Neural tissue view">
          <span class="icon-neural">&#129504;</span>
        </button>
        <button class="tool-btn" @click="exportSVG" title="Export SVG">
          <span class="btn-text">SVG</span>
        </button>
        <button class="tool-btn" @click="exportPNG" title="Export PNG">
          <span class="btn-text">PNG</span>
        </button>
        <button class="tool-btn" @click="$emit('toggle-maximize')" title="Maximize/Restore">
          <span class="icon-maximize">&#9974;</span>
        </button>
      </div>
    </div>

    <div class="graph-container" :class="{ 'neural-mode': visualStyle === 'neural' }" ref="graphContainer">
      <!-- Empty state -->
      <div v-if="!graphData || (graphData.nodes && graphData.nodes.length === 0)" class="empty-state">
        <div class="empty-icon">&#9881;</div>
        <p>No research topics mapped yet.</p>
        <p class="empty-hint">Ingest papers first, then build the topic map.</p>
      </div>

      <!-- D3 SVG canvas -->
      <svg v-show="graphData && graphData.nodes && graphData.nodes.length > 0" ref="graphSvg" class="graph-svg"></svg>

      <!-- Zoom level indicator -->
      <div v-if="graphData && graphData.nodes && graphData.nodes.length > 0" class="zoom-indicator">
        <span class="zoom-level-label">{{ zoomLevelName }}</span>
        <span class="zoom-level-value">{{ currentZoomLevel.toFixed(1) }}x</span>
      </div>

      <!-- Node detail panel -->
      <div v-if="selectedNode" class="detail-panel">
        <div class="detail-panel-header">
          <span class="detail-title">{{ selectedNode.type === 'topic' ? 'Topic' : 'Paper' }}</span>
          <span class="detail-type-badge" :style="{ background: getNodeColor(selectedNode) }">
            {{ selectedNode.type === 'topic' ? `L${selectedNode.level}` : selectedNode.doi }}
          </span>
          <button class="detail-close" @click="selectedNode = null">&times;</button>
        </div>
        <div class="detail-content">
          <div class="detail-row">
            <span class="detail-label">Name:</span>
            <span class="detail-value">{{ selectedNode.label }}</span>
          </div>
          <div v-if="selectedNode.type === 'paper'" class="detail-row">
            <span class="detail-label">DOI:</span>
            <span class="detail-value uuid-text">{{ selectedNode.doi }}</span>
          </div>
          <div v-if="selectedNode.type === 'paper'" class="detail-row">
            <span class="detail-label">Date:</span>
            <span class="detail-value">{{ selectedNode.date }}</span>
          </div>
          <div v-if="selectedNode.type === 'paper'" class="detail-row">
            <span class="detail-label">Citations:</span>
            <span class="detail-value">{{ selectedNode.citation_count || 0 }}</span>
          </div>
          <div v-if="selectedNode.type === 'topic'" class="detail-row">
            <span class="detail-label">Papers:</span>
            <span class="detail-value">{{ selectedNode.paper_count || 0 }}</span>
          </div>
        </div>
      </div>

      <!-- Interactive Legend -->
      <div v-if="graphData && graphData.nodes && graphData.nodes.length > 0" class="graph-legend">
        <div class="legend-header">
          <select v-model="colorMode" class="color-mode-select" title="Color mode">
            <option value="topic">By Topic Level</option>
            <option value="year">By Year</option>
            <option value="citations">By Citations</option>
            <option value="source">By Source</option>
          </select>
        </div>
        <div class="legend-items">
          <div
            v-for="item in legendItems"
            :key="item.key"
            class="legend-item"
            :class="{ 'legend-item-hidden': hiddenCategories.has(item.key) }"
            @click="toggleCategory(item.key)"
            :title="hiddenCategories.has(item.key) ? 'Click to show' : 'Click to hide'"
          >
            <span class="legend-dot" :style="{ background: item.color }"></span>
            <span class="legend-label">{{ item.label }}</span>
            <span class="legend-count">({{ item.count }})</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as d3 from 'd3'
import {
  createNeuralDefs,
  createNeuralBackground,
  computeBezierPath,
  renderNeuralEdges,
  updateNeuralEdgePaths,
  renderNeuralNode,
  renderNeuralGaps
} from './neural-graph-helpers'

const props = defineProps({
  graphData: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  gaps: { type: Array, default: () => [] }
})

const emit = defineEmits(['refresh', 'toggle-maximize', 'node-click'])

const graphContainer = ref(null)
const graphSvg = ref(null)
const selectedNode = ref(null)
const showLabels = ref(true)
const currentZoomLevel = ref(1)
const colorMode = ref('topic')
const hiddenCategories = reactive(new Set())
const visualStyle = ref('classic') // 'classic' | 'neural'

let simulation = null
let resizeObserver = null
let themeObserver = null
let currentZoomTransform = null
let neuralEdgePaths = null // d3 selection for neural edge tick updates

function toggleVisualStyle() {
  visualStyle.value = visualStyle.value === 'classic' ? 'neural' : 'classic'
}

// ─── Zoom level name ──────────────────────────────────────────────────────────
const zoomLevelName = computed(() => {
  const k = currentZoomLevel.value
  const isNeural = visualStyle.value === 'neural'
  if (k < 0.5) return isNeural ? 'Brain Regions' : 'Domains'
  if (k < 0.8) return isNeural ? 'Neuron Soma' : 'Subfields'
  if (k < 1.5) return isNeural ? 'Synaptic Terminals' : 'Threads'
  return isNeural ? 'Vesicles' : 'Papers'
})

// ─── CSS var helper ───────────────────────────────────────────────────────────
function getCSSVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

// ─── Color mode scales ────────────────────────────────────────────────────────
function getYearScale(nodes) {
  const currentYear = new Date().getFullYear()
  return d3.scaleSequential(d3.interpolateRdYlBu).domain([currentYear, currentYear - 5])
}

function getCitationScale(nodes) {
  const maxCitations = d3.max(nodes, d => d.citation_count || 0) || 1
  return d3.scaleSequential(d3.interpolateBlues).domain([0, maxCitations])
}

const SOURCE_COLORS = {
  biorxiv: '#E64A19',
  arxiv: '#1565C0',
  semantic_scholar: '#2E7D32',
  openalex: '#6A1B9A',
  pubmed: '#F9A825'
}

function getNodeColor(node) {
  if (colorMode.value === 'topic') {
    if (node.type === 'topic') {
      if (node.level === 1) return getCSSVar('--graph-domain')
      if (node.level === 2) return getCSSVar('--graph-subfield')
      return getCSSVar('--graph-thread')
    }
    return getCSSVar('--graph-paper')
  }

  if (colorMode.value === 'year') {
    const scale = getYearScale()
    const year = node.date ? parseInt(node.date.substring(0, 4)) : new Date().getFullYear()
    return scale(year)
  }

  if (colorMode.value === 'citations') {
    const allNodes = (props.graphData && props.graphData.nodes) || []
    const scale = getCitationScale(allNodes)
    return scale(node.citation_count || 0)
  }

  if (colorMode.value === 'source') {
    const src = (node.source || '').toLowerCase().replace(/[\s-]/g, '_')
    return SOURCE_COLORS[src] || '#888888'
  }

  // Fallback to topic mode
  if (node.type === 'topic') {
    if (node.level === 1) return getCSSVar('--graph-domain')
    if (node.level === 2) return getCSSVar('--graph-subfield')
    return getCSSVar('--graph-thread')
  }
  return getCSSVar('--graph-paper')
}

// ─── Legend items (computed) ──────────────────────────────────────────────────
const legendItems = computed(() => {
  if (!props.graphData || !props.graphData.nodes) return []
  const nodes = props.graphData.nodes

  if (colorMode.value === 'topic') {
    const domainCount = nodes.filter(n => n.type === 'topic' && n.level === 1).length
    const subfieldCount = nodes.filter(n => n.type === 'topic' && n.level === 2).length
    const threadCount = nodes.filter(n => n.type === 'topic' && n.level === 3).length
    const paperCount = nodes.filter(n => n.type === 'paper').length
    const isNeural = visualStyle.value === 'neural'
    return [
      { key: 'domain', label: isNeural ? 'Brain Region' : 'Domain', color: getCSSVar('--graph-domain'), count: domainCount },
      { key: 'subfield', label: isNeural ? 'Neuron Soma' : 'Subfield', color: getCSSVar('--graph-subfield'), count: subfieldCount },
      { key: 'thread', label: isNeural ? 'Synapse' : 'Thread', color: getCSSVar('--graph-thread'), count: threadCount },
      { key: 'paper', label: isNeural ? 'Vesicle' : 'Paper', color: getCSSVar('--graph-paper'), count: paperCount }
    ]
  }

  if (colorMode.value === 'year') {
    const currentYear = new Date().getFullYear()
    const scale = getYearScale()
    const years = new Map()
    for (const n of nodes) {
      const yr = n.date ? parseInt(n.date.substring(0, 4)) : currentYear
      years.set(yr, (years.get(yr) || 0) + 1)
    }
    const sortedYears = [...years.entries()].sort((a, b) => b[0] - a[0])
    return sortedYears.map(([yr, count]) => ({
      key: `year_${yr}`,
      label: String(yr),
      color: scale(yr),
      count
    }))
  }

  if (colorMode.value === 'citations') {
    const maxCitations = d3.max(nodes, d => d.citation_count || 0) || 1
    const scale = getCitationScale(nodes)
    const brackets = [
      { min: 0, max: 0, label: '0' },
      { min: 1, max: 5, label: '1-5' },
      { min: 6, max: 20, label: '6-20' },
      { min: 21, max: 100, label: '21-100' },
      { min: 101, max: Infinity, label: '100+' }
    ]
    return brackets.map(b => {
      const count = nodes.filter(n => {
        const c = n.citation_count || 0
        return c >= b.min && c <= b.max
      }).length
      const midVal = b.max === Infinity ? maxCitations : (b.min + b.max) / 2
      return {
        key: `cite_${b.label}`,
        label: b.label + ' citations',
        color: scale(midVal),
        count
      }
    }).filter(item => item.count > 0)
  }

  if (colorMode.value === 'source') {
    const sources = new Map()
    for (const n of nodes) {
      const src = (n.source || 'unknown').toLowerCase().replace(/[\s-]/g, '_')
      sources.set(src, (sources.get(src) || 0) + 1)
    }
    return [...sources.entries()].map(([src, count]) => ({
      key: `source_${src}`,
      label: src.replace(/_/g, ' '),
      color: SOURCE_COLORS[src] || '#888888',
      count
    }))
  }

  return []
})

function toggleCategory(key) {
  if (hiddenCategories.has(key)) {
    hiddenCategories.delete(key)
  } else {
    hiddenCategories.add(key)
  }
  applyLegendFilter()
}

// ─── Node radius ─────────────────────────────────────────────────────────────
const LEVEL_RADIUS = { 1: 18, 2: 12, 3: 8 }

function getNodeRadius(node) {
  if (node.type === 'topic') {
    const base = LEVEL_RADIUS[node.level] || 8
    return base + Math.min((node.paper_count || 0) * 0.5, 10)
  }
  return 4 + Math.min(Math.sqrt(node.citation_count || 0), 8)
}

// ─── Determine which category a node belongs to for legend filtering ─────────
function getNodeCategory(node) {
  if (colorMode.value === 'topic') {
    if (node.type === 'topic') {
      if (node.level === 1) return 'domain'
      if (node.level === 2) return 'subfield'
      return 'thread'
    }
    return 'paper'
  }
  if (colorMode.value === 'year') {
    const yr = node.date ? parseInt(node.date.substring(0, 4)) : new Date().getFullYear()
    return `year_${yr}`
  }
  if (colorMode.value === 'citations') {
    const c = node.citation_count || 0
    if (c === 0) return 'cite_0'
    if (c <= 5) return 'cite_1-5'
    if (c <= 20) return 'cite_6-20'
    if (c <= 100) return 'cite_21-100'
    return 'cite_100+'
  }
  if (colorMode.value === 'source') {
    const src = (node.source || 'unknown').toLowerCase().replace(/[\s-]/g, '_')
    return `source_${src}`
  }
  return ''
}

// ─── Semantic zoom: determine node visibility by type and zoom level ─────────
function isNodeVisibleAtZoom(node, k) {
  // Domain nodes (level 1 topics) always visible
  if (node.type === 'topic' && node.level === 1) return true
  // Subfield nodes (level 2) visible at k >= 0.5
  if (node.type === 'topic' && node.level === 2) return k >= 0.5
  // Thread nodes (level 3) visible at k >= 0.8
  if (node.type === 'topic' && node.level === 3) return k >= 0.8
  // Paper nodes visible at k >= 1.5
  if (node.type === 'paper') return k >= 1.5
  return true
}

function isEdgeVisibleAtZoom(edge, k) {
  // hierarchy edges always visible
  if (edge.type === 'hierarchy') return true
  // belongs_to edges visible at k >= 0.8
  if (edge.type === 'belongs_to') return k >= 0.8
  // cites edges visible at k >= 1.5
  if (edge.type === 'cites') return k >= 1.5
  return k >= 0.8
}

function applySemanticZoom() {
  if (!graphSvg.value) return
  const svg = d3.select(graphSvg.value)
  const k = currentZoomLevel.value

  // Update node visibility
  svg.selectAll('.nodes g').each(function() {
    const el = d3.select(this)
    const d = el.datum()
    if (!d) return
    const visible = isNodeVisibleAtZoom(d, k)
    const hidden = hiddenCategories.has(getNodeCategory(d))
    el.attr('opacity', visible && !hidden ? 1 : 0)
      .style('pointer-events', visible && !hidden ? 'all' : 'none')
  })

  // Update edge visibility (classic uses .links line, neural uses .neural-edge)
  const edgeSelector = visualStyle.value === 'neural' ? '.neural-edge' : '.links line'
  svg.selectAll(edgeSelector).each(function() {
    const el = d3.select(this)
    const d = el.datum()
    if (!d) return
    const visible = isEdgeVisibleAtZoom(d, k)
    el.attr('opacity', visible ? null : 0)
      .style('pointer-events', visible ? 'all' : 'none')
  })

  // Scale labels inversely with zoom (bigger text when zoomed out)
  const labelScale = Math.max(0.6, Math.min(2.0, 1.0 / k))
  svg.selectAll('.nodes text')
    .attr('font-size', function() {
      const d = d3.select(this.parentNode).datum()
      if (!d) return '10px'
      const base = d.type === 'topic' && d.level === 1 ? 12 : 10
      return (base * labelScale) + 'px'
    })
}

// ─── Apply legend filter (toggle hidden categories) ──────────────────────────
function applyLegendFilter() {
  if (!graphSvg.value) return
  const svg = d3.select(graphSvg.value)
  const k = currentZoomLevel.value

  svg.selectAll('.nodes g').each(function() {
    const el = d3.select(this)
    const d = el.datum()
    if (!d) return
    const visibleByZoom = isNodeVisibleAtZoom(d, k)
    const hidden = hiddenCategories.has(getNodeCategory(d))
    el.attr('opacity', visibleByZoom && !hidden ? 1 : hidden ? 0.05 : 0)
      .style('pointer-events', visibleByZoom && !hidden ? 'all' : 'none')
  })
}

// ─── Refresh / events ─────────────────────────────────────────────────────────
function handleRefresh() {
  emit('refresh')
}

// ─── Export functions ─────────────────────────────────────────────────────────
function exportSVG() {
  if (!graphSvg.value) return
  const svgEl = graphSvg.value
  const serializer = new XMLSerializer()
  const svgString = serializer.serializeToString(svgEl)
  const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'topic-graph.svg'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function exportPNG() {
  if (!graphSvg.value) return
  const svgEl = graphSvg.value
  const serializer = new XMLSerializer()
  const svgString = serializer.serializeToString(svgEl)
  const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(svgBlob)

  const img = new Image()
  img.onload = () => {
    const canvas = document.createElement('canvas')
    const scale = 2 // retina export
    canvas.width = svgEl.clientWidth * scale
    canvas.height = svgEl.clientHeight * scale
    const ctx = canvas.getContext('2d')
    ctx.scale(scale, scale)
    ctx.drawImage(img, 0, 0)
    URL.revokeObjectURL(url)

    canvas.toBlob((blob) => {
      if (!blob) return
      const pngUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = pngUrl
      a.download = 'topic-graph.png'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(pngUrl)
    }, 'image/png')
  }
  img.src = url
}

// ─── Main render ──────────────────────────────────────────────────────────────
function renderGraph() {
  if (!graphSvg.value || !graphContainer.value || !props.graphData) return

  const nodes = props.graphData.nodes || []
  const edges = props.graphData.edges || []

  if (nodes.length === 0) return

  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight

  // Clear previous
  const svg = d3.select(graphSvg.value)
  svg.selectAll('*').remove()
  svg.attr('width', width).attr('height', height)

  // Zoom group
  const g = svg.append('g')
  const zoom = d3.zoom()
    .scaleExtent([0.1, 8])
    .on('zoom', (event) => {
      g.attr('transform', event.transform)
      currentZoomLevel.value = event.transform.k
      currentZoomTransform = event.transform
      applySemanticZoom()
    })
  svg.call(zoom)

  // Build link/node data with copies
  const nodeMap = new Map()
  const simNodes = nodes.map(n => {
    const copy = { ...n }
    nodeMap.set(n.id, copy)
    return copy
  })

  const simLinks = edges
    .filter(e => nodeMap.has(e.source) && nodeMap.has(e.target))
    .map(e => ({
      source: e.source,
      target: e.target,
      type: e.type,
      weight: e.weight || 1,
    }))

  // Force simulation
  if (simulation) simulation.stop()

  simulation = d3.forceSimulation(simNodes)
    .force('link', d3.forceLink(simLinks).id(d => d.id).distance(d => {
      if (d.type === 'hierarchy') return 60
      if (d.type === 'belongs_to') return 80
      return 120
    }))
    .force('charge', d3.forceManyBody().strength(d => {
      if (d.type === 'topic') return -300
      return -50
    }))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(d => getNodeRadius(d) + 4))
    .force('x', d3.forceX(width / 2).strength(0.03))
    .force('y', d3.forceY(height / 2).strength(0.03))

  // Shared drag behavior
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

  svg.on('click', () => {
    selectedNode.value = null
  })

  if (visualStyle.value === 'neural') {
    // ── Neural mode rendering ─────────────────────────────────
    createNeuralDefs(svg, getCSSVar)
    createNeuralBackground(g, width, height, getCSSVar)

    const labelColor = getCSSVar('--neural-label')

    // Edges
    const linkGroup = g.append('g').attr('class', 'links')
    neuralEdgePaths = renderNeuralEdges(linkGroup, simLinks, getCSSVar)

    // Nodes
    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(simNodes)
      .join('g')
      .attr('cursor', 'pointer')
      .call(d3.drag()
        .on('start', dragStarted)
        .on('drag', dragged)
        .on('end', dragEnded)
      )
      .on('click', (event, d) => {
        event.stopPropagation()
        selectedNode.value = d
        emit('node-click', d)
      })

    renderNeuralNode(node, getNodeRadius, getNodeColor, getCSSVar)

    // Labels
    node.append('text')
      .text(d => {
        if (d.type === 'topic') return d.label
        return d.label ? d.label.substring(0, 25) + (d.label.length > 25 ? '...' : '') : ''
      })
      .attr('dx', d => getNodeRadius(d) + 4)
      .attr('dy', 4)
      .attr('font-size', d => d.type === 'topic' && d.level === 1 ? '12px' : '10px')
      .attr('font-weight', d => d.type === 'topic' && d.level <= 2 ? '600' : '400')
      .attr('fill', labelColor)
      .attr('display', d => {
        if (!showLabels.value && d.type === 'paper') return 'none'
        return null
      })

    // Gaps
    if (props.gaps && props.gaps.length > 0) {
      const gapGroup = g.append('g').attr('class', 'gaps')
      renderNeuralGaps(gapGroup, props.gaps, nodeMap, getCSSVar)
    }

    // Tick
    simulation.on('tick', () => {
      updateNeuralEdgePaths(neuralEdgePaths)
      node.attr('transform', d => `translate(${d.x},${d.y})`)
      g.selectAll('.gaps path')
        .attr('d', function() {
          const datum = d3.select(this).datum()
          if (!datum) return ''
          return computeBezierPath(datum.source, datum.target, 0.15)
        })
    })

  } else {
    // ── Classic mode rendering ─────────────────────────────────
    const edgeColor = getCSSVar('--graph-edge')
    const hierarchyColor = getCSSVar('--graph-hierarchy')
    const labelColor = getCSSVar('--graph-label')
    const bgColor = getCSSVar('--bg-primary')

    // Draw edges
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(simLinks)
      .join('line')
      .attr('stroke', d => {
        if (d.type === 'hierarchy') return hierarchyColor
        return edgeColor
      })
      .attr('stroke-width', d => {
        if (d.type === 'hierarchy') return 2
        if (d.type === 'cites') return 1.5
        return 0.8
      })
      .attr('stroke-opacity', d => {
        if (d.type === 'hierarchy') return 0.7
        return 0.25
      })
      .attr('stroke-dasharray', d => d.type === 'cites' ? '4,2' : null)

    // Draw nodes
    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(simNodes)
      .join('g')
      .attr('cursor', 'pointer')
      .call(d3.drag()
        .on('start', dragStarted)
        .on('drag', dragged)
        .on('end', dragEnded)
      )
      .on('click', (event, d) => {
        event.stopPropagation()
        selectedNode.value = d
        emit('node-click', d)
      })

    // Node circles
    node.append('circle')
      .attr('r', d => getNodeRadius(d))
      .attr('fill', d => getNodeColor(d))
      .attr('stroke', bgColor)
      .attr('stroke-width', d => d.type === 'topic' ? 2 : 1)

    // Node labels
    node.append('text')
      .text(d => {
        if (d.type === 'topic') return d.label
        return d.label ? d.label.substring(0, 25) + (d.label.length > 25 ? '...' : '') : ''
      })
      .attr('dx', d => getNodeRadius(d) + 4)
      .attr('dy', 4)
      .attr('font-size', d => d.type === 'topic' && d.level === 1 ? '12px' : '10px')
      .attr('font-weight', d => d.type === 'topic' && d.level <= 2 ? '600' : '400')
      .attr('fill', labelColor)
      .attr('display', d => {
        if (!showLabels.value && d.type === 'paper') return 'none'
        return null
      })

    // Gap indicators
    if (props.gaps && props.gaps.length > 0) {
      const gapColor = getCSSVar('--graph-gap')
      const gapLines = g.append('g').attr('class', 'gaps')

      for (const gap of props.gaps) {
        const nodeA = nodeMap.get(gap.topic_a_id)
        const nodeB = nodeMap.get(gap.partner_id)
        if (nodeA && nodeB) {
          gapLines.append('line')
            .attr('class', 'gap-line')
            .attr('stroke', gapColor)
            .attr('stroke-width', Math.max(1, gap.gap_score * 3))
            .attr('stroke-dasharray', '6,4')
            .attr('stroke-opacity', 0.6)
            .datum({ source: nodeA, target: nodeB })
        }
      }
    }

    // Tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)

      node.attr('transform', d => `translate(${d.x},${d.y})`)

      g.selectAll('.gap-line')
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)
    })

    neuralEdgePaths = null
  }

  // Apply initial semantic zoom state
  applySemanticZoom()
}

// ─── Update node fills when color mode changes ───────────────────────────────
function updateNodeColors() {
  if (!graphSvg.value) return
  const svg = d3.select(graphSvg.value)
  svg.selectAll('.nodes circle')
    .attr('fill', function() {
      const d = d3.select(this.parentNode).datum()
      if (!d) return '#888'
      return getNodeColor(d)
    })
}

// ─── Watchers ─────────────────────────────────────────────────────────────────
watch(() => props.graphData, () => {
  hiddenCategories.clear()
  nextTick(renderGraph)
}, { deep: true })

watch(showLabels, () => {
  if (!graphSvg.value) return
  const svg = d3.select(graphSvg.value)
  svg.selectAll('.nodes text')
    .attr('display', function() {
      const d = d3.select(this.parentNode).datum()
      if (!showLabels.value && d.type === 'paper') return 'none'
      return null
    })
})

watch(colorMode, () => {
  hiddenCategories.clear()
  updateNodeColors()
})

watch(visualStyle, () => {
  hiddenCategories.clear()
  nextTick(renderGraph)
})

// ─── Lifecycle ────────────────────────────────────────────────────────────────
onMounted(() => {
  nextTick(renderGraph)

  if (graphContainer.value) {
    resizeObserver = new ResizeObserver(() => {
      nextTick(renderGraph)
    })
    resizeObserver.observe(graphContainer.value)
  }

  // Re-render graph when theme changes (data-theme attribute on <html>)
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
.topic-graph-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-secondary);
  background: var(--bg-secondary);
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.3px;
}

.header-tools {
  display: flex;
  gap: 6px;
}

.tool-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tool-btn:hover {
  background: var(--bg-hover);
  border-color: var(--os-brand);
  color: var(--os-brand);
}

.tool-btn.active {
  background: var(--os-brand);
  color: var(--text-on-brand);
  border-color: var(--os-brand);
}

.tool-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-text {
  font-size: 11px;
}

.icon-refresh {
  font-size: 14px;
  display: inline-block;
}

.icon-refresh.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.graph-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: var(--graph-bg);
}

.graph-svg {
  width: 100%;
  height: 100%;
}

/* Empty state */
.empty-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: var(--text-tertiary);
}

.empty-icon {
  font-size: 36px;
  margin-bottom: 12px;
  opacity: 0.4;
}

.empty-state p {
  margin: 4px 0;
  font-size: 13px;
}

.empty-hint {
  font-size: 11px !important;
  color: var(--text-tertiary);
}

/* Detail panel */
.detail-panel {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 280px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  z-index: 10;
}

.detail-panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-secondary);
}

.detail-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.detail-type-badge {
  font-size: 10px;
  font-weight: 600;
  color: #FFF;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}

.detail-close {
  margin-left: auto;
  background: none;
  border: none;
  font-size: 18px;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 0 4px;
}

.detail-close:hover {
  color: var(--text-primary);
}

.detail-content {
  padding: 12px;
}

.detail-row {
  display: flex;
  margin-bottom: 8px;
  font-size: 12px;
}

.detail-label {
  font-weight: 600;
  color: var(--text-tertiary);
  min-width: 70px;
}

.detail-value {
  color: var(--text-primary);
  word-break: break-all;
}

.uuid-text {
  font-size: 10px;
  font-family: var(--font-mono);
}

/* Zoom level indicator */
.zoom-indicator {
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-md);
  font-size: 11px;
  color: var(--text-secondary);
  box-shadow: var(--shadow-sm);
  z-index: 5;
  user-select: none;
  pointer-events: none;
}

.zoom-level-label {
  font-weight: 600;
  color: var(--text-primary);
}

.zoom-level-value {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-tertiary);
}

/* Interactive Legend */
.graph-legend {
  position: absolute;
  bottom: 12px;
  left: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 12px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-md);
  font-size: 11px;
  color: var(--text-secondary);
  box-shadow: var(--shadow-sm);
  z-index: 5;
  max-height: 220px;
  overflow-y: auto;
}

.legend-header {
  display: flex;
  align-items: center;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--border-secondary);
}

.color-mode-select {
  width: 100%;
  padding: 3px 6px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  outline: none;
}

.color-mode-select:hover {
  border-color: var(--os-brand);
}

.legend-items {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 4px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  user-select: none;
}

.legend-item:hover {
  background: var(--bg-hover);
}

.legend-item-hidden {
  opacity: 0.35;
  text-decoration: line-through;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-label {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-transform: capitalize;
}

.legend-count {
  font-size: 10px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  flex-shrink: 0;
}

/* ── Neural mode ── */
.icon-neural {
  font-size: 14px;
  line-height: 1;
}

.graph-container.neural-mode {
  background: var(--neural-bg);
}

/* Breathing aura for domain nodes */
:deep(.neural-breathe) {
  animation: neural-breathe-scale 4s ease-in-out infinite;
  transform-origin: center;
  will-change: transform;
}

@keyframes neural-breathe-scale {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.08); }
}

/* Brownian jitter for paper vesicles */
:deep(.neural-jitter) {
  animation: neural-brownian 3s ease-in-out infinite;
  will-change: transform;
}

@keyframes neural-brownian {
  0%   { transform: translate(0, 0); }
  25%  { transform: translate(1px, -1px); }
  50%  { transform: translate(-1px, 0.5px); }
  75%  { transform: translate(0.5px, 1px); }
  100% { transform: translate(0, 0); }
}

/* Flickering dormant synapse for gaps */
:deep(.neural-flicker) {
  animation: neural-gap-flicker var(--flicker-dur, 2s) ease-in-out infinite;
  will-change: opacity;
}

@keyframes neural-gap-flicker {
  0%, 100% { opacity: 0.15; }
  50% { opacity: 0.7; }
}
</style>

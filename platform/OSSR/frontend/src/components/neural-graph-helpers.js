/**
 * neural-graph-helpers.js — Neural tissue visual rendering for TopicGraph
 *
 * Pure functions that generate SVG elements for the "neural network" visual mode.
 * Domains → brain regions, subfields → neuron soma, threads → synaptic terminals,
 * papers → neurotransmitter vesicles. Edges become dendrites with traveling pulses.
 *
 * No Vue dependencies — just D3 + DOM manipulation.
 */

import * as d3 from 'd3'

// ── SVG <defs> for neural mode ─────────────────────────────────────

/**
 * Create SVG filter and gradient definitions for neural rendering.
 * @param {d3.Selection} svg - The root SVG selection
 * @param {(name: string) => string} getCSSVar - CSS variable resolver
 */
export function createNeuralDefs(svg, getCSSVar) {
  // Remove existing neural defs if re-rendering
  svg.select('defs.neural-defs').remove()
  const defs = svg.append('defs').attr('class', 'neural-defs')

  // Cellular noise filter for background texture
  const noiseFilter = defs.append('filter')
    .attr('id', 'neural-noise')
    .attr('x', '0%').attr('y', '0%')
    .attr('width', '100%').attr('height', '100%')
  noiseFilter.append('feTurbulence')
    .attr('type', 'fractalNoise')
    .attr('baseFrequency', '0.65')
    .attr('numOctaves', '3')
    .attr('stitchTiles', 'stitch')
    .attr('result', 'noise')
  noiseFilter.append('feColorMatrix')
    .attr('type', 'saturate')
    .attr('values', '0')
    .attr('in', 'noise')
    .attr('result', 'grayNoise')
  noiseFilter.append('feBlend')
    .attr('in', 'SourceGraphic')
    .attr('in2', 'grayNoise')
    .attr('mode', 'multiply')

  // Glow filter (small) for subfield halos
  const glowSm = defs.append('filter')
    .attr('id', 'neural-glow')
    .attr('x', '-50%').attr('y', '-50%')
    .attr('width', '200%').attr('height', '200%')
  glowSm.append('feGaussianBlur')
    .attr('in', 'SourceGraphic')
    .attr('stdDeviation', '4')
    .attr('result', 'blur')
  glowSm.append('feMerge')
    .selectAll('feMergeNode')
    .data(['blur', 'SourceGraphic'])
    .join('feMergeNode')
    .attr('in', d => d)

  // Glow filter (large) for domain aura halos
  const glowLg = defs.append('filter')
    .attr('id', 'neural-glow-lg')
    .attr('x', '-80%').attr('y', '-80%')
    .attr('width', '260%').attr('height', '260%')
  glowLg.append('feGaussianBlur')
    .attr('in', 'SourceGraphic')
    .attr('stdDeviation', '8')
    .attr('result', 'blur')
  glowLg.append('feMerge')
    .selectAll('feMergeNode')
    .data(['blur', 'SourceGraphic'])
    .join('feMergeNode')
    .attr('in', d => d)

  // Radial gradient for subfield (neuron soma) inner glow
  const somaGrad = defs.append('radialGradient')
    .attr('id', 'neural-soma-gradient')
    .attr('cx', '40%').attr('cy', '35%')
    .attr('r', '60%')
  somaGrad.append('stop')
    .attr('offset', '0%')
    .attr('stop-color', getCSSVar('--neural-subfield-nucleus'))
    .attr('stop-opacity', '0.9')
  somaGrad.append('stop')
    .attr('offset', '100%')
    .attr('stop-color', getCSSVar('--neural-subfield-core'))
    .attr('stop-opacity', '0.6')

  // Radial gradient for thread (synaptic vesicle) glass effect
  const vesicleGrad = defs.append('radialGradient')
    .attr('id', 'neural-vesicle-gradient')
    .attr('cx', '35%').attr('cy', '30%')
    .attr('r', '65%')
  vesicleGrad.append('stop')
    .attr('offset', '0%')
    .attr('stop-color', '#ffffff')
    .attr('stop-opacity', '0.4')
  vesicleGrad.append('stop')
    .attr('offset', '50%')
    .attr('stop-color', getCSSVar('--neural-thread-fill'))
    .attr('stop-opacity', '0.6')
  vesicleGrad.append('stop')
    .attr('offset', '100%')
    .attr('stop-color', getCSSVar('--neural-thread-fill'))
    .attr('stop-opacity', '0.3')
}

// ── Background layer ───────────────────────────────────────────────

/**
 * Create the neural background: solid fill + cellular noise + CSF drift particles.
 * @param {d3.Selection} g - The zoom group
 * @param {number} width
 * @param {number} height
 * @param {(name: string) => string} getCSSVar
 */
export function createNeuralBackground(g, width, height, getCSSVar) {
  const bg = g.append('g').attr('class', 'neural-background')

  // Solid background fill
  bg.append('rect')
    .attr('x', -width).attr('y', -height)
    .attr('width', width * 3).attr('height', height * 3)
    .attr('fill', getCSSVar('--neural-bg'))

  // Cellular noise overlay
  bg.append('rect')
    .attr('x', -width).attr('y', -height)
    .attr('width', width * 3).attr('height', height * 3)
    .attr('fill', getCSSVar('--neural-bg-grid'))
    .attr('filter', 'url(#neural-noise)')
    .attr('opacity', 0.5)

  // Cerebrospinal fluid drift particles
  const particleCount = 10
  for (let i = 0; i < particleCount; i++) {
    const cx = Math.random() * width
    const cy = Math.random() * height
    const r = 1 + Math.random() * 2.5
    const dur = 15 + Math.random() * 15
    // Random drift path
    const dx1 = (Math.random() - 0.5) * 80
    const dy1 = (Math.random() - 0.5) * 60
    const dx2 = (Math.random() - 0.5) * 80
    const dy2 = (Math.random() - 0.5) * 60

    const particle = bg.append('circle')
      .attr('cx', cx).attr('cy', cy)
      .attr('r', r)
      .attr('fill', getCSSVar('--neural-csf-particle'))
      .attr('opacity', 0.6)

    // Native SVG animateMotion for smooth drift
    const motionPath = `M0,0 C${dx1},${dy1} ${dx2},${dy2} 0,0`
    const animate = document.createElementNS('http://www.w3.org/2000/svg', 'animateMotion')
    animate.setAttribute('path', motionPath)
    animate.setAttribute('dur', `${dur}s`)
    animate.setAttribute('repeatCount', 'indefinite')
    particle.node().appendChild(animate)
  }
}

// ── Bezier helpers ─────────────────────────────────────────────────

/**
 * Compute a cubic Bezier SVG path between two points with perpendicular offset.
 * @param {{ x: number, y: number }} source
 * @param {{ x: number, y: number }} target
 * @param {number} curvature - 0 = straight, 0.3 = moderate curve
 * @returns {string} SVG path d attribute
 */
export function computeBezierPath(source, target, curvature = 0.2) {
  if (!source || !target || isNaN(source.x) || isNaN(target.x)) return ''
  const dx = target.x - source.x
  const dy = target.y - source.y
  const dist = Math.sqrt(dx * dx + dy * dy)
  if (dist < 0.01) return `M${source.x},${source.y}L${target.x},${target.y}`

  // Perpendicular offset for control points
  const nx = -dy / dist * curvature * dist * 0.5
  const ny = dx / dist * curvature * dist * 0.5
  const mx = (source.x + target.x) / 2
  const my = (source.y + target.y) / 2

  return `M${source.x},${source.y} Q${mx + nx},${my + ny} ${target.x},${target.y}`
}

// ── Edge rendering ─────────────────────────────────────────────────

/**
 * Render edges as Bezier curves with optional traveling pulse dots.
 * @param {d3.Selection} linkGroup - Container <g> for edges
 * @param {Array} simLinks - D3 force link array
 * @param {(name: string) => string} getCSSVar
 * @returns {d3.Selection} The path selection (for tick updates)
 */
export function renderNeuralEdges(linkGroup, simLinks, getCSSVar) {
  let particleCount = 0
  const MAX_PARTICLES = 30

  const paths = linkGroup.selectAll('g.neural-edge')
    .data(simLinks)
    .join('g')
    .attr('class', 'neural-edge')

  // Edge path
  paths.append('path')
    .attr('class', 'neural-edge-path')
    .attr('fill', 'none')
    .attr('stroke', d => {
      if (d.type === 'hierarchy') return getCSSVar('--neural-dendrite')
      if (d.type === 'cites') return getCSSVar('--neural-synapse')
      return getCSSVar('--neural-synapse')
    })
    .attr('stroke-width', d => {
      if (d.type === 'hierarchy') return 2.5
      if (d.type === 'cites') return 1
      return 0.8
    })
    .attr('stroke-opacity', d => {
      if (d.type === 'hierarchy') return 0.7
      if (d.type === 'cites') return 0.35
      return 0.2
    })
    .attr('stroke-linecap', 'round')
    .attr('d', d => computeBezierPath(d.source, d.target,
      d.type === 'hierarchy' ? 0.2 : 0.15))

  // Traveling pulse dots on hierarchy edges
  paths.each(function (d) {
    if (particleCount >= MAX_PARTICLES) return
    if (d.type !== 'hierarchy' && d.type !== 'cites') return

    const isHierarchy = d.type === 'hierarchy'
    if (!isHierarchy && particleCount >= MAX_PARTICLES - 5) return

    particleCount++

    const dot = d3.select(this).append('circle')
      .attr('r', isHierarchy ? 2 : 1.5)
      .attr('fill', getCSSVar('--neural-pulse-dot'))
      .attr('opacity', isHierarchy ? 0.8 : 0.5)
      .attr('class', isHierarchy ? 'action-potential-dot' : 'neurotransmitter-particle')

    const animate = document.createElementNS('http://www.w3.org/2000/svg', 'animateMotion')
    animate.setAttribute('dur', isHierarchy ? `${2 + Math.random()}s` : `${3 + Math.random() * 2}s`)
    animate.setAttribute('repeatCount', 'indefinite')
    animate.setAttribute('fill', 'freeze')
    // Path will be set on each tick
    dot.node().appendChild(animate)
    dot.node().__edgeDatum = d
  })

  // Return path selection for tick updates
  return paths
}

/**
 * Update edge paths on simulation tick.
 * @param {d3.Selection} edgePaths - The neural edge group selection
 */
export function updateNeuralEdgePaths(edgePaths) {
  edgePaths.each(function (d) {
    const g = d3.select(this)
    const curvature = d.type === 'hierarchy' ? 0.2 : 0.15
    const pathD = computeBezierPath(d.source, d.target, curvature)

    g.select('.neural-edge-path').attr('d', pathD)

    // Update animateMotion paths
    g.selectAll('animateMotion').each(function () {
      this.setAttribute('path', pathD.replace(/^M/, 'm0,0 ') || 'M0,0L0,0')
    })
  })
}

// ── Node rendering ─────────────────────────────────────────────────

/**
 * Render nodes with neural tissue aesthetics.
 * @param {d3.Selection} selection - Node <g> selection
 * @param {(d: any) => number} getNodeRadius
 * @param {(d: any) => string} getNodeColor
 * @param {(name: string) => string} getCSSVar
 */
export function renderNeuralNode(selection, getNodeRadius, getNodeColor, getCSSVar) {
  selection.each(function (d) {
    const g = d3.select(this)
    const r = getNodeRadius(d)
    const color = getNodeColor(d)

    if (d.type === 'topic' && d.level === 1) {
      // Domain → Brain region: outer aura halo + inner solid
      g.append('circle')
        .attr('r', r * 1.8)
        .attr('fill', color)
        .attr('opacity', 0.2)
        .attr('filter', 'url(#neural-glow-lg)')
        .attr('class', 'neural-breathe')

      g.append('circle')
        .attr('r', r)
        .attr('fill', color)
        .attr('stroke', getCSSVar('--neural-domain-glow'))
        .attr('stroke-width', 1.5)
        .attr('opacity', 0.85)

    } else if (d.type === 'topic' && d.level === 2) {
      // Subfield → Neuron soma: glow halo + gradient fill + nucleus dot
      g.append('circle')
        .attr('r', r * 1.3)
        .attr('fill', color)
        .attr('opacity', 0.2)
        .attr('filter', 'url(#neural-glow)')

      g.append('circle')
        .attr('r', r)
        .attr('fill', 'url(#neural-soma-gradient)')
        .attr('stroke', color)
        .attr('stroke-width', 1)
        .attr('opacity', 0.8)

      g.append('circle')
        .attr('r', r * 0.25)
        .attr('fill', getCSSVar('--neural-subfield-nucleus'))
        .attr('opacity', 0.9)

    } else if (d.type === 'topic' && d.level === 3) {
      // Thread → Synaptic terminal: translucent vesicle with glass effect
      g.append('circle')
        .attr('r', r)
        .attr('fill', 'url(#neural-vesicle-gradient)')
        .attr('stroke', getCSSVar('--neural-thread-stroke'))
        .attr('stroke-width', 1)
        .attr('opacity', 0.75)

    } else {
      // Paper → Neurotransmitter vesicle: tiny particle with jitter
      g.append('circle')
        .attr('r', r)
        .attr('fill', getCSSVar('--neural-paper-fill'))
        .attr('opacity', 0.7)
        .attr('class', 'neural-jitter')
    }
  })
}

// ── Gap rendering ──────────────────────────────────────────────────

/**
 * Render research gaps as dormant synapse arcs with flicker animation.
 * @param {d3.Selection} gapGroup - Container <g>
 * @param {Array} gaps - Gap data array
 * @param {Map} nodeMap - Map of node id → node datum (with x, y)
 * @param {(name: string) => string} getCSSVar
 */
export function renderNeuralGaps(gapGroup, gaps, nodeMap, getCSSVar) {
  for (const gap of gaps) {
    const nodeA = nodeMap.get(gap.topic_a_id)
    const nodeB = nodeMap.get(gap.partner_id)
    if (!nodeA || !nodeB) continue

    // Flicker speed proportional to gap severity
    const flickerDur = Math.max(0.8, 3 - gap.gap_score * 2.5)

    gapGroup.append('path')
      .attr('fill', 'none')
      .attr('stroke', getCSSVar('--neural-gap-dormant'))
      .attr('stroke-width', Math.max(1, gap.gap_score * 3))
      .attr('stroke-dasharray', '4,6')
      .attr('class', 'neural-flicker')
      .style('--flicker-dur', `${flickerDur}s`)
      .datum({ source: nodeA, target: nodeB })
      .attr('d', computeBezierPath(nodeA, nodeB, 0.15))
  }
}

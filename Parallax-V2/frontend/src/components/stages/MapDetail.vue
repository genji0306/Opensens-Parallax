<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as d3 from 'd3'
import MetricCard from '@/components/shared/MetricCard.vue'
import { getResearchMap, getResearchGaps } from '@/api/research'
import { getRunTopics } from '@/api/ais'
import type { RunTopic } from '@/api/ais'

const props = defineProps<{
  result: Record<string, unknown>
  runId?: string
}>()

// ── Topic click detail ──
const selectedTopic = ref<RunTopic | null>(null)
const topicDetails = ref<RunTopic[]>([])

async function fetchTopicDetails() {
  if (!props.runId) return
  try {
    const res = await getRunTopics(props.runId, { limit: 50 })
    const body = res.data as unknown as Record<string, unknown>
    const inner = (body.data ?? body) as Record<string, unknown>
    topicDetails.value = (inner.topics ?? []) as RunTopic[]
  } catch { /* details are optional */ }
}

function handleTopicClick(topicName: string) {
  const match = topicDetails.value.find(t => t.name === topicName)
  if (match) {
    selectedTopic.value = selectedTopic.value?.topic_id === match.topic_id ? null : match
  } else {
    selectedTopic.value = {
      topic_id: '', name: topicName, level: 0, description: '',
      parent_id: null, paper_count: 0, key_papers: [], contradictions: [],
      gaps: [], novelty_opportunities: [], cluster_summary: `Topic: ${topicName}`,
    }
  }
}

interface TopicSummary {
  name: string
  paper_count: number
}

interface MapNode {
  id: string
  label: string
  type: string
  paper_count?: number
  connections?: string[]
}

interface MapEdge {
  source: string
  target: string
  type?: string
}

interface GraphNode extends d3.SimulationNodeDatum {
  id: string
  label: string
  type: 'topic' | 'paper'
  paper_count?: number
  radius: number
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  source: string | GraphNode
  target: string | GraphNode
}

const error = ref<string | null>(null)
const graphContainer = ref<HTMLDivElement | null>(null)
let simulation: d3.Simulation<GraphNode, GraphLink> | null = null

// API-fetched data (for the D3 graph and fallback counts)
const apiTopics = ref<TopicSummary[]>([])
const apiNodes = ref<MapNode[]>([])
const apiEdges = ref<MapEdge[]>([])
const apiFetchedPapers = ref<number | null>(null)
const apiFetchedTopics = ref<number | null>(null)
const apiFetchedGaps = ref<number | null>(null)

// ── Metrics: prefer props.result (run-scoped), fall back to API ──
const topicsFound = computed(() =>
  (props.result.topics_found as number)
  ?? (props.result.topic_count as number)
  ?? (props.result.cluster_count as number)
  ?? apiFetchedTopics.value
  ?? 0,
)
const papersIngested = computed(() =>
  (props.result.papers_ingested as number)
  ?? (props.result.paper_count as number)
  ?? apiFetchedPapers.value
  ?? 0,
)
const gapsCount = computed(() =>
  (props.result.gaps_found as number)
  ?? (props.result.research_gaps_count as number)
  ?? (props.result.gaps_count as number)
  ?? apiFetchedGaps.value
  ?? 0,
)

// ── Top topics: props.result first, then API ──
const topTopics = computed<TopicSummary[]>(() => {
  // From props.result
  const raw = props.result.top_topics as TopicSummary[] | undefined
  if (raw && Array.isArray(raw) && raw.length > 0) return raw.slice(0, 12)

  // From clusters in props.result
  const clusters = props.result.clusters as Record<string, unknown>[] | undefined
  if (clusters && Array.isArray(clusters) && clusters.length > 0) {
    return clusters
      .map((c) => ({
        name: (c.label ?? c.name ?? c.topic ?? 'Unknown') as string,
        paper_count: (c.paper_count ?? c.count ?? c.size ?? 0) as number,
      }))
      .sort((a, b) => b.paper_count - a.paper_count)
      .slice(0, 12)
  }

  // From topic details fetch (limited to 50, already sorted by paper_count)
  if (topicDetails.value.length > 0) {
    return topicDetails.value
      .slice(0, 15)
      .map(t => ({ name: t.name, paper_count: t.paper_count }))
  }

  // From API
  return apiTopics.value
})

const hasData = computed(() =>
  topicsFound.value > 0 || topTopics.value.length > 0 || gapsCount.value > 0 || papersIngested.value > 0,
)

// ── Fetch from API for the D3 graph & fallback metrics ──
const loading = ref(true)

onMounted(async () => {
  await fetchTopicDetails()

  // Skip expensive full-map API fetch when we already have summary metrics.
  // Old projects with 6000+ topics produce multi-MB responses that freeze the browser.
  // The D3 graph only needs 20 nodes, so the topic details fetch (limit: 50) is sufficient.
  if (hasData.value) {
    loading.value = false
    await nextTick()
    renderGraph()
    return
  }

  try {
    const [mapRes, gapsRes] = await Promise.allSettled([
      getResearchMap(props.runId ? { run_id: props.runId } : {}),
      getResearchGaps(props.runId ? { run_id: props.runId } : {}),
    ])

    if (mapRes.status === 'fulfilled') {
      const mapData = mapRes.value.data?.data as Record<string, unknown> | undefined
      const nodes = mapData?.nodes
      const edges = mapData?.edges

      if (Array.isArray(nodes)) {
        apiNodes.value = nodes as MapNode[]

        const topicNodes = nodes
          .filter((n: Record<string, unknown>) => n.type === 'topic')
          .sort((a: Record<string, unknown>, b: Record<string, unknown>) =>
            ((b.paper_count as number) ?? 0) - ((a.paper_count as number) ?? 0),
          )
          .slice(0, 15)
          .map((n: Record<string, unknown>) => ({
            name: n.label as string,
            paper_count: (n.paper_count as number) ?? 0,
          }))
        apiTopics.value = topicNodes

        // Derive counts
        const allTopicNodes = nodes.filter((n: Record<string, unknown>) => n.type === 'topic')
        const allPaperNodes = nodes.filter((n: Record<string, unknown>) => n.type === 'paper')
        apiFetchedTopics.value = allTopicNodes.length
        apiFetchedPapers.value = allPaperNodes.length
      }

      if (Array.isArray(edges)) {
        apiEdges.value = edges as MapEdge[]
      }
    }

    if (gapsRes.status === 'fulfilled') {
      const gapsData = gapsRes.value.data?.data
      if (Array.isArray(gapsData)) {
        apiFetchedGaps.value = gapsData.length
      }
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load map data'
  } finally {
    loading.value = false
  }

  await nextTick()
  renderGraph()
})

// ── D3 Force-Directed Graph ──
// Build graph from the top topics (API or result)
const graphNodes = computed<GraphNode[]>(() => {
  // Prefer real API nodes if available
  if (apiNodes.value.length > 0) {
    const topicNodes = apiNodes.value
      .filter(n => n.type === 'topic')
      .sort((a, b) => (b.paper_count ?? 0) - (a.paper_count ?? 0))
      .slice(0, 20)
    return topicNodes.map(n => ({
      id: n.id,
      label: n.label,
      type: 'topic' as const,
      paper_count: n.paper_count ?? 0,
      radius: Math.max(16, Math.min(40, 12 + Math.sqrt(n.paper_count ?? 0) * 4)),
    }))
  }

  // Fallback: build from topTopics
  const topics = topTopics.value
  if (topics.length === 0) return []

  return topics.map((t, i) => ({
    id: `topic-${i}`,
    label: t.name,
    type: 'topic' as const,
    paper_count: t.paper_count,
    radius: Math.max(16, Math.min(40, 12 + Math.sqrt(t.paper_count) * 4)),
  }))
})

const graphLinks = computed<GraphLink[]>(() => {
  const nodes = graphNodes.value
  if (nodes.length < 2) return []

  const nodeIds = new Set(nodes.map(n => n.id))

  // Use real API edges when available
  if (apiEdges.value.length > 0) {
    const realLinks: GraphLink[] = []
    for (const e of apiEdges.value) {
      if (nodeIds.has(e.source) && nodeIds.has(e.target)) {
        realLinks.push({ source: e.source, target: e.target })
      }
    }
    if (realLinks.length > 0) return realLinks
  }

  // Use node connections field if available
  if (apiNodes.value.length > 0) {
    const connLinks: GraphLink[] = []
    for (const n of apiNodes.value) {
      if (!nodeIds.has(n.id) || !n.connections) continue
      for (const targetId of n.connections) {
        if (nodeIds.has(targetId) && n.id < targetId) {
          connLinks.push({ source: n.id, target: targetId })
        }
      }
    }
    if (connLinks.length > 0) return connLinks
  }

  // Fallback: generate sparse network based on topic proximity
  const links: GraphLink[] = []
  for (let i = 0; i < nodes.length; i++) {
    const connections = Math.min(2, nodes.length - 1 - i)
    for (let j = 1; j <= connections; j++) {
      const src = nodes[i]
      const tgt = nodes[i + j]
      if (src && tgt) {
        links.push({ source: src.id, target: tgt.id })
      }
    }
  }
  return links
})

function renderGraph() {
  if (!graphContainer.value || graphNodes.value.length === 0) return

  // Cleanup previous
  d3.select(graphContainer.value).selectAll('*').remove()
  if (simulation) simulation.stop()

  const rect = graphContainer.value.getBoundingClientRect()
  const width = rect.width || 600
  const height = 300

  const svg = d3.select(graphContainer.value)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)

  // Defs for glow
  const defs = svg.append('defs')
  const filter = defs.append('filter').attr('id', 'glow')
  filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'blur')
  filter.append('feMerge').selectAll('feMergeNode')
    .data(['blur', 'SourceGraphic'])
    .join('feMergeNode')
    .attr('in', (d) => d)

  const nodes: GraphNode[] = graphNodes.value.map(d => ({ ...d }))
  const links: GraphLink[] = graphLinks.value.map(d => ({ ...d }))

  simulation = d3.forceSimulation<GraphNode>(nodes)
    .force('link', d3.forceLink<GraphNode, GraphLink>(links).id(d => d.id).distance(80))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide<GraphNode>().radius(d => d.radius + 6))
    .force('x', d3.forceX(width / 2).strength(0.05))
    .force('y', d3.forceY(height / 2).strength(0.05))

  const linkGroup = svg.append('g').attr('class', 'links')
  const nodeGroup = svg.append('g').attr('class', 'nodes')

  const linkElements = linkGroup.selectAll('line')
    .data(links)
    .join('line')
    .attr('stroke', 'var(--border-primary)')
    .attr('stroke-width', 1)
    .attr('stroke-opacity', 0.4)

  const nodeElements = nodeGroup.selectAll<SVGGElement, GraphNode>('g')
    .data(nodes)
    .join('g')
    .attr('cursor', 'pointer')
    .call(d3.drag<SVGGElement, GraphNode>()
      .on('start', (event, d) => {
        if (!event.active) simulation!.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
      })
      .on('drag', (event, d) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on('end', (event, d) => {
        if (!event.active) simulation!.alphaTarget(0)
        d.fx = null
        d.fy = null
      }),
    )

  nodeElements.append('circle')
    .attr('r', d => d.radius)
    .attr('fill', 'var(--os-brand-light)')
    .attr('stroke', 'var(--os-brand)')
    .attr('stroke-width', 1.5)
    .attr('filter', 'url(#glow)')
    .on('mouseenter', function () {
      d3.select(this).attr('fill', 'var(--os-brand-subtle)').attr('stroke-width', 2.5)
    })
    .on('mouseleave', function () {
      d3.select(this).attr('fill', 'var(--os-brand-light)').attr('stroke-width', 1.5)
    })
    .on('click', (_event: MouseEvent, d: GraphNode) => {
      handleTopicClick(d.label)
    })
    .style('cursor', 'pointer')

  // Paper count inside circle
  nodeElements.append('text')
    .text(d => d.paper_count ?? '')
    .attr('text-anchor', 'middle')
    .attr('dy', '0.35em')
    .attr('font-size', d => Math.max(10, d.radius * 0.45))
    .attr('font-weight', '700')
    .attr('font-family', 'var(--font-mono)')
    .attr('fill', 'var(--os-brand)')
    .attr('pointer-events', 'none')

  // Label below
  nodeElements.append('text')
    .text(d => d.label.length > 22 ? d.label.slice(0, 20) + '...' : d.label)
    .attr('text-anchor', 'middle')
    .attr('dy', d => d.radius + 14)
    .attr('font-size', '10px')
    .attr('font-weight', '500')
    .attr('fill', 'var(--text-secondary)')
    .attr('pointer-events', 'none')

  simulation.on('tick', () => {
    linkElements
      .attr('x1', d => (d.source as GraphNode).x!)
      .attr('y1', d => (d.source as GraphNode).y!)
      .attr('x2', d => (d.target as GraphNode).x!)
      .attr('y2', d => (d.target as GraphNode).y!)

    nodeElements.attr('transform', d => {
      const x = Math.max(d.radius, Math.min(width - d.radius, d.x!))
      const y = Math.max(d.radius + 5, Math.min(height - d.radius - 15, d.y!))
      d.x = x
      d.y = y
      return `translate(${x},${y})`
    })
  })
}

watch(graphNodes, () => {
  nextTick(() => renderGraph())
})

onUnmounted(() => {
  if (simulation) simulation.stop()
})
</script>

<template>
  <div class="map-detail">
    <template v-if="hasData">
      <div class="map-detail__metrics">
        <MetricCard
          label="Papers"
          :value="papersIngested"
          icon="article"
        />
        <MetricCard
          label="Topics"
          :value="topicsFound"
          icon="hub"
        />
        <MetricCard
          label="Research Gaps"
          :value="gapsCount"
          icon="lightbulb"
        />
      </div>

      <!-- Top Topics List -->
      <div v-if="topTopics.length > 0" class="topic-section">
        <h5 class="detail-heading">Top Topics</h5>
        <div class="topic-chips">
          <button
            v-for="topic in topTopics"
            :key="topic.name"
            class="topic-chip"
            :class="{ 'topic-chip--selected': selectedTopic?.name === topic.name }"
            @click="handleTopicClick(topic.name)"
          >
            {{ topic.name }}
            <span class="topic-chip__count font-mono">{{ topic.paper_count }}</span>
          </button>
        </div>
      </div>

      <!-- D3 Force-Directed Graph -->
      <div v-if="graphNodes.length > 0" class="viz-container">
        <h5 class="detail-heading">Topic Network</h5>
        <p class="viz-hint">Click a node to see topic details</p>
        <div ref="graphContainer" class="viz-graph" />
      </div>

      <!-- Topic Detail Panel (on click) -->
      <div v-if="selectedTopic" class="topic-detail">
        <div class="topic-detail__header">
          <h5 class="topic-detail__name">{{ selectedTopic.name }}</h5>
          <span class="topic-detail__count font-mono">{{ selectedTopic.paper_count }} papers</span>
          <button class="topic-detail__close" @click="selectedTopic = null">
            <span class="material-symbols-outlined" style="font-size:16px">close</span>
          </button>
        </div>
        <p v-if="selectedTopic.cluster_summary" class="topic-detail__summary">{{ selectedTopic.cluster_summary }}</p>
        <div v-if="selectedTopic.key_papers?.length" class="topic-detail__section">
          <h6 class="detail-heading">Key Papers</h6>
          <div v-for="paper in selectedTopic.key_papers" :key="paper.paper_id" class="topic-detail__paper">
            <span class="topic-detail__paper-title">{{ paper.title }}</span>
            <span class="topic-detail__paper-cit font-mono">{{ paper.citations }} cit.</span>
          </div>
        </div>
        <div v-if="selectedTopic.gaps?.length" class="topic-detail__section">
          <h6 class="detail-heading">Research Gaps</h6>
          <ul class="topic-detail__list topic-detail__list--gap">
            <li v-for="(g, i) in selectedTopic.gaps" :key="i">{{ typeof g === 'string' ? g : (g as Record<string,string>).description || '' }}</li>
          </ul>
        </div>
        <div v-if="selectedTopic.novelty_opportunities?.length" class="topic-detail__section">
          <h6 class="detail-heading">Novelty Opportunities</h6>
          <ul class="topic-detail__list topic-detail__list--novelty">
            <li v-for="(n, i) in selectedTopic.novelty_opportunities" :key="i">{{ typeof n === 'string' ? n : (n as Record<string,string>).description || '' }}</li>
          </ul>
        </div>
      </div>
    </template>

    <div v-else-if="loading" class="map-detail__empty">
      <span class="material-symbols-outlined" style="font-size: 24px; color: var(--text-tertiary)">hourglass_empty</span>
      <span>Loading map data...</span>
    </div>

    <div v-else-if="error" class="map-detail__error">
      <span class="material-symbols-outlined" style="font-size: 16px; color: var(--error)">error</span>
      <span>{{ error }}</span>
    </div>

    <div v-else class="map-detail__empty">
      <span class="material-symbols-outlined" style="font-size: 24px; color: var(--text-tertiary)">hub</span>
      <span>No map data available yet</span>
    </div>
  </div>
</template>

<style scoped>
.map-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 14px;
}

.detail-heading {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin: 0 0 8px;
}

.map-detail__metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
}

/* ── Topic Chips ── */
.topic-section {
  display: flex;
  flex-direction: column;
}

.topic-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.topic-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-pill);
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.topic-chip:hover {
  border-color: var(--os-brand);
  background: var(--bg-active);
}

.topic-chip__count {
  font-size: 10px;
  color: var(--text-tertiary);
  padding: 1px 5px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-pill);
}

/* ── D3 Graph ── */
.viz-container {
  display: flex;
  flex-direction: column;
}

.viz-graph {
  width: 100%;
  min-height: 300px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.viz-graph :deep(svg) {
  display: block;
}

.map-detail__empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 20px;
  color: var(--text-tertiary);
  font-size: 13px;
  justify-content: center;
}

.map-detail__error {
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

.viz-hint { font-size: 11px; color: var(--text-tertiary); margin: 0 0 6px; }

.topic-chip { cursor: pointer; border: none; font-family: inherit; }
.topic-chip--selected { background: var(--os-brand-light); outline: 1px solid var(--os-brand); }

.topic-detail {
  padding: 14px; background: var(--bg-secondary); border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md); margin-top: 12px;
}
.topic-detail__header { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.topic-detail__name { flex: 1; font-size: 14px; font-weight: 600; color: var(--text-primary); margin: 0; }
.topic-detail__count { font-size: 11px; color: var(--text-secondary); }
.topic-detail__close {
  background: none; border: none; color: var(--text-tertiary); cursor: pointer;
  padding: 2px; border-radius: var(--radius-sm);
}
.topic-detail__close:hover { background: var(--bg-tertiary); }
.topic-detail__summary { font-size: 12px; color: var(--text-secondary); line-height: 1.5; margin: 0 0 10px; }
.topic-detail__section { margin-bottom: 10px; }
.topic-detail__paper {
  display: flex; justify-content: space-between; align-items: center;
  padding: 4px 6px; border-radius: var(--radius-sm); font-size: 12px;
}
.topic-detail__paper:hover { background: var(--bg-hover); }
.topic-detail__paper-title { flex: 1; color: var(--text-primary); }
.topic-detail__paper-cit { font-size: 10px; color: var(--text-tertiary); flex-shrink: 0; margin-left: 8px; }
.topic-detail__list { margin: 0; padding: 0 0 0 16px; font-size: 12px; line-height: 1.5; }
.topic-detail__list--gap li { color: var(--warning); }
.topic-detail__list--novelty li { color: var(--success); }
</style>

<template>
  <div class="node-detail">
    <div class="detail-header">
      <span class="type-badge" :style="{ background: typeColor }">{{ node.node_type || node.type }}</span>
      <button class="detail-close" @click="$emit('close')">&times;</button>
    </div>

    <div class="detail-label">{{ node.label || node.id }}</div>

    <div class="detail-fields">
      <div class="detail-field" v-if="node.confidence != null">
        <span class="field-key">Confidence</span>
        <span class="field-val">{{ Math.round(node.confidence * 100) }}%</span>
      </div>

      <div class="detail-field" v-if="node.created_at_round != null">
        <span class="field-key">Added</span>
        <span class="field-val">Round {{ node.created_at_round }}</span>
      </div>

      <div class="detail-field" v-if="node.weight != null">
        <span class="field-key">Weight</span>
        <span class="field-val">{{ node.weight.toFixed(2) }}</span>
      </div>

      <!-- Type-specific fields -->
      <div class="detail-field" v-if="node.metadata?.doi">
        <span class="field-key">DOI</span>
        <span class="field-val mono">{{ node.metadata.doi }}</span>
      </div>

      <div class="detail-field" v-if="node.metadata?.institution">
        <span class="field-key">Institution</span>
        <span class="field-val">{{ node.metadata.institution }}</span>
      </div>

      <div class="detail-field" v-if="node.metadata?.method_type">
        <span class="field-key">Method</span>
        <span class="field-val">{{ node.metadata.method_type }}</span>
      </div>

      <div class="detail-field" v-if="node.metadata?.description">
        <span class="field-key">Description</span>
        <span class="field-val desc">{{ node.metadata.description }}</span>
      </div>

      <div class="detail-field" v-if="node.cluster_id">
        <span class="field-key">Cluster</span>
        <span class="field-val">{{ node.cluster_id }}</span>
      </div>
    </div>

    <!-- Connected edges summary -->
    <div class="detail-connections" v-if="connections.length > 0">
      <div class="conn-title">Connections ({{ connections.length }})</div>
      <div v-for="(conn, i) in connections.slice(0, 8)" :key="i" class="conn-item">
        <span class="conn-relation" :class="conn.relation">{{ conn.relation }}</span>
        <span class="conn-target">{{ conn.label }}</span>
      </div>
      <div v-if="connections.length > 8" class="conn-more">+{{ connections.length - 8 }} more</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const TYPE_COLORS = {
  paper: 'var(--mf-paper)',
  author: 'var(--mf-author)',
  institution: 'var(--mf-institution)',
  method: 'var(--mf-method)',
  claim: 'var(--mf-claim)',
  dataset: 'var(--mf-dataset)',
  experiment: 'var(--mf-experiment)',
  critique: 'var(--mf-critique)',
  open_question: 'var(--mf-open-question)',
  agent_persona: 'var(--mf-agent)',
  evidence_block: 'var(--mf-evidence)',
  option: 'var(--mf-option)',
}

const props = defineProps({
  node: { type: Object, required: true },
  graphSnapshot: { type: Object, default: null },
})

defineEmits(['close'])

const typeColor = computed(() => {
  return TYPE_COLORS[props.node.node_type || props.node.type] || 'var(--text-tertiary)'
})

const connections = computed(() => {
  if (!props.graphSnapshot) return []
  const edges = props.graphSnapshot.links || props.graphSnapshot.edges || []
  const nodes = props.graphSnapshot.nodes || []
  const nodeId = props.node.node_id || props.node.id
  const nodeMap = new Map(nodes.map(n => [n.node_id || n.id, n]))

  return edges
    .filter(e => {
      const src = typeof e.source === 'object' ? e.source.id || e.source.node_id : e.source
      const tgt = typeof e.target === 'object' ? e.target.id || e.target.node_id : e.target
      return src === nodeId || tgt === nodeId
    })
    .map(e => {
      const src = typeof e.source === 'object' ? e.source.id || e.source.node_id : e.source
      const tgt = typeof e.target === 'object' ? e.target.id || e.target.node_id : e.target
      const otherId = src === nodeId ? tgt : src
      const other = nodeMap.get(otherId)
      return {
        relation: e.relation || e.type,
        label: other?.label || otherId,
      }
    })
})
</script>

<style scoped>
.node-detail {
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  padding: 10px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.type-badge {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  color: white;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.detail-close {
  background: none;
  border: none;
  font-size: 18px;
  color: var(--text-tertiary);
  cursor: pointer;
  line-height: 1;
  padding: 0 4px;
}
.detail-close:hover { color: var(--text-primary); }

.detail-label {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
  line-height: 1.3;
}

.detail-fields {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
}

.detail-field {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}

.field-key {
  font-size: 11px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.field-val {
  font-size: 11px;
  color: var(--text-secondary);
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.field-val.mono { font-family: var(--font-mono); font-size: 10px; }
.field-val.desc { white-space: normal; text-align: left; font-size: 10px; }

.detail-connections {
  border-top: 1px solid var(--border-secondary);
  padding-top: 8px;
}

.conn-title {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

.conn-item {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 3px;
}

.conn-relation {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  color: var(--text-tertiary);
  font-weight: 500;
  flex-shrink: 0;
}
.conn-relation.supports { color: var(--mf-edge-supports); }
.conn-relation.contradicts { color: var(--mf-edge-contradicts); }
.conn-relation.extends { color: var(--mf-edge-extends); }
.conn-relation.critiques { color: var(--mf-edge-critiques); }

.conn-target {
  font-size: 11px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conn-more {
  font-size: 10px;
  color: var(--text-tertiary);
  font-style: italic;
  margin-top: 4px;
}
</style>

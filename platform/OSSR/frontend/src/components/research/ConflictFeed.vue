<template>
  <div class="conflict-feed">
    <!-- Disagreements -->
    <div class="cf-section" v-if="disagreements.length > 0">
      <div class="cf-title">Active Conflicts</div>
      <div v-for="(d, i) in disagreements" :key="'d-' + i" class="conflict-card">
        <div class="conflict-vs">
          <span class="conflict-claim">{{ truncate(d.claim_a, 50) }}</span>
          <span class="vs-badge">vs</span>
          <span class="conflict-claim">{{ truncate(d.claim_b, 50) }}</span>
        </div>
        <div class="conflict-meta">
          <span class="severity-bar">
            <span class="severity-fill" :style="{ width: ((d.severity || 0.5) * 100) + '%' }"></span>
          </span>
          <span class="rounds-active" v-if="d.rounds_active">{{ d.rounds_active }}R</span>
        </div>
      </div>
    </div>

    <!-- Coalitions -->
    <div class="cf-section" v-if="coalitions.length > 0">
      <div class="cf-title">Coalitions</div>
      <div v-for="(c, i) in coalitions" :key="'c-' + i" class="coalition-card">
        <div class="coalition-agents">
          <span v-for="agentId in (c.agent_ids || []).slice(0, 4)" :key="agentId" class="coalition-dot"></span>
          <span class="coalition-count">{{ c.agent_ids?.length || 0 }} agents</span>
        </div>
        <div class="coalition-positions" v-if="c.shared_positions?.length">
          <span v-for="pos in c.shared_positions" :key="pos" class="position-tag">{{ pos }}</span>
        </div>
        <div class="coalition-strength">
          Strength: {{ ((c.strength || 0) * 100).toFixed(0) }}%
        </div>
      </div>
    </div>

    <div v-if="disagreements.length === 0 && coalitions.length === 0" class="cf-empty">
      No conflicts or coalitions detected.
    </div>
  </div>
</template>

<script setup>
defineProps({
  disagreements: { type: Array, default: () => [] },
  coalitions: { type: Array, default: () => [] },
})

function truncate(text, max) {
  if (!text) return ''
  return text.length > max ? text.substring(0, max) + '...' : text
}
</script>

<style scoped>
.conflict-feed {
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  padding: 10px;
}

.cf-section { margin-bottom: 10px; }
.cf-section:last-child { margin-bottom: 0; }

.cf-title {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

.cf-empty {
  font-size: 12px;
  color: var(--text-tertiary);
  font-style: italic;
}

.conflict-card {
  padding: 6px 8px;
  background: var(--bg-primary);
  border: 1px solid var(--border-secondary);
  border-left: 3px solid var(--error);
  border-radius: var(--radius-sm);
  margin-bottom: 6px;
}

.conflict-vs {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.conflict-claim {
  font-size: 11px;
  color: var(--text-secondary);
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.vs-badge {
  font-size: 9px;
  font-weight: 700;
  color: var(--error);
  text-transform: uppercase;
  flex-shrink: 0;
}

.conflict-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
}

.severity-bar {
  flex: 1;
  height: 3px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}

.severity-fill {
  height: 100%;
  background: var(--error);
  border-radius: 2px;
}

.rounds-active {
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--text-tertiary);
}

.coalition-card {
  padding: 6px 8px;
  background: var(--bg-primary);
  border: 1px solid var(--border-secondary);
  border-left: 3px solid var(--info);
  border-radius: var(--radius-sm);
  margin-bottom: 6px;
}

.coalition-agents {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-bottom: 4px;
}

.coalition-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--os-brand);
}

.coalition-count {
  font-size: 10px;
  color: var(--text-tertiary);
  margin-left: 4px;
}

.coalition-positions {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-bottom: 4px;
}

.position-tag {
  font-size: 9px;
  padding: 1px 5px;
  background: rgba(var(--os-brand-rgb), 0.1);
  border-radius: var(--radius-pill);
  color: var(--os-brand);
}

.coalition-strength {
  font-size: 10px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
}
</style>

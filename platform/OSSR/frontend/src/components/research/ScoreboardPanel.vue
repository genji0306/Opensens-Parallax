<template>
  <div class="scoreboard-panel">
    <!-- Topic Summary -->
    <div class="sb-section">
      <div class="sb-section-title">Topic</div>
      <div class="topic-summary" v-if="frame">
        <div class="topic-name">{{ frame.topic }}</div>
        <div class="subtopics" v-if="frame.subtopics?.length">
          <span v-for="st in frame.subtopics" :key="st" class="subtopic-tag">{{ st }}</span>
        </div>
      </div>
      <div v-else class="sb-empty">No frame data</div>
    </div>

    <!-- Options Tracker -->
    <div class="sb-section">
      <div class="sb-section-title">Options</div>
      <div v-if="options.length > 0" class="options-list">
        <div v-for="opt in options" :key="opt.option_id" class="option-row">
          <div class="option-header">
            <span class="option-label">{{ opt.label }}</span>
            <span class="option-conf">{{ Math.round((opt.confidence || 0) * 100) }}%</span>
          </div>
          <div class="confidence-bar">
            <div
              class="confidence-fill"
              :class="opt.status || 'competitive'"
              :style="{ width: ((opt.confidence || 0) * 100) + '%' }"
            ></div>
          </div>
          <div class="option-meta">
            <span class="agent-count for">{{ opt.supporting_agents?.length || 0 }} for</span>
            <span class="agent-count against">{{ opt.opposing_agents?.length || 0 }} against</span>
            <span v-if="opt.status" class="status-tag" :class="opt.status">{{ opt.status }}</span>
          </div>
        </div>
      </div>
      <div v-else class="sb-empty">No options tracked</div>
    </div>

    <!-- Consensus -->
    <div class="sb-section">
      <div class="sb-section-title">Consensus</div>
      <div class="consensus-meter" v-if="scoreboard">
        <div class="consensus-bar">
          <div class="consensus-fill" :style="{ width: consensusPercent + '%' }"></div>
        </div>
        <div class="consensus-info">
          <span class="consensus-value">{{ consensusPercent }}%</span>
          <span class="consensus-trend" v-if="scoreboard.consensus_trend">
            {{ trendIcon(scoreboard.consensus_trend) }} {{ scoreboard.consensus_trend }}
          </span>
        </div>
      </div>
      <div v-else class="sb-empty">--</div>
    </div>

    <!-- Agent Influence -->
    <div class="sb-section">
      <div class="sb-section-title">Agent Influence</div>
      <div v-if="influences.length > 0" class="influence-list">
        <div v-for="inf in influences" :key="inf.agent_id" class="influence-row">
          <span class="inf-name">{{ inf.agent_name || inf.agent_id }}</span>
          <div class="inf-bar-wrap">
            <div class="inf-bar" :style="{ width: ((inf.influence_score || 0) * 100) + '%' }"></div>
          </div>
          <span class="inf-score">{{ (inf.influence_score || 0).toFixed(2) }}</span>
        </div>
      </div>
      <div v-else class="sb-empty">No influence data</div>
    </div>

    <!-- Round Stats -->
    <div class="sb-section" v-if="scoreboard">
      <div class="sb-section-title">Round Stats</div>
      <div class="stats-grid">
        <div class="stat-item">
          <span class="stat-value">{{ scoreboard.key_shifts_this_round?.length || 0 }}</span>
          <span class="stat-label">Shifts</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ scoreboard.major_disagreements?.length || 0 }}</span>
          <span class="stat-label">Conflicts</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ scoreboard.unresolved_questions?.length || 0 }}</span>
          <span class="stat-label">Open Q</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ scoreboard.coalitions?.length || 0 }}</span>
          <span class="stat-label">Coalitions</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  frame: { type: Object, default: null },
  scoreboard: { type: Object, default: null },
  currentRound: { type: Number, default: 0 },
})

const options = computed(() => {
  return props.scoreboard?.options || props.scoreboard?.option_scores || []
})

const consensusPercent = computed(() => {
  return Math.round((props.scoreboard?.consensus_level || 0) * 100)
})

const influences = computed(() => {
  return (props.scoreboard?.agent_influence || [])
    .slice()
    .sort((a, b) => (b.influence_score || 0) - (a.influence_score || 0))
})

function trendIcon(trend) {
  if (trend === 'converging') return '\u2197'
  if (trend === 'diverging') return '\u2198'
  return '\u2192'
}
</script>

<style scoped>
.scoreboard-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sb-section {
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  padding: 10px;
}

.sb-section-title {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--text-tertiary);
  margin-bottom: 8px;
}

.sb-empty {
  font-size: 12px;
  color: var(--text-tertiary);
  font-style: italic;
}

/* Topic */
.topic-name {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}

.subtopics {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.subtopic-tag {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: var(--radius-pill);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}

/* Options */
.options-list { display: flex; flex-direction: column; gap: 8px; }

.option-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.option-label {
  font-size: 12px;
  font-weight: 500;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.option-conf {
  font-size: 12px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--os-brand);
}

.confidence-bar {
  height: 4px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  margin: 4px 0;
  overflow: hidden;
}

.confidence-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s ease;
}
.confidence-fill.leading { background: var(--success); }
.confidence-fill.competitive { background: var(--os-brand); }
.confidence-fill.declining { background: var(--warning); }
.confidence-fill.eliminated { background: var(--text-tertiary); }

.option-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}

.agent-count {
  font-size: 10px;
  color: var(--text-tertiary);
}
.agent-count.for { color: var(--success); }
.agent-count.against { color: var(--error); }

.status-tag {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: var(--radius-pill);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.status-tag.leading { background: rgba(34,197,94,0.15); color: var(--success); }
.status-tag.competitive { background: rgba(var(--os-brand-rgb),0.15); color: var(--os-brand); }
.status-tag.declining { background: rgba(245,158,11,0.15); color: var(--warning); }
.status-tag.eliminated { background: var(--bg-tertiary); color: var(--text-tertiary); }

/* Consensus */
.consensus-bar {
  height: 6px;
  background: var(--bg-tertiary);
  border-radius: 3px;
  overflow: hidden;
}

.consensus-fill {
  height: 100%;
  background: var(--os-brand);
  border-radius: 3px;
  transition: width 0.5s ease;
}

.consensus-info {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
}

.consensus-value {
  font-size: 14px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--os-brand);
}

.consensus-trend {
  font-size: 11px;
  color: var(--text-secondary);
}

/* Influence */
.influence-list { display: flex; flex-direction: column; gap: 6px; }

.influence-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.inf-name {
  font-size: 11px;
  font-weight: 500;
  min-width: 60px;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.inf-bar-wrap {
  flex: 1;
  height: 4px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}

.inf-bar {
  height: 100%;
  background: var(--os-brand);
  border-radius: 2px;
  transition: width 0.5s ease;
}

.inf-score {
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--text-tertiary);
  min-width: 28px;
  text-align: right;
}

/* Stats */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
}

.stat-value {
  font-size: 16px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--text-primary);
}

.stat-label {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-tertiary);
}
</style>

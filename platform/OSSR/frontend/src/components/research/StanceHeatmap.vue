<template>
  <div class="stance-heatmap" v-if="agentIds.length > 0 && optionList.length > 0">
    <div class="hm-title">Stance Map</div>
    <div class="hm-grid">
      <!-- Header row: option labels -->
      <div class="hm-corner"></div>
      <div v-for="opt in optionList" :key="opt.option_id" class="hm-col-header" :title="opt.label">
        {{ shortLabel(opt.label) }}
      </div>

      <!-- Agent rows -->
      <template v-for="agentId in agentIds" :key="agentId">
        <div class="hm-row-header" :title="agentId">{{ shortAgent(agentId) }}</div>
        <div
          v-for="opt in optionList"
          :key="opt.option_id + '-' + agentId"
          class="hm-cell"
          :style="cellStyle(agentId, opt.option_id)"
          :title="cellTooltip(agentId, opt.option_id)"
        ></div>
      </template>
    </div>
    <div class="hm-legend">
      <span class="hm-leg-label">Against</span>
      <div class="hm-leg-gradient"></div>
      <span class="hm-leg-label">For</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  stances: { type: Array, default: () => [] },
  frame: { type: Object, default: null },
  currentRound: { type: Number, default: 0 },
})

const optionList = computed(() => {
  if (props.frame?.options) return props.frame.options
  // Infer from stances
  const seen = new Map()
  for (const s of props.stances) {
    if (s.option_id && !seen.has(s.option_id)) {
      seen.set(s.option_id, { option_id: s.option_id, label: s.option_id })
    }
  }
  return Array.from(seen.values())
})

const agentIds = computed(() => {
  const ids = new Set()
  for (const s of props.stances) {
    if (s.agent_id) ids.add(s.agent_id)
  }
  return Array.from(ids)
})

// Build a lookup: stanceMap[agentId][optionId] = { position, confidence }
const stanceMap = computed(() => {
  const map = {}
  const round = props.currentRound || Infinity
  for (const s of props.stances) {
    if (s.round_num > round) continue
    const key = `${s.agent_id}|${s.option_id}`
    if (!map[key] || s.round_num > map[key].round_num) {
      map[key] = s
    }
  }
  return map
})

function getStance(agentId, optionId) {
  return stanceMap.value[`${agentId}|${optionId}`] || null
}

function cellStyle(agentId, optionId) {
  const s = getStance(agentId, optionId)
  if (!s) return { background: 'var(--bg-tertiary)', opacity: 0.3 }

  const pos = s.position ?? 0 // -1 to +1
  const conf = s.confidence ?? 0.5

  // Map position to hue: -1 = red (0), 0 = yellow (55), +1 = green (145)
  const hue = Math.round(((pos + 1) / 2) * 145)
  const sat = 70
  const light = 45

  return {
    background: `hsl(${hue}, ${sat}%, ${light}%)`,
    opacity: 0.3 + conf * 0.7,
  }
}

function cellTooltip(agentId, optionId) {
  const s = getStance(agentId, optionId)
  if (!s) return `${shortAgent(agentId)} — ${optionId}: no data`
  return `${shortAgent(agentId)} — ${optionId}\nPosition: ${s.position?.toFixed(2)}\nConfidence: ${s.confidence?.toFixed(2)}\nRound: ${s.round_num}`
}

function shortLabel(label) {
  if (!label) return '?'
  return label.length > 8 ? label.substring(0, 7) + '.' : label
}

function shortAgent(agentId) {
  if (!agentId) return '?'
  // Try to extract name portion
  const parts = agentId.split('-')
  return parts[0].substring(0, 6)
}
</script>

<style scoped>
.stance-heatmap {
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  padding: 10px;
}

.hm-title {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--text-tertiary);
  margin-bottom: 8px;
}

.hm-grid {
  display: grid;
  grid-template-columns: 50px repeat(v-bind('optionList.length'), 1fr);
  gap: 2px;
}

.hm-corner {
  /* empty top-left corner */
}

.hm-col-header {
  font-size: 9px;
  color: var(--text-tertiary);
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 2px 0;
}

.hm-row-header {
  font-size: 9px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hm-cell {
  height: 18px;
  border-radius: 2px;
  transition: all var(--transition-fast);
  cursor: default;
}
.hm-cell:hover {
  outline: 1px solid var(--text-primary);
  z-index: 1;
}

.hm-legend {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  justify-content: center;
}

.hm-leg-label {
  font-size: 9px;
  color: var(--text-tertiary);
}

.hm-leg-gradient {
  width: 60px;
  height: 6px;
  border-radius: 3px;
  background: linear-gradient(to right, hsl(0, 70%, 45%), hsl(55, 70%, 45%), hsl(145, 70%, 45%));
}
</style>

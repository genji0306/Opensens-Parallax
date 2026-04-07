<script setup lang="ts">
import { computed } from 'vue'
import type { StageInfo, StageId } from '@/types/pipeline'

const props = defineProps<{
  stages: StageInfo[]
  activeStage?: StageId
}>()

const emit = defineEmits<{
  'stage-click': [stageId: StageId]
}>()

function statusIcon(status: string): string {
  switch (status) {
    case 'done': return 'check'
    case 'active': return 'arrow_forward'
    case 'failed': return 'close'
    case 'skipped': return 'remove'
    case 'invalidated': return 'restart_alt'
    default: return ''
  }
}

/*
 * V2 DAG Layout — two parallel tracks from Map:
 *
 * TOP ROW:    Search → Map → Debate → Validate ←─── (feedback from Revise)
 *                       |  /               |                  |
 * BOTTOM ROW:        Ideas → Draft → Experiment → Revise → Pass
 *                                    (if needed)       (if high score)
 */

const topRowIds: StageId[] = ['crawl', 'map', 'debate', 'validate']
const bottomRowIds: StageId[] = ['ideas', 'draft', 'experiment', 'rehab', 'pass']

const topRow = computed(() => {
  const ordered = topRowIds.filter(id => props.stages.some(s => s.id === id))
  return ordered.map(id => props.stages.find(s => s.id === id)!)
})

const bottomRow = computed(() => {
  const ordered = bottomRowIds.filter(id => props.stages.some(s => s.id === id))
  // Include any stages not in either row
  const extra = props.stages.filter(s => !topRowIds.includes(s.id) && !bottomRowIds.includes(s.id))
  return [...ordered.map(id => props.stages.find(s => s.id === id)!), ...extra]
})


</script>

<template>
  <div class="pipeline-tracker">
    <!-- Top row: main flow -->
    <div class="pipeline-tracker__row pipeline-tracker__row--main">
      <template v-for="(stage, i) in topRow" :key="stage.id">
        <div
          v-if="i > 0"
          class="pipeline-tracker__connector"
          :class="{
            'pipeline-tracker__connector--done': topRow[i - 1]?.status === 'done',
            'pipeline-tracker__connector--active': topRow[i - 1]?.status === 'done' && stage.status === 'active',
            'pipeline-tracker__connector--pending': stage.status === 'pending' || stage.status === 'skipped',
            'pipeline-tracker__connector--failed': stage.status === 'failed',
          }"
        />
        <button
          class="pipeline-tracker__node"
          :class="[
            `pipeline-tracker__node--${stage.status}`,
            { 'pipeline-tracker__node--current': activeStage === stage.id },
          ]"
          :title="stage.description || stage.label"
          @click="emit('stage-click', stage.id)"
        >
          <span class="pipeline-tracker__circle">
            <span
              v-if="statusIcon(stage.status)"
              class="material-symbols-outlined pipeline-tracker__icon"
            >{{ statusIcon(stage.status) }}</span>
            <span
              v-else
              class="material-symbols-outlined pipeline-tracker__icon pipeline-tracker__icon--stage"
            >{{ stage.icon }}</span>
          </span>
          <span class="pipeline-tracker__label">{{ stage.shortLabel || stage.label }}</span>
          <span v-if="stage.metric" class="pipeline-tracker__metric">{{ stage.metric }}</span>
        </button>
      </template>
    </div>

    <!-- Branch connectors: Map↓Ideas (left) and Revise↑Validate (right, feedback) -->
    <div v-if="bottomRow.length > 0" class="pipeline-tracker__branch">
      <!-- Map → Ideas (branch down-left) -->
      <svg class="pipeline-tracker__branch-svg pipeline-tracker__branch-svg--left" viewBox="0 0 100 36">
        <path
          d="M 50 0 L 50 18 L 10 18 L 10 36"
          fill="none"
          :stroke="bottomRow[0]?.status === 'done' || bottomRow[0]?.status === 'active' ? 'var(--os-brand)' : 'var(--border-primary)'"
          stroke-width="2"
        />
      </svg>
      <!-- Revise → Validate (feedback loop, dashed arrow going up-right) -->
      <svg class="pipeline-tracker__branch-svg pipeline-tracker__branch-svg--right" viewBox="0 0 120 36">
        <path
          d="M 10 36 L 10 18 L 100 18 L 100 0"
          fill="none"
          stroke="var(--warning, #f59e0b)"
          stroke-width="1.5"
          stroke-dasharray="5,3"
        />
        <polygon
          points="95,4 100,0 105,4"
          fill="var(--warning, #f59e0b)"
        />
      </svg>
    </div>

    <!-- Bottom row: debate branch -->
    <div v-if="bottomRow.length > 0" class="pipeline-tracker__row pipeline-tracker__row--branch">
      <template v-for="(stage, i) in bottomRow" :key="stage.id">
        <div
          v-if="i > 0"
          class="pipeline-tracker__connector"
          :class="{
            'pipeline-tracker__connector--done': bottomRow[i - 1]?.status === 'done',
            'pipeline-tracker__connector--active': bottomRow[i - 1]?.status === 'done' && stage.status === 'active',
            'pipeline-tracker__connector--pending': stage.status === 'pending' || stage.status === 'skipped',
            'pipeline-tracker__connector--failed': stage.status === 'failed',
          }"
        />
        <button
          class="pipeline-tracker__node"
          :class="[
            `pipeline-tracker__node--${stage.status}`,
            { 'pipeline-tracker__node--current': activeStage === stage.id },
          ]"
          :title="stage.description || stage.label"
          @click="emit('stage-click', stage.id)"
        >
          <span class="pipeline-tracker__circle">
            <span
              v-if="statusIcon(stage.status)"
              class="material-symbols-outlined pipeline-tracker__icon"
            >{{ statusIcon(stage.status) }}</span>
            <span
              v-else
              class="material-symbols-outlined pipeline-tracker__icon pipeline-tracker__icon--stage"
            >{{ stage.icon }}</span>
          </span>
          <span class="pipeline-tracker__label">{{ stage.shortLabel || stage.label }}</span>
          <span v-if="stage.metric" class="pipeline-tracker__metric">{{ stage.metric }}</span>
        </button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.pipeline-tracker {
  width: 100%;
  overflow-x: auto;
  overflow-y: visible;
  padding: 8px 0 4px;
  -webkit-overflow-scrolling: touch;
  display: flex;
  flex-direction: column;
  gap: 0;
  position: relative;
}

.pipeline-tracker::-webkit-scrollbar {
  height: 3px;
}

/* ── Row layout ── */
.pipeline-tracker__row {
  display: flex;
  align-items: flex-start;
  min-width: max-content;
  gap: 0;
  padding: 0 4px;
}

.pipeline-tracker__row--branch {
  padding-left: 40px;
}

/* ── Branch connector SVGs ── */
.pipeline-tracker__branch {
  height: 36px;
  position: relative;
  display: flex;
  justify-content: space-between;
  padding: 0 20px;
}

.pipeline-tracker__branch-svg {
  height: 36px;
  flex-shrink: 0;
}

.pipeline-tracker__branch-svg--left {
  width: 100px;
}

.pipeline-tracker__branch-svg--right {
  width: 120px;
}

/* ── Connector ── */
.pipeline-tracker__connector {
  width: 32px;
  height: 2px;
  margin-top: 15px;
  flex-shrink: 0;
  border-radius: 1px;
  transition: background var(--transition-normal);
}

.pipeline-tracker__connector--done,
.pipeline-tracker__connector--active {
  background: var(--os-brand);
}

.pipeline-tracker__connector--pending {
  background: repeating-linear-gradient(
    90deg,
    var(--border-primary) 0,
    var(--border-primary) 4px,
    transparent 4px,
    transparent 8px
  );
}

.pipeline-tracker__connector--failed {
  background: var(--error);
}

/* ── Node ── */
.pipeline-tracker__node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  flex-shrink: 0;
  min-width: 48px;
  transition: transform var(--transition-fast);
}

.pipeline-tracker__node:hover {
  transform: translateY(-1px);
}

/* ── Circle ── */
.pipeline-tracker__circle {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--border-primary);
  background: var(--bg-primary);
  transition:
    background var(--transition-normal),
    border-color var(--transition-normal),
    box-shadow var(--transition-normal),
    transform var(--transition-normal);
}

/* Done */
.pipeline-tracker__node--done .pipeline-tracker__circle {
  background: var(--os-brand);
  border-color: var(--os-brand);
}

.pipeline-tracker__node--done .pipeline-tracker__icon {
  color: var(--text-on-brand);
  font-size: 16px;
}

/* Active */
.pipeline-tracker__node--active .pipeline-tracker__circle {
  width: 34px;
  height: 34px;
  background: var(--os-brand);
  border-color: var(--os-brand);
  animation: stage-pulse 2s ease-in-out infinite;
}

.pipeline-tracker__node--active .pipeline-tracker__icon {
  color: var(--text-on-brand);
  font-size: 16px;
}

/* Pending */
.pipeline-tracker__node--pending .pipeline-tracker__circle {
  background: transparent;
  border-color: var(--border-primary);
  border-style: solid;
}

.pipeline-tracker__node--pending .pipeline-tracker__icon {
  color: var(--text-tertiary);
  font-size: 14px;
}

/* Failed */
.pipeline-tracker__node--failed .pipeline-tracker__circle {
  background: var(--error);
  border-color: var(--error);
}

.pipeline-tracker__node--failed .pipeline-tracker__icon {
  color: var(--text-on-brand);
  font-size: 16px;
}

/* Skipped */
.pipeline-tracker__node--skipped .pipeline-tracker__circle {
  background: transparent;
  border-color: var(--text-tertiary);
  border-style: dashed;
}

.pipeline-tracker__node--skipped .pipeline-tracker__icon {
  color: var(--text-tertiary);
  font-size: 14px;
}

/* Invalidated (V2) */
.pipeline-tracker__node--invalidated .pipeline-tracker__circle {
  background: transparent;
  border-color: var(--warning, #f59e0b);
  border-style: dashed;
}

.pipeline-tracker__node--invalidated .pipeline-tracker__icon {
  color: var(--warning, #f59e0b);
  font-size: 14px;
}

/* ── Icon defaults ── */
.pipeline-tracker__icon {
  font-size: 14px;
  font-variation-settings: 'FILL' 0, 'wght' 500, 'GRAD' 0, 'opsz' 20;
  line-height: 1;
}

.pipeline-tracker__icon--stage {
  color: var(--text-tertiary);
}

/* ── Labels ── */
.pipeline-tracker__label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  line-height: 1;
}

.pipeline-tracker__node--active .pipeline-tracker__label {
  color: var(--os-brand);
}

.pipeline-tracker__node--done .pipeline-tracker__label {
  color: var(--os-brand);
}

.pipeline-tracker__node--failed .pipeline-tracker__label {
  color: var(--error);
}

.pipeline-tracker__node--invalidated .pipeline-tracker__label {
  color: var(--warning, #f59e0b);
}

.pipeline-tracker__metric {
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--text-tertiary);
  line-height: 1;
}

@keyframes stage-pulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--os-brand-subtle, rgba(30, 168, 142, 0.3)); }
  50% { box-shadow: 0 0 0 6px transparent; }
}
</style>

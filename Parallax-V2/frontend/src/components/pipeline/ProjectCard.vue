<script setup lang="ts">
import { computed } from 'vue'
import type { ProjectSummary } from '@/types/pipeline'
import { STAGE_ORDER, statusToBadgeStatus } from '@/types/pipeline'
import GlassPanel from '@/components/shared/GlassPanel.vue'
import ProgressBar from '@/components/shared/ProgressBar.vue'
import StatusBadge from '@/components/shared/StatusBadge.vue'

const props = defineProps<{
  project: ProjectSummary
}>()

const emit = defineEmits<{
  select: []
}>()

const typeBadgeColor: Record<string, string> = {
  debate: 'var(--info)',
  ais: 'var(--os-brand)',
  paper: 'var(--os-tertiary)',
  paper_rehab: 'var(--os-tertiary)',
  report: 'var(--role-phd)',
}

const typeBadgeLabel: Record<string, string> = {
  debate: 'Debate',
  ais: 'AiS Pipeline',
  paper: 'Paper Rehab',
  paper_rehab: 'Paper Rehab',
  report: 'Report',
}

const stageProgress = computed(() => {
  if (!props.project.stage_results) return 0
  const sr = props.project.stage_results
  const completed = STAGE_ORDER.filter((s) => {
    const val = sr[s]
    if (val == null) return false
    // Empty objects {} do not count as completed
    if (typeof val === 'object' && !Array.isArray(val) && Object.keys(val).length === 0) return false
    return true
  }).length
  return Math.round((completed / STAGE_ORDER.length) * 100)
})

const statusForBadge = computed(() => {
  return statusToBadgeStatus(props.project.status)
})

const elapsedText = computed(() => {
  const updated = props.project.updated_at
  if (!updated) return ''
  const diff = Date.now() - new Date(updated).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
})

const truncatedTopic = computed(() => {
  const t = props.project.topic || ''
  return t.length > 80 ? t.slice(0, 80) + '...' : t
})
</script>

<template>
  <GlassPanel
    class="project-card"
    padding="12px 16px"
    @click="emit('select')"
  >
    <div class="project-card__top">
      <span class="project-card__title">{{ project.title || truncatedTopic }}</span>
      <StatusBadge :status="statusForBadge" size="sm" />
    </div>

    <p v-if="project.topic" class="project-card__topic">{{ truncatedTopic }}</p>

    <div class="project-card__meta">
      <span
        class="project-card__type"
        :style="{ '--badge-color': typeBadgeColor[project.type] || 'var(--text-tertiary)' }"
      >
        {{ typeBadgeLabel[project.type] || project.type }}
      </span>

      <span class="project-card__time">{{ elapsedText }}</span>
    </div>

    <div class="project-card__progress">
      <ProgressBar :progress="stageProgress" height="3px" />
      <span class="project-card__progress-label">{{ stageProgress }}%</span>
    </div>
  </GlassPanel>
</template>

<style scoped>
.project-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: pointer;
  transition:
    transform var(--transition-fast),
    box-shadow var(--transition-fast),
    border-color var(--transition-fast);
}

.project-card:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
  border-color: var(--os-brand-subtle);
}

.project-card:active {
  transform: translateY(0);
}

/* ── Top row ── */
.project-card__top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.project-card__title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}

/* ── Topic ── */
.project-card__topic {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── Meta row ── */
.project-card__meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.project-card__type {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--badge-color);
  background: color-mix(in srgb, var(--badge-color) 10%, transparent);
  padding: 2px 7px;
  border-radius: var(--radius-pill);
}

.project-card__time {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-tertiary);
  margin-left: auto;
}

/* ── Progress ── */
.project-card__progress {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}

.project-card__progress-label {
  font-size: 10px;
  font-family: var(--font-mono);
  font-weight: 500;
  color: var(--text-tertiary);
  flex-shrink: 0;
  min-width: 28px;
  text-align: right;
}
</style>

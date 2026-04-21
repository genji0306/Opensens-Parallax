<script setup lang="ts">
import { computed, ref } from 'vue'
import type { VisualizationArtifact } from '@/api/paperLab'
import ActionButton from '@/components/shared/ActionButton.vue'

const props = defineProps<{
  artifacts: VisualizationArtifact[]
  loading?: boolean
}>()

const emit = defineEmits<{
  refresh: []
  select: [artifact: VisualizationArtifact]
  render: [artifact: VisualizationArtifact]
  audit: [artifact: VisualizationArtifact]
  export: [artifact: VisualizationArtifact]
}>()

const query = ref('')
const activeType = ref<'all' | VisualizationArtifact['type']>('all')

const typeOptions = computed(() => {
  const types = Array.from(new Set(props.artifacts.map(artifact => artifact.type)))
  return ['all', ...types] as Array<'all' | VisualizationArtifact['type']>
})

const filteredArtifacts = computed(() => {
  const q = query.value.trim().toLowerCase()
  return props.artifacts.filter((artifact) => {
    const typeMatch = activeType.value === 'all' || artifact.type === activeType.value
    const queryMatch = !q
      || artifact.title.toLowerCase().includes(q)
      || artifact.intent.toLowerCase().includes(q)
      || artifact.status.toLowerCase().includes(q)
    return typeMatch && queryMatch
  })
})
</script>

<template>
  <section class="artifact-inventory">
    <div class="artifact-inventory__header">
      <div>
        <h4>Artifact Inventory</h4>
        <p>Persisted visuals, communication outputs, and readiness state.</p>
      </div>
      <ActionButton variant="secondary" size="sm" icon="refresh" :loading="loading" @click="emit('refresh')">Refresh</ActionButton>
    </div>

    <div v-if="artifacts.length" class="artifact-toolbar">
      <input v-model="query" type="text" placeholder="Search artifacts" class="artifact-toolbar__search" />
      <div class="artifact-toolbar__filters">
        <button
          v-for="type in typeOptions"
          :key="type"
          class="artifact-filter"
          :class="{ 'artifact-filter--active': activeType === type }"
          @click="activeType = type"
        >
          {{ type }}
        </button>
      </div>
    </div>

    <div v-if="!artifacts.length" class="artifact-empty">
      No visualization artifacts yet. Create one from the plan below or from the legacy analysis tools.
    </div>

    <div v-else-if="!filteredArtifacts.length" class="artifact-empty">
      No artifacts match the current search or type filter.
    </div>

    <div v-else class="artifact-list">
      <article v-for="artifact in filteredArtifacts" :key="artifact.artifact_id" class="artifact-card">
        <button class="artifact-card__main" @click="emit('select', artifact)">
          <div>
            <p class="artifact-card__eyebrow">{{ artifact.type }} · {{ artifact.intent }}</p>
            <h5>{{ artifact.title }}</h5>
            <p class="artifact-card__status">
              Status: <strong>{{ artifact.status }}</strong>
              <span v-if="artifact.audit?.consistency_status"> · Audit: {{ artifact.audit.consistency_status }}</span>
            </p>
          </div>
          <span class="artifact-card__version">v{{ artifact.version }}</span>
        </button>

        <div class="artifact-card__actions">
          <ActionButton variant="ghost" size="sm" icon="insert_chart" @click="emit('render', artifact)">Render</ActionButton>
          <ActionButton variant="ghost" size="sm" icon="fact_check" @click="emit('audit', artifact)">Audit</ActionButton>
          <ActionButton variant="ghost" size="sm" icon="download" @click="emit('export', artifact)">Export</ActionButton>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.artifact-inventory {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.artifact-inventory__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.artifact-inventory__header h4 {
  margin: 0;
  font-size: 14px;
  color: var(--text-primary);
}

.artifact-inventory__header p,
.artifact-empty {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.artifact-toolbar {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.artifact-toolbar__search {
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  background: rgba(0, 0, 0, 0.2);
  color: var(--text-primary);
  padding: 10px 12px;
  font: inherit;
}

.artifact-toolbar__filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.artifact-filter {
  border: 1px solid var(--border-secondary);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-secondary);
  padding: 6px 10px;
  font-size: 11px;
  text-transform: capitalize;
  cursor: pointer;
}

.artifact-filter--active {
  border-color: var(--os-brand);
  color: var(--os-brand);
  background: rgba(204, 255, 0, 0.08);
}

.artifact-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.artifact-card {
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-lg);
  background: var(--bg-secondary);
}

.artifact-card__main {
  width: 100%;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  background: none;
  border: none;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.artifact-card__eyebrow {
  margin: 0 0 4px;
  font-size: 10px;
  color: var(--os-brand);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.artifact-card h5 {
  margin: 0 0 4px;
  font-size: 13px;
  color: var(--text-primary);
}

.artifact-card__status,
.artifact-card__version {
  margin: 0;
  font-size: 11px;
  color: var(--text-secondary);
}

.artifact-card__actions {
  display: flex;
  gap: 6px;
  padding: 0 14px 14px;
  flex-wrap: wrap;
}
</style>

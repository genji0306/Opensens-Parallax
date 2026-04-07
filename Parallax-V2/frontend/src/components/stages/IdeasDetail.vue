<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import ProgressBar from '@/components/shared/ProgressBar.vue'
import ActionButton from '@/components/shared/ActionButton.vue'
import { selectIdea, getIdeas } from '@/api/ais'
import { usePipelineStore } from '@/stores/pipeline'

const props = defineProps<{
  result: Record<string, unknown>
  runId?: string
}>()

const pipeline = usePipelineStore()
const selectingId = ref<string | null>(null)
const selectedIdeaId = ref<string | null>(null)
const fetchedIdeas = ref<Idea[]>([])
const loadingIdeas = ref(false)
const error = ref<string | null>(null)

interface Idea {
  id: string
  title: string
  hypothesis?: string
  composite_score: number
  scores?: {
    novelty: number
    feasibility: number
    interestingness: number
    debate_support: number
  }
}

async function fetchIdeas() {
  if (!props.runId) return
  loadingIdeas.value = true
  try {
    const res = await getIdeas(props.runId)
    const data = res.data?.data
    // Backend may return { ideas: [...] } or [...] directly
    const dataObj = data as unknown as Record<string, unknown> | null | undefined
    const raw = dataObj?.ideas ?? data
    if (Array.isArray(raw)) {
      fetchedIdeas.value = raw.map((i: Record<string, unknown>) => ({
        id: (i.idea_id ?? i.id) as string,
        title: i.title as string,
        hypothesis: i.hypothesis as string | undefined,
        composite_score: (i.composite_score ?? 0) as number,
        scores: i.novelty != null ? {
          novelty: (i.novelty ?? 0) as number,
          feasibility: (i.feasibility ?? 0) as number,
          interestingness: (i.interestingness ?? 0) as number,
          debate_support: (i.debate_support ?? 0) as number,
        } : (i.scores as Idea['scores']),
      }))
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to fetch ideas'
    console.error('Failed to fetch ideas:', err)
  } finally {
    loadingIdeas.value = false
  }
}

onMounted(fetchIdeas)
watch(() => props.runId, fetchIdeas)

const ideas = computed<Idea[]>(() => {
  // Prefer fetched ideas from API, fall back to result
  if (fetchedIdeas.value.length > 0) {
    return [...fetchedIdeas.value].sort((a, b) => b.composite_score - a.composite_score)
  }
  // Normalize: result may be { ideas: [...] } or the array may be at root level
  let raw: unknown = props.result?.ideas
  if (!raw || !Array.isArray(raw)) {
    // Check if result itself is an array (root-level format)
    const resultAsArray = props.result as unknown
    if (Array.isArray(resultAsArray)) {
      raw = resultAsArray
    }
  }
  if (!raw || !Array.isArray(raw)) return []
  return [...(raw as Idea[])].sort((a, b) => (b.composite_score ?? 0) - (a.composite_score ?? 0))
})

const persistedSelectedIdeaId = computed(() => {
  const fromResult = props.result.selected_idea_id
  if (typeof fromResult === 'string' && fromResult) return fromResult
  const fromStore = pipeline.stageResults['selected_idea_id']
  return typeof fromStore === 'string' && fromStore ? fromStore : null
})

watch(
  persistedSelectedIdeaId,
  (ideaId) => {
    selectedIdeaId.value = ideaId
  },
  { immediate: true },
)

function scoreColor(score: number): string {
  if (score >= 7) return 'var(--success)'
  if (score >= 5) return 'var(--os-brand)'
  if (score >= 3) return 'var(--warning)'
  return 'var(--error)'
}

const scoreLabels: Array<{ key: keyof NonNullable<Idea['scores']>; label: string; icon: string }> = [
  { key: 'novelty', label: 'Novelty', icon: 'new_releases' },
  { key: 'feasibility', label: 'Feasibility', icon: 'build' },
  { key: 'interestingness', label: 'Interest', icon: 'star' },
  { key: 'debate_support', label: 'Debate', icon: 'forum' },
]

async function handleSelect(ideaId: string) {
  if (!props.runId) return
  selectingId.value = ideaId
  error.value = null
  try {
    await selectIdea(props.runId, ideaId)
    selectedIdeaId.value = ideaId
    // Refresh pipeline so debate stage knows an idea is selected
    await pipeline.refreshStages()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to select idea'
    console.error('Failed to select idea:', err)
  } finally {
    selectingId.value = null
  }
}
</script>

<template>
  <div class="ideas-detail">
    <div v-if="error" class="ideas-detail__error">
      <span class="material-symbols-outlined" style="font-size: 16px; color: var(--error)">error</span>
      <span>{{ error }}</span>
    </div>
    <template v-if="ideas.length > 0">
      <div class="ideas-grid">
        <div
          v-for="(idea, idx) in ideas"
          :key="idea.id"
          class="idea-card"
          :class="{
            'idea-card--top': idx === 0 && !selectedIdeaId,
            'idea-card--selected': selectedIdeaId === idea.id,
          }"
        >
          <div class="idea-card__header">
            <span class="idea-card__rank font-mono">#{{ idx + 1 }}</span>
            <span
              class="idea-card__score font-mono"
              :style="{ color: scoreColor(idea.composite_score) }"
            >
              {{ idea.composite_score.toFixed(1) }}
            </span>
          </div>

          <h5 class="idea-card__title">{{ idea.title }}</h5>
          <p v-if="idea.hypothesis" class="idea-card__hypothesis">{{ idea.hypothesis }}</p>

          <!-- Score Bars -->
          <div v-if="idea.scores" class="idea-card__scores">
            <div
              v-for="sl in scoreLabels"
              :key="sl.key"
              class="score-row"
            >
              <div class="score-row__label">
                <span class="material-symbols-outlined" style="font-size: 14px">{{ sl.icon }}</span>
                <span>{{ sl.label }}</span>
              </div>
              <ProgressBar
                :progress="(idea.scores![sl.key] ?? 0) * 10"
                :color="scoreColor(idea.scores![sl.key] ?? 0)"
                height="4px"
              />
              <span class="score-row__value font-mono">
                {{ (idea.scores![sl.key] ?? 0).toFixed(1) }}
              </span>
            </div>
          </div>

          <ActionButton
            v-if="runId"
            :variant="selectedIdeaId === idea.id ? 'primary' : 'secondary'"
            size="sm"
            :icon="selectedIdeaId === idea.id ? 'check_circle' : 'check'"
            :loading="selectingId === idea.id"
            :disabled="selectedIdeaId === idea.id"
            class="idea-card__select"
            @click="handleSelect(idea.id)"
          >
            {{ selectedIdeaId === idea.id ? 'Selected' : 'Select' }}
          </ActionButton>
        </div>
      </div>
    </template>

    <div v-else class="ideas-detail__empty">
      <span class="material-symbols-outlined" style="font-size: 24px; color: var(--text-tertiary)">lightbulb</span>
      <span>No ideas generated yet</span>
    </div>
  </div>
</template>

<style scoped>
.ideas-detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 14px;
}

.ideas-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.idea-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.idea-card:hover {
  border-color: var(--border-primary);
  box-shadow: var(--shadow-sm);
}

.idea-card--top {
  border-color: var(--os-brand);
  background: var(--bg-active);
}

.idea-card--selected {
  border-color: var(--success);
  background: color-mix(in srgb, var(--success) 5%, var(--bg-secondary));
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--success) 20%, transparent);
}

.idea-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.idea-card__rank {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-tertiary);
}

.idea-card__score {
  font-size: 18px;
  font-weight: 700;
}

.idea-card__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.4;
}

.idea-card__hypothesis {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── Score Bars ── */
.idea-card__scores {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
}

.score-row {
  display: grid;
  grid-template-columns: 80px 1fr 30px;
  gap: 8px;
  align-items: center;
}

.score-row__label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.score-row__value {
  font-size: 10px;
  color: var(--text-secondary);
  text-align: right;
}

.idea-card__select {
  margin-top: 4px;
  align-self: flex-end;
}

.ideas-detail__empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 20px;
  color: var(--text-tertiary);
  font-size: 13px;
  justify-content: center;
}

.ideas-detail__error {
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
</style>

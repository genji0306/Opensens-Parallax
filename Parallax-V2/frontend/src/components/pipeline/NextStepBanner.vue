<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import GlassPanel from '@/components/shared/GlassPanel.vue'
import ActionButton from '@/components/shared/ActionButton.vue'
import type { ProjectSummary } from '@/types/pipeline'
import { getCostEstimate } from '@/api/ais'

const props = defineProps<{
  project: ProjectSummary | null
  pipeline: any // the pipeline store
}>()

const emit = defineEmits<{
  (e: 'action', actionKey: string): void
}>()

const router = useRouter()

const costEstimate = ref<number | null>(null)
const costAction = ref<string>('')

const recommendation = computed(() => {
  if (!props.project || !props.pipeline) return null

  const p = props.pipeline
  const stages = p.stages || {}

  if (!stages['search'] || stages['search'].status !== 'completed') {
    costAction.value = 'full_pipeline'
    return {
      title: 'Start Research Crawl',
      description: 'Initialize semantic search to gather key papers before proceeding.',
      action: 'start_search',
      button: 'Start Crawl'
    }
  }

  if (!stages['debate'] || stages['debate'].status !== 'completed') {
    costAction.value = 'debate_20_5'
    return {
      title: 'Launch Multi-Agent Debate',
      description: 'Run a multi-round adversarial debate to stress-test your research claims.',
      action: 'start_debate',
      button: 'Launch Debate'
    }
  }

  if (!stages['draft'] || stages['draft'].status !== 'completed') {
    costAction.value = 'paper_draft'
    return {
      title: 'Generate Initial Draft',
      description: 'Synthesize debate findings into a structured manuscript draft.',
      action: 'start_draft',
      button: 'Generate Draft'
    }
  }

  if (p.draftScore !== null && p.draftScore < 6) {
    costAction.value = 'paper_rehab_3'
    return {
      title: `Send to Paper Lab — Score is ${p.draftScore}/10`,
      description: 'Draft score is below threshold. Refine with adversarial review in Paper Lab.',
      action: 'send_paper_lab',
      button: 'Open Paper Lab'
    }
  }

  return {
    title: 'Ready for Review or Export',
    description: 'Pipeline complete. Export your draft or start a new project.',
    action: 'export_or_new',
    button: 'Export Draft'
  }
})

watch(() => costAction.value, async (newAction) => {
  if (!newAction) return
  try {
    const res = await getCostEstimate({ action: newAction })
    if (res.data?.success && res.data?.data) {
      costEstimate.value = res.data.data.estimated_cost_usd
    }
  } catch (err) {
    console.error('Failed to get cost estimate', err)
  }
}, { immediate: true })

function handleAction() {
  const r = recommendation.value
  if (!r) return
  if (r.action === 'send_paper_lab') {
    router.push({ name: 'paper-lab', query: { upload_id: props.project?.run_id } })
  } else if (r.action === 'export_or_new') {
    router.push({ name: 'project', params: { runId: props.project?.run_id } })
  } else {
    emit('action', r.action)
    router.push({ name: 'project', params: { runId: props.project?.run_id } })
  }
}
</script>

<template>
  <GlassPanel v-if="recommendation" elevated padding="20px" class="next-step-banner">
    <div class="nsb-content">
      <div class="nsb-text">
        <span class="nsb-label">RECOMMENDED NEXT STEP</span>
        <h3 class="nsb-title">{{ recommendation.title }}</h3>
        <p class="nsb-description">{{ recommendation.description }}</p>
      </div>
      
      <div class="nsb-actions">
        <div v-if="costEstimate !== null" class="nsb-cost-badge">
          <span class="material-symbols-outlined">payments</span>
          ~${{ costEstimate.toFixed(2) }}
        </div>
        <ActionButton variant="primary" icon="play_arrow" @click="handleAction">
          {{ recommendation.button }}
        </ActionButton>
      </div>
    </div>
  </GlassPanel>
</template>

<style scoped>
.next-step-banner {
  border-left: 4px solid var(--os-brand);
  background: var(--bg-active);
}

.nsb-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.nsb-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nsb-label {
  font-size: 10px;
  font-family: var(--font-mono);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--os-brand);
}

.nsb-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.nsb-description {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.nsb-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nsb-cost-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 600;
  font-family: var(--font-mono);
  color: var(--text-secondary);
}

.nsb-cost-badge .material-symbols-outlined {
  font-size: 14px;
}
</style>

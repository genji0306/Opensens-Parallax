<script setup lang="ts">
import type { VisualizationPlan, VisualizationPlanItem } from '@/api/paperLab'
import ActionButton from '@/components/shared/ActionButton.vue'

defineProps<{
  plan: VisualizationPlan | null
  loading?: boolean
}>()

const emit = defineEmits<{
  generate: []
  create: [item: VisualizationPlanItem]
}>()

const sections: Array<{ key: keyof VisualizationPlan; label: string }> = [
  { key: 'reconstruct', label: 'Reconstruct' },
  { key: 'improve', label: 'Improve' },
  { key: 'create_missing', label: 'Create Missing' },
  { key: 'graphical_abstract', label: 'Graphical Abstract' },
  { key: 'communication_outputs', label: 'Communication Outputs' },
]
</script>

<template>
  <section class="figure-plan">
    <div class="figure-plan__header">
      <div>
        <h4>Figure Plan</h4>
        <p>PaperOrchestra-inspired planning ties review findings to visual recommendations.</p>
      </div>
      <ActionButton variant="secondary" size="sm" icon="auto_awesome" :loading="loading" @click="emit('generate')">Generate Plan</ActionButton>
    </div>

    <div v-if="!plan" class="figure-plan__empty">
      Generate a plan to see what should be reconstructed, improved, or created next.
    </div>

    <div v-else class="figure-plan__groups">
      <section v-for="section in sections" :key="section.key" class="plan-group">
        <div class="plan-group__header">
          <h5>{{ section.label }}</h5>
          <span>{{ plan[section.key]?.length ?? 0 }}</span>
        </div>
        <div v-if="!(plan[section.key]?.length)" class="plan-group__empty">No items in this group.</div>
        <article v-for="item in plan[section.key]" :key="item.plan_id" class="plan-item">
          <div class="plan-item__meta">
            <p class="plan-item__eyebrow">{{ item.type }} · {{ item.recommended_engine }}</p>
            <h6>{{ item.title }}</h6>
            <p>{{ item.rationale }}</p>
          </div>
          <div class="plan-item__details">
            <p v-if="item.linked_review_findings.length"><strong>Linked review findings:</strong> {{ item.linked_review_findings.join(' | ') }}</p>
            <p v-if="item.required_data.length"><strong>Required data:</strong> {{ item.required_data.join(' | ') }}</p>
          </div>
          <ActionButton variant="ghost" size="sm" icon="add_circle" @click="emit('create', item)">Create Artifact</ActionButton>
        </article>
      </section>
    </div>
  </section>
</template>

<style scoped>
.figure-plan {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.figure-plan__header,
.plan-group__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.figure-plan h4,
.plan-group h5,
.plan-item h6 {
  margin: 0;
  color: var(--text-primary);
}

.figure-plan p,
.figure-plan__empty,
.plan-group__empty {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.figure-plan__groups {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.plan-group {
  padding: 14px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-secondary);
  background: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.plan-item {
  padding: 12px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-secondary);
}

.plan-item__eyebrow {
  margin: 0 0 4px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--os-brand);
}

.plan-item__details {
  margin: 8px 0 10px;
}

@media (max-width: 960px) {
  .figure-plan__groups {
    grid-template-columns: 1fr;
  }
}
</style>

<script setup lang="ts">
import { computed } from 'vue'
import MetricCard from '@/components/shared/MetricCard.vue'

const props = defineProps<{
  result: Record<string, unknown>
}>()

const finalScore = computed(() => {
  return (props.result.final_score as number | undefined)
    ?? (props.result.last_score as number | undefined)
    ?? null
})

const revisionCount = computed(() => {
  return (props.result.revision_count as number | undefined) ?? 0
})

const publicationStatus = computed(() => {
  return (props.result.status as string | undefined)
    ?? (props.result.message as string | undefined)
    ?? 'Ready for publication'
})

const passReason = computed(() => {
  return (props.result.reason as string | undefined)
    ?? (props.result.loop_reason as string | undefined)
    ?? null
})

const hasData = computed(() =>
  finalScore.value !== null || revisionCount.value > 0 || !!passReason.value,
)
</script>

<template>
  <div class="pass-detail">
    <template v-if="hasData">
      <div class="pass-detail__metrics">
        <MetricCard
          label="Final Score"
          :value="finalScore !== null ? finalScore.toFixed(1) : '--'"
          icon="grade"
        />
        <MetricCard
          label="Revision Count"
          :value="revisionCount"
          icon="repeat"
        />
        <MetricCard
          label="Status"
          :value="publicationStatus"
          icon="workspace_premium"
        />
      </div>

      <p v-if="passReason" class="pass-detail__reason">
        {{ passReason }}
      </p>
    </template>

    <div v-else class="pass-detail__empty">
      <span class="material-symbols-outlined" style="font-size: 24px; color: var(--text-tertiary)">workspace_premium</span>
      <span>No publication-gate data available yet</span>
    </div>
  </div>
</template>

<style scoped>
.pass-detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 14px;
}

.pass-detail__metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.pass-detail__reason {
  margin: 0;
  padding: 14px;
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.pass-detail__empty {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-tertiary);
  padding-top: 6px;
}
</style>

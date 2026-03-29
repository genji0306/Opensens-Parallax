<script setup lang="ts">
/**
 * RevisionPlanView — Prioritized revision plan + rebuttal generator (Sprint 11).
 */

import { ref } from 'vue'
import { createRevisionPlan, generateRebuttal } from '@/api/ais'

const props = defineProps<{ runId: string }>()

const plan = ref<Array<{ priority: number; theme: string; action: string; sections_affected: string[]; estimated_effort: string; rationale: string }>>([])
const rebuttal = ref<Array<{ comment_id: string; reviewer_type: string; response: string; action_taken: string; status: string }>>([])
const planLoading = ref(false)
const rebuttalLoading = ref(false)
const error = ref<string | null>(null)

async function loadPlan() {
  planLoading.value = true
  error.value = null
  try {
    const res = await createRevisionPlan(props.runId)
    plan.value = res.data?.data?.plan ?? []
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to create plan'
  } finally {
    planLoading.value = false
  }
}

async function loadRebuttal() {
  rebuttalLoading.value = true
  error.value = null
  try {
    const res = await generateRebuttal(props.runId)
    rebuttal.value = res.data?.data?.responses ?? []
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to generate rebuttal'
  } finally {
    rebuttalLoading.value = false
  }
}

function effortColor(effort: string): string {
  return effort === 'major' ? 'var(--danger, #ef4444)' : effort === 'moderate' ? 'var(--warning, #f59e0b)' : 'var(--success, #22c55e)'
}

function statusIcon(status: string): string {
  return status === 'addressed' ? 'check_circle' : status === 'partially_addressed' ? 'pending' : 'cancel'
}
</script>

<template>
  <div class="revision-plan">
    <div class="revision-plan__section">
      <div class="revision-plan__header">
        <h5 class="detail-heading">Revision Plan</h5>
        <button v-if="!plan.length" class="revision-plan__btn" :disabled="planLoading" @click="loadPlan">
          {{ planLoading ? 'Creating...' : 'Create Plan' }}
        </button>
      </div>

      <div v-if="plan.length" class="revision-plan__list">
        <div v-for="item in plan" :key="item.priority" class="plan-item">
          <div class="plan-item__header">
            <span class="plan-item__priority font-mono">{{ item.priority }}</span>
            <span class="plan-item__theme">{{ item.theme }}</span>
            <span class="plan-item__effort" :style="{ color: effortColor(item.estimated_effort) }">
              {{ item.estimated_effort }}
            </span>
          </div>
          <p class="plan-item__action">{{ item.action }}</p>
          <div v-if="item.sections_affected.length" class="plan-item__sections">
            <span v-for="s in item.sections_affected" :key="s" class="plan-item__section-chip">{{ s }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="revision-plan__section">
      <div class="revision-plan__header">
        <h5 class="detail-heading">Response to Reviewers</h5>
        <button v-if="!rebuttal.length" class="revision-plan__btn" :disabled="rebuttalLoading" @click="loadRebuttal">
          {{ rebuttalLoading ? 'Generating...' : 'Generate Rebuttal' }}
        </button>
      </div>

      <div v-if="rebuttal.length" class="revision-plan__rebuttal">
        <div v-for="resp in rebuttal" :key="resp.comment_id" class="rebuttal-item">
          <div class="rebuttal-item__header">
            <span class="material-symbols-outlined rebuttal-item__icon" style="font-size: 14px">
              {{ statusIcon(resp.status) }}
            </span>
            <span class="rebuttal-item__reviewer">{{ resp.reviewer_type }}</span>
            <span class="rebuttal-item__status">{{ resp.status.replace(/_/g, ' ') }}</span>
          </div>
          <p class="rebuttal-item__response">{{ resp.response }}</p>
          <p v-if="resp.action_taken" class="rebuttal-item__action">{{ resp.action_taken }}</p>
        </div>
      </div>
    </div>

    <div v-if="error" class="revision-plan__error">{{ error }}</div>
  </div>
</template>

<style scoped>
.revision-plan { display: flex; flex-direction: column; gap: 16px; }
.revision-plan__section { display: flex; flex-direction: column; gap: 8px; }
.revision-plan__header { display: flex; justify-content: space-between; align-items: center; }
.detail-heading { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); margin: 0; }
.revision-plan__btn {
  padding: 5px 12px; font-size: 11px; font-weight: 500; color: var(--os-brand);
  background: color-mix(in srgb, var(--os-brand) 10%, transparent);
  border: 1px solid var(--os-brand); border-radius: var(--radius-md); cursor: pointer;
}
.revision-plan__btn:disabled { opacity: 0.5; cursor: not-allowed; }
.revision-plan__error { font-size: 12px; color: var(--danger, #ef4444); }

.revision-plan__list, .revision-plan__rebuttal { display: flex; flex-direction: column; gap: 6px; }

.plan-item {
  padding: 10px 12px; background: var(--bg-secondary);
  border: 1px solid var(--border-secondary); border-radius: var(--radius-md);
}
.plan-item__header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.plan-item__priority { font-size: 11px; font-weight: 700; color: var(--os-brand); min-width: 18px; }
.plan-item__theme { font-size: 12px; font-weight: 500; color: var(--text-primary); flex: 1; }
.plan-item__effort { font-size: 10px; font-weight: 600; text-transform: uppercase; }
.plan-item__action { font-size: 12px; color: var(--text-secondary); margin: 0 0 4px; line-height: 1.4; }
.plan-item__sections { display: flex; gap: 4px; flex-wrap: wrap; }
.plan-item__section-chip {
  font-size: 10px; padding: 1px 6px; border-radius: var(--radius-pill, 999px);
  background: var(--bg-primary); border: 1px solid var(--border-secondary); color: var(--text-tertiary);
}

.rebuttal-item {
  padding: 10px 12px; background: var(--bg-secondary);
  border: 1px solid var(--border-secondary); border-radius: var(--radius-md);
}
.rebuttal-item__header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.rebuttal-item__icon { color: var(--text-tertiary); }
.rebuttal-item__reviewer { font-size: 10px; font-weight: 600; text-transform: uppercase; color: var(--os-brand); }
.rebuttal-item__status { font-size: 10px; color: var(--text-tertiary); margin-left: auto; text-transform: capitalize; }
.rebuttal-item__response { font-size: 12px; color: var(--text-primary); margin: 0 0 4px; line-height: 1.5; }
.rebuttal-item__action { font-size: 11px; color: var(--text-tertiary); margin: 0; font-style: italic; }
</style>

<script setup lang="ts">
/**
 * AnnotationLayer — LLM-Peer-Review-style granular markup display.
 *
 * Renders reviewer annotations against a draft's sections with per-annotation
 * accept / reject buttons. Parent owns the decision state so the same
 * component can be reused for figure critique, consistency check, and
 * AgentReview 5-phase review output.
 */

import { computed } from 'vue'
import type { Annotation, AnnotationSeverity } from '@/types/api'

interface DraftSection {
  id: string
  heading: string
  text: string
}

interface Props {
  annotations: Annotation[]
  sections?: DraftSection[]
  /** Map of annotation_id -> 'accepted' | 'rejected' | undefined */
  decisions?: Record<string, 'accepted' | 'rejected' | undefined>
  /** Hide annotations that have already been accepted or rejected */
  hideResolved?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  sections: () => [],
  decisions: () => ({}),
  hideResolved: false,
})

const emit = defineEmits<{
  (e: 'accept', annotation: Annotation): void
  (e: 'reject', annotation: Annotation): void
}>()

const SEVERITY_ORDER: Record<AnnotationSeverity, number> = {
  critical: 0,
  major: 1,
  minor: 2,
  nit: 3,
}

const visible = computed<Annotation[]>(() => {
  const list = props.hideResolved
    ? props.annotations.filter(a => !props.decisions[a.annotation_id])
    : [...props.annotations]
  return list.sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
  )
})

const sectionMap = computed<Record<string, DraftSection>>(() => {
  const map: Record<string, DraftSection> = {}
  for (const section of props.sections) {
    map[section.id] = section
  }
  return map
})

const grouped = computed<Array<{ targetId: string; heading: string; items: Annotation[] }>>(() => {
  const groups: Record<string, Annotation[]> = {}
  for (const ann of visible.value) {
    const key = ann.target_id || 'unassigned'
    if (!groups[key]) groups[key] = []
    groups[key].push(ann)
  }
  return Object.entries(groups).map(([targetId, items]) => ({
    targetId,
    heading: sectionMap.value[targetId]?.heading ?? targetId,
    items,
  }))
})

function decisionOf(id: string): 'accepted' | 'rejected' | undefined {
  return props.decisions[id]
}

function accept(annotation: Annotation): void {
  emit('accept', annotation)
}

function reject(annotation: Annotation): void {
  emit('reject', annotation)
}
</script>

<template>
  <div class="annotation-layer">
    <header v-if="visible.length" class="annotation-layer__summary">
      {{ visible.length }} annotation{{ visible.length === 1 ? '' : 's' }}
    </header>
    <p v-else class="annotation-layer__empty">No annotations yet.</p>

    <section
      v-for="group in grouped"
      :key="group.targetId"
      class="annotation-group"
    >
      <h4 class="annotation-group__heading">{{ group.heading }}</h4>
      <ul class="annotation-list">
        <li
          v-for="ann in group.items"
          :key="ann.annotation_id"
          class="annotation"
          :class="[
            `annotation--${ann.severity}`,
            decisionOf(ann.annotation_id) ? `annotation--${decisionOf(ann.annotation_id)}` : '',
          ]"
        >
          <div class="annotation__meta">
            <span class="annotation__severity">{{ ann.severity }}</span>
            <span v-if="ann.reviewer_id" class="annotation__reviewer">
              {{ ann.reviewer_id }}
            </span>
            <span v-if="ann.confidence !== undefined" class="annotation__confidence">
              {{ Math.round((ann.confidence ?? 0) * 100) }}%
            </span>
          </div>
          <p v-if="ann.original_text" class="annotation__original">
            <span class="annotation__label">Quote:</span> {{ ann.original_text }}
          </p>
          <p class="annotation__comment">{{ ann.comment }}</p>
          <p v-if="ann.replacement_text" class="annotation__replacement">
            <span class="annotation__label">Suggested:</span> {{ ann.replacement_text }}
          </p>
          <div class="annotation__actions" v-if="!decisionOf(ann.annotation_id)">
            <button type="button" class="annotation__btn annotation__btn--accept" @click="accept(ann)">
              Accept
            </button>
            <button type="button" class="annotation__btn annotation__btn--reject" @click="reject(ann)">
              Reject
            </button>
          </div>
          <div class="annotation__status" v-else>
            {{ decisionOf(ann.annotation_id) }}
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.annotation-layer {
  display: flex;
  flex-direction: column;
  gap: var(--space-3, 0.75rem);
}

.annotation-layer__summary {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-muted, #6b7280);
}

.annotation-layer__empty {
  color: var(--color-muted, #6b7280);
  font-style: italic;
}

.annotation-group__heading {
  margin: 0 0 0.5rem 0;
  font-size: 0.9rem;
  font-weight: 600;
}

.annotation-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.annotation {
  border-radius: 8px;
  border-left: 3px solid var(--color-border, #d1d5db);
  background: var(--color-surface-alt, #f9fafb);
  padding: 0.75rem 0.875rem;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.annotation--critical { border-left-color: #dc2626; }
.annotation--major    { border-left-color: #f59e0b; }
.annotation--minor    { border-left-color: #3b82f6; }
.annotation--nit      { border-left-color: #9ca3af; }

.annotation--accepted { opacity: 0.7; background: #ecfdf5; }
.annotation--rejected { opacity: 0.5; background: #fef2f2; }

.annotation__meta {
  display: flex;
  gap: 0.5rem;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-muted, #6b7280);
}

.annotation__label {
  font-weight: 600;
  color: var(--color-muted, #6b7280);
}

.annotation__original,
.annotation__replacement,
.annotation__comment {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.45;
}

.annotation__original {
  font-style: italic;
  color: var(--color-muted, #4b5563);
}

.annotation__actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.25rem;
}

.annotation__btn {
  padding: 0.3rem 0.75rem;
  border-radius: 6px;
  border: 1px solid transparent;
  font-size: 0.78rem;
  cursor: pointer;
  transition: background-color 150ms ease;
}

.annotation__btn--accept {
  background: #10b981;
  color: white;
}

.annotation__btn--accept:hover { background: #059669; }

.annotation__btn--reject {
  background: transparent;
  color: #dc2626;
  border-color: #fca5a5;
}

.annotation__btn--reject:hover { background: #fef2f2; }

.annotation__status {
  font-size: 0.75rem;
  text-transform: uppercase;
  color: var(--color-muted, #6b7280);
}
</style>

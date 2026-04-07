<script setup lang="ts">
/**
 * QuestionTree — Tree visualization of research sub-questions (Sprint 6.2).
 * Shows evidence coverage per question.
 */

import { ref, watch } from 'vue'
import { decomposeQuestions, getKnowledgeArtifact } from '@/api/ais'
import type { KnowledgeArtifact, QuestionTreeData } from '@/api/ais'

const props = defineProps<{ runId: string }>()

const data = ref<QuestionTreeData | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

function buildQuestionTree(artifact: KnowledgeArtifact | null | undefined): QuestionTreeData | null {
  if (!artifact) return null

  const questions = Array.isArray(artifact.sub_questions) ? artifact.sub_questions : []
  if (!questions.length) return null

  const nodes = new Map<string, QuestionTreeData['tree'][number] & { parent_id: string | null }>()
  const orderedIds: string[] = []

  for (const question of questions) {
    if (!question.question_id) continue
    nodes.set(question.question_id, {
      id: question.question_id,
      text: question.text ?? '',
      evidence_coverage: Number(question.evidence_coverage ?? 0),
      parent_id: question.parent_id ?? null,
      children: [],
    })
    orderedIds.push(question.question_id)
  }

  const tree: QuestionTreeData['tree'] = []
  for (const questionId of orderedIds) {
    const node = nodes.get(questionId)
    if (!node) continue
    const parentId = node.parent_id
    if (parentId && nodes.has(parentId)) {
      nodes.get(parentId)!.children.push(node)
    } else {
      tree.push(node)
    }
  }

  const coverages = questions.map(question => Number(question.evidence_coverage ?? 0))
  return {
    questions,
    tree,
    stats: {
      total_questions: questions.length,
      avg_coverage: coverages.length ? Number((coverages.reduce((sum, coverage) => sum + coverage, 0) / coverages.length).toFixed(2)) : 0,
      uncovered_count: coverages.filter(coverage => coverage < 0.3).length,
    },
  }
}

async function hydrateQuestionTree() {
  if (!props.runId) {
    data.value = null
    return
  }

  try {
    const res = await getKnowledgeArtifact(props.runId)
    data.value = buildQuestionTree(res.data?.data ?? null)
  } catch {
    data.value = null
  }
}

async function runDecompose() {
  if (!props.runId) return
  loading.value = true
  error.value = null
  try {
    const res = await decomposeQuestions(props.runId)
    data.value = res.data?.data ?? null
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to decompose questions'
  } finally {
    loading.value = false
  }
}

watch(() => props.runId, () => {
  hydrateQuestionTree()
}, { immediate: true })

function coverageColor(coverage: number): string {
  if (coverage >= 0.7) return 'var(--success, #22c55e)'
  if (coverage >= 0.3) return 'var(--warning, #f59e0b)'
  return 'var(--danger, #ef4444)'
}

function coverageWidth(coverage: number): string {
  return `${Math.max(coverage * 100, 4)}%`
}
</script>

<template>
  <div class="question-tree">
    <div class="question-tree__header">
      <h5 class="detail-heading">Research Questions</h5>
      <button v-if="!data" class="question-tree__btn" :disabled="loading" @click="runDecompose">
        {{ loading ? 'Decomposing...' : 'Decompose' }}
      </button>
    </div>

    <div v-if="error" class="question-tree__error">{{ error }}</div>

    <template v-if="data">
      <div class="question-tree__stats">
        <span>{{ data.stats.total_questions }} questions</span>
        <span>Avg coverage: <strong>{{ (data.stats.avg_coverage * 100).toFixed(0) }}%</strong></span>
        <span v-if="data.stats.uncovered_count > 0" class="question-tree__uncovered">
          {{ data.stats.uncovered_count }} uncovered
        </span>
      </div>

      <div class="question-tree__list">
        <div v-for="node in data.tree" :key="node.id" class="question-tree__branch">
          <div class="question-tree__node">
            <span class="question-tree__text">{{ node.text }}</span>
            <div class="question-tree__coverage">
              <div
                class="question-tree__bar"
                :style="{ width: coverageWidth(node.evidence_coverage), background: coverageColor(node.evidence_coverage) }"
              ></div>
            </div>
            <span class="question-tree__pct font-mono">{{ (node.evidence_coverage * 100).toFixed(0) }}%</span>
          </div>

          <div v-if="node.children.length > 0" class="question-tree__children">
            <div v-for="child in node.children" :key="child.id" class="question-tree__node question-tree__node--child">
              <span class="question-tree__connector">└</span>
              <span class="question-tree__text">{{ child.text }}</span>
              <div class="question-tree__coverage">
                <div
                  class="question-tree__bar"
                  :style="{ width: coverageWidth(child.evidence_coverage), background: coverageColor(child.evidence_coverage) }"
                ></div>
              </div>
              <span class="question-tree__pct font-mono">{{ (child.evidence_coverage * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.question-tree { display: flex; flex-direction: column; gap: 12px; }
.question-tree__header { display: flex; justify-content: space-between; align-items: center; }
.detail-heading { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); margin: 0; }
.question-tree__btn {
  padding: 5px 12px; font-size: 11px; font-weight: 500; color: var(--os-brand);
  background: color-mix(in srgb, var(--os-brand) 10%, transparent);
  border: 1px solid var(--os-brand); border-radius: var(--radius-md); cursor: pointer;
}
.question-tree__btn:disabled { opacity: 0.5; cursor: not-allowed; }
.question-tree__error { font-size: 12px; color: var(--danger, #ef4444); }
.question-tree__stats { display: flex; gap: 12px; font-size: 11px; color: var(--text-secondary); }
.question-tree__uncovered { color: var(--danger, #ef4444); }

.question-tree__list { display: flex; flex-direction: column; gap: 8px; }
.question-tree__branch { display: flex; flex-direction: column; gap: 4px; }
.question-tree__node {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; background: var(--bg-secondary);
  border: 1px solid var(--border-secondary); border-radius: var(--radius-md);
}
.question-tree__node--child { margin-left: 20px; }
.question-tree__connector { font-size: 12px; color: var(--text-tertiary); font-family: monospace; }
.question-tree__text { flex: 1; font-size: 12px; color: var(--text-primary); line-height: 1.4; }
.question-tree__coverage {
  width: 60px; height: 6px; background: var(--bg-primary);
  border-radius: 3px; overflow: hidden; flex-shrink: 0;
}
.question-tree__bar { height: 100%; border-radius: 3px; transition: width 0.3s ease; }
.question-tree__pct { font-size: 10px; color: var(--text-tertiary); min-width: 28px; text-align: right; }
.question-tree__children { display: flex; flex-direction: column; gap: 4px; }
</style>

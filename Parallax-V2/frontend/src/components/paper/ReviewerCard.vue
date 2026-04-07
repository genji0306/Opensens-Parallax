<script setup lang="ts">
import { ref } from 'vue'

interface Weakness {
  severity: string
  section?: string
  text: string
  suggestion?: string
}

interface LanguageIssue {
  text: string
  suggestion?: string
}

interface Review {
  reviewer: string
  archetype: string
  score: number
  decision: string
  strengths: string[]
  weaknesses: Weakness[]
  language_issues: LanguageIssue[]
}

defineProps<{
  review: Review
}>()

const expanded = ref(false)

function scoreColor(score: number): string {
  if (score >= 7) return 'var(--success)'
  if (score >= 4) return 'var(--warning)'
  return 'var(--error)'
}

function scoreColorHex(score: number): string {
  if (score >= 7) return '#22c55e'
  if (score >= 4) return '#eab308'
  return '#ef4444'
}

function severityColor(severity: string): string {
  const s = severity.toLowerCase()
  if (s === 'fatal') return 'var(--error)'
  if (s === 'major') return 'var(--warning)'
  return 'var(--text-tertiary)'
}

function severityBg(severity: string): string {
  const s = severity.toLowerCase()
  if (s === 'fatal') return 'rgba(239,68,68,0.12)'
  if (s === 'major') return 'rgba(234,179,8,0.12)'
  return 'rgba(128,128,128,0.10)'
}

const archetypeColors: Record<string, string> = {
  methodologist: '#6366f1',
  novelty_hawk: '#f59e0b',
  field_expert: '#22c55e',
  clarity_editor: '#3b82f6',
  reference_auditor: '#ec4899',
  statistician: '#a78bfa',
  default: 'var(--os-brand)',
}

function archetypeColor(archetype: string): string {
  const key = archetype.toLowerCase().replace(/\s+/g, '_')
  return archetypeColors[key] ?? archetypeColors['default'] ?? 'var(--os-brand)'
}
</script>

<template>
  <div class="reviewer-card" :class="{ 'reviewer-card--expanded': expanded }">
    <!-- ── Trigger row ── -->
    <button class="rc-trigger" @click="expanded = !expanded">
      <!-- Score bar (mini) -->
      <div class="rc-score-wrap">
        <svg width="44" height="10" class="rc-score-bar">
          <rect x="0" y="1" width="44" height="8" rx="3" fill="var(--bg-tertiary)" opacity="0.5" />
          <rect
            x="0"
            y="1"
            :width="Math.max(3, (review.score / 10) * 44)"
            height="8"
            rx="3"
            :fill="scoreColorHex(review.score)"
            opacity="0.85"
          />
        </svg>
        <span class="rc-score font-mono" :style="{ color: scoreColor(review.score) }">
          {{ review.score?.toFixed(1) ?? '--' }}
        </span>
      </div>

      <!-- Name + archetype -->
      <div class="rc-identity">
        <span class="rc-name">{{ review.reviewer }}</span>
        <span
          class="rc-archetype"
          :style="{ color: archetypeColor(review.archetype), background: archetypeColor(review.archetype) + '1a' }"
        >
          {{ review.archetype }}
        </span>
      </div>

      <!-- Decision -->
      <span class="rc-decision">{{ review.decision?.replace(/_/g, ' ') }}</span>

      <!-- Counts -->
      <div class="rc-counts">
        <span v-if="review.strengths?.length" class="rc-count rc-count--ok">
          {{ review.strengths.length }} ✓
        </span>
        <span v-if="review.weaknesses?.length" class="rc-count rc-count--warn">
          {{ review.weaknesses.length }} ✗
        </span>
      </div>

      <!-- Chevron -->
      <span class="material-symbols-outlined rc-chevron">
        {{ expanded ? 'expand_less' : 'expand_more' }}
      </span>
    </button>

    <!-- ── Expanded body ── -->
    <div v-if="expanded" class="rc-body">
      <!-- Strengths -->
      <div v-if="review.strengths?.length" class="rc-section">
        <h6 class="rc-section__title rc-section__title--ok">
          <span class="material-symbols-outlined" style="font-size: 14px">thumb_up</span>
          Strengths
        </h6>
        <ul class="rc-list">
          <li v-for="(s, i) in review.strengths" :key="i" class="rc-list__item rc-list__item--ok">
            {{ s }}
          </li>
        </ul>
      </div>

      <!-- Weaknesses -->
      <div v-if="review.weaknesses?.length" class="rc-section">
        <h6 class="rc-section__title rc-section__title--warn">
          <span class="material-symbols-outlined" style="font-size: 14px">warning</span>
          Weaknesses
        </h6>
        <div class="rc-weakness-list">
          <div
            v-for="(w, wi) in review.weaknesses"
            :key="wi"
            class="rc-weakness"
          >
            <div class="rc-weakness__header">
              <span
                class="rc-severity"
                :style="{ color: severityColor(w.severity), background: severityBg(w.severity) }"
              >
                {{ w.severity }}
              </span>
              <span v-if="w.section" class="rc-weakness__section font-mono">{{ w.section }}</span>
            </div>
            <p class="rc-weakness__text">{{ w.text }}</p>
            <p v-if="w.suggestion" class="rc-weakness__suggestion">
              <span class="material-symbols-outlined" style="font-size: 12px; vertical-align: middle">lightbulb</span>
              {{ w.suggestion }}
            </p>
          </div>
        </div>
      </div>

      <!-- Language issues -->
      <div v-if="review.language_issues?.length" class="rc-section">
        <h6 class="rc-section__title rc-section__title--dim">
          <span class="material-symbols-outlined" style="font-size: 14px">spellcheck</span>
          Language Issues ({{ review.language_issues.length }})
        </h6>
        <ul class="rc-list">
          <li v-for="(li, i) in review.language_issues" :key="i" class="rc-list__item">
            {{ li.text }}
            <span v-if="li.suggestion" class="rc-lang-suggestion"> → {{ li.suggestion }}</span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reviewer-card {
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-primary);
  transition: border-color var(--transition-fast);
}

.reviewer-card--expanded {
  border-color: var(--border-primary);
}

/* ── Trigger ── */
.rc-trigger {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 12px;
  background: none;
  border: none;
  cursor: pointer;
  font-family: var(--font-sans);
  text-align: left;
  transition: background var(--transition-fast);
}

.rc-trigger:hover {
  background: var(--bg-hover);
}

/* Score */
.rc-score-wrap {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
}

.rc-score-bar {
  flex-shrink: 0;
}

.rc-score {
  font-size: 12px;
  font-weight: 700;
  min-width: 28px;
}

/* Identity */
.rc-identity {
  display: flex;
  align-items: center;
  gap: 7px;
  flex: 1;
  min-width: 0;
}

.rc-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rc-archetype {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 2px 6px;
  border-radius: var(--radius-pill);
  white-space: nowrap;
  flex-shrink: 0;
}

/* Decision */
.rc-decision {
  font-size: 11px;
  color: var(--text-tertiary);
  text-transform: capitalize;
  white-space: nowrap;
  flex-shrink: 0;
}

/* Counts */
.rc-counts {
  display: flex;
  gap: 5px;
  flex-shrink: 0;
}

.rc-count {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: var(--radius-sm);
}

.rc-count--ok {
  color: var(--success);
  background: rgba(34, 197, 94, 0.1);
}

.rc-count--warn {
  color: var(--warning);
  background: rgba(234, 179, 8, 0.1);
}

/* Chevron */
.rc-chevron {
  font-size: 18px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

/* ── Body ── */
.rc-body {
  padding: 12px;
  border-top: 1px solid var(--border-secondary);
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.rc-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rc-section__title {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0;
}

.rc-section__title--ok { color: var(--success); }
.rc-section__title--warn { color: var(--warning); }
.rc-section__title--dim { color: var(--text-tertiary); }

/* Lists */
.rc-list {
  margin: 0;
  padding-left: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rc-list__item {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.rc-list__item--ok {
  color: var(--text-secondary);
}

.rc-lang-suggestion {
  color: var(--os-brand);
  font-style: italic;
}

/* Weakness items */
.rc-weakness-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.rc-weakness {
  padding: 7px 10px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-sm);
}

.rc-weakness__header {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 4px;
}

.rc-severity {
  display: inline-block;
  padding: 1px 5px;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-radius: var(--radius-sm);
}

.rc-weakness__section {
  font-size: 10px;
  color: var(--text-tertiary);
}

.rc-weakness__text {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0 0 3px;
}

.rc-weakness__suggestion {
  font-size: 11px;
  color: var(--text-tertiary);
  font-style: italic;
  line-height: 1.4;
  margin: 3px 0 0;
}
</style>

<script setup lang="ts">
import { computed } from 'vue'

interface RuleCheck {
  rule_id: string
  rule: string
  check: string
  status: 'pass' | 'warn' | 'fail'
  note: string
}

interface FigureAudit {
  ref: string
  chart_type: string
  score: number
  checks: RuleCheck[]
}

interface AuditResult {
  overall_score: number
  figure_count: number
  figures: FigureAudit[]
  recommendations: string[]
  rules_reference: string
}

const props = defineProps<{
  audit: AuditResult
}>()

const scoreColor = computed(() => {
  const s = props.audit.overall_score
  if (s >= 8) return 'var(--success)'
  if (s >= 5) return 'var(--warning)'
  return 'var(--error)'
})

function statusIcon(status: string): string {
  if (status === 'pass') return 'check_circle'
  if (status === 'warn') return 'warning'
  return 'cancel'
}

function statusColor(status: string): string {
  if (status === 'pass') return 'var(--success)'
  if (status === 'warn') return 'var(--warning)'
  return 'var(--error)'
}

function scoreBarWidth(score: number): string {
  return `${Math.max(score * 10, 2)}%`
}
</script>

<template>
  <div class="fqa">
    <!-- Overall score -->
    <div class="fqa-header">
      <div class="fqa-title">
        <span class="material-symbols-outlined" style="font-size: 18px">fact_check</span>
        Figure Quality Audit
      </div>
      <div class="fqa-score" :style="{ color: scoreColor }">
        <span class="score-value">{{ audit.overall_score.toFixed(1) }}</span>
        <span class="score-max">/10</span>
      </div>
    </div>

    <div class="fqa-subtitle">
      Based on Rougier, Droettboom &amp; Bourne — <em>Ten Simple Rules for Better Figures</em> (PLOS Comp Bio, 2014)
    </div>

    <!-- Per-figure audits -->
    <div v-for="fig in audit.figures" :key="fig.ref" class="fqa-figure">
      <div class="fqa-figure-header">
        <span class="fig-ref">{{ fig.ref }}</span>
        <span class="fig-type">{{ fig.chart_type }}</span>
        <div class="fig-score-bar">
          <div class="fig-score-fill" :style="{
            width: scoreBarWidth(fig.score),
            background: fig.score >= 8 ? 'var(--success)' : fig.score >= 5 ? 'var(--warning)' : 'var(--error)',
          }" />
        </div>
        <span class="fig-score-label" :style="{
          color: fig.score >= 8 ? 'var(--success)' : fig.score >= 5 ? 'var(--warning)' : 'var(--error)',
        }">{{ fig.score.toFixed(1) }}</span>
      </div>

      <div class="fqa-checks">
        <div v-for="check in fig.checks" :key="check.rule_id" class="fqa-check" :class="check.status">
          <span class="material-symbols-outlined check-icon" :style="{ color: statusColor(check.status) }">
            {{ statusIcon(check.status) }}
          </span>
          <div class="check-content">
            <div class="check-rule">
              <span class="rule-id">{{ check.rule_id }}</span>
              {{ check.rule }}
            </div>
            <div v-if="check.note" class="check-note">{{ check.note }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Recommendations -->
    <div v-if="audit.recommendations.length" class="fqa-recs">
      <div class="fqa-recs-title">
        <span class="material-symbols-outlined" style="font-size: 16px">lightbulb</span>
        Recommendations
      </div>
      <ul class="fqa-recs-list">
        <li v-for="(rec, i) in audit.recommendations" :key="i">{{ rec }}</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.fqa {
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.fqa-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-secondary);
}

.fqa-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.fqa-score {
  display: flex;
  align-items: baseline;
  font-family: var(--font-mono);
}

.score-value { font-size: 20px; font-weight: 600; }
.score-max { font-size: 12px; opacity: 0.6; }

.fqa-subtitle {
  padding: 6px 14px;
  font-size: 11px;
  color: var(--text-tertiary);
  border-bottom: 1px solid var(--border-secondary);
  background: var(--bg-secondary);
}

.fqa-figure {
  border-bottom: 1px solid var(--border-secondary);
}

.fqa-figure:last-child { border-bottom: none; }

.fqa-figure-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--bg-primary);
}

.fig-ref {
  font-weight: 600;
  font-size: 12px;
  color: var(--text-primary);
}

.fig-type {
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--text-tertiary);
  padding: 1px 6px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-pill);
}

.fig-score-bar {
  flex: 1;
  height: 4px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}

.fig-score-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.fig-score-label {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  min-width: 28px;
  text-align: right;
}

.fqa-checks {
  padding: 0 14px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.fqa-check {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 4px 0;
}

.check-icon {
  font-size: 14px;
  margin-top: 1px;
  flex-shrink: 0;
}

.check-content { flex: 1; }

.check-rule {
  font-size: 12px;
  color: var(--text-primary);
}

.rule-id {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  color: var(--text-tertiary);
  margin-right: 4px;
}

.check-note {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 1px;
  font-style: italic;
}

.fqa-recs {
  padding: 12px 14px;
  background: var(--bg-secondary);
  border-top: 1px solid var(--border-secondary);
}

.fqa-recs-title {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.fqa-recs-list {
  margin: 0;
  padding-left: 20px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.fqa-recs-list li { margin-bottom: 4px; }
</style>

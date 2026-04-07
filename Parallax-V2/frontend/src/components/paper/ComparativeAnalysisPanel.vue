<script setup lang="ts">
import { ref } from 'vue'
import type { PaperUpload } from '@/types/api'
import type { ComparativeAnalysisResult } from '@/api/paperLab'
import { runComparativeAnalysis } from '@/api/paperLab'

const props = defineProps<{
  uploads: PaperUpload[]
}>()

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const result = ref<ComparativeAnalysisResult | null>(null)
const errorMsg = ref('')

async function startCompare() {
  if (props.uploads.length < 2) return
  status.value = 'running'
  errorMsg.value = ''
  
  try {
    const ids = props.uploads.map(u => u.upload_id)
    const res = await runComparativeAnalysis(ids)
    if (res.data?.data) {
      result.value = res.data.data
      status.value = 'done'
    } else {
      throw new Error('Invalid response structure')
    }
  } catch (err: any) {
    status.value = 'error'
    errorMsg.value = err.response?.data?.error || err.message || 'Comparison failed'
  }
}
</script>

<template>
  <div class="comparative-panel">
    <div class="comp-header">
      <div class="comp-header__text">
        <h3 class="comp-title">Comparative Analysis Lab</h3>
        <p class="comp-desc">
          Using <strong>Gemini 2.0 Flash Thinking</strong> across {{ uploads.length }} selected documents.
          Contrasting methods, identifying conflicts, and extracting synergies.
        </p>
      </div>
      <button 
        class="viz-action-btn"
        :disabled="status === 'running' || uploads.length < 2"
        @click="startCompare"
      >
        <span class="material-symbols-outlined" :class="{ spin: status === 'running' }">
          {{ status === 'running' ? 'progress_activity' : 'compare_arrows' }}
        </span>
        {{ status === 'running' ? 'Analysing...' : 'Run Comparative Analysis' }}
      </button>
    </div>

    <!-- Error State -->
    <div v-if="status === 'error'" class="comp-error">
      <span class="material-symbols-outlined">error</span>
      <p>{{ errorMsg }}</p>
    </div>

    <!-- Initial State -->
    <div v-if="status === 'idle'" class="comp-idle">
      <div class="docs-list">
        <div v-for="(up, i) in uploads" :key="up.upload_id" class="doc-badge">
          <span class="doc-num">Doc {{ i + 1 }}</span>
          <span class="doc-title">{{ up.title || up.source_filename }}</span>
        </div>
      </div>
      <p class="idle-hint">Click the button above to begin the deep comparison.</p>
    </div>

    <!-- Results -->
    <div v-if="status === 'done' && result" class="comp-results">
      
      <!-- Summary -->
      <div class="res-card">
        <div class="res-card__header">
          <span class="material-symbols-outlined">overview</span>
          <h4>Executive Summary</h4>
        </div>
        <p class="summary-text">{{ result.comparative_summary }}</p>
        <span class="engine-tag">{{ result.engine }}</span>
      </div>

      <div class="res-grid">
        <!-- Synergies -->
        <div class="res-card" style="grid-column: 1 / -1;">
          <div class="res-card__header">
            <span class="material-symbols-outlined" style="color: var(--success)">handshake</span>
            <h4>Conceptual Synergies</h4>
          </div>
          <div v-if="!result.synergies || result.synergies.length === 0" class="empty-res">None identified.</div>
          <div v-else class="syn-list">
            <div v-for="(syn, idx) in result.synergies" :key="idx" class="syn-item">
              <strong>{{ syn.concept }}</strong>
              <p>{{ syn.explanation }}</p>
            </div>
          </div>
        </div>

        <!-- Methods -->
        <div class="res-card">
          <div class="res-card__header">
            <span class="material-symbols-outlined" style="color: var(--os-brand)">science</span>
            <h4>Methodological Differences</h4>
          </div>
          <div v-if="!result.methodological_differences || result.methodological_differences.length === 0" class="empty-res">None identified.</div>
          <div v-for="(diff, idx) in result.methodological_differences" :key="idx" class="method-card">
            <span class="method-theme">{{ diff.theme }}</span>
            <p>{{ diff.description }}</p>
          </div>
        </div>

        <!-- Conflicts -->
        <div class="res-card">
          <div class="res-card__header">
            <span class="material-symbols-outlined" style="color: var(--warning)">warning</span>
            <h4>Conflicting Results</h4>
          </div>
          <div v-if="!result.conflicting_results || result.conflicting_results.length === 0" class="empty-res">None identified.</div>
          <div v-for="(conf, idx) in result.conflicting_results" :key="idx" class="conflict-card">
            <p class="conflict-finding"><strong>Finding:</strong> {{ conf.finding }}</p>
            <div class="conflict-claims">
              <div class="claim">
                <span class="claim-label">Doc A:</span>
                <span>{{ conf.paper_A_claim }}</span>
              </div>
              <div class="claim">
                <span class="claim-label">Doc B:</span>
                <span>{{ conf.paper_B_claim }}</span>
              </div>
            </div>
            <div class="conflict-res">
              <span class="material-symbols-outlined icon-small">lightbulb</span>
              {{ conf.resolution_suggestion }}
            </div>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<style scoped>
.comparative-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

.comp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.02);
  padding: 20px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.comp-title {
  margin: 0 0 4px 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.comp-desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.viz-action-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 8px;
  background: rgba(204, 255, 0, 0.1);
  color: #ccff00;
  font-size: 13px;
  font-weight: 500;
  border: 1px solid rgba(204, 255, 0, 0.2);
  cursor: pointer;
  transition: all 0.2s ease;
}

.viz-action-btn:hover:not(:disabled) {
  background: rgba(204, 255, 0, 0.15);
  border-color: rgba(204, 255, 0, 0.3);
  transform: scale(0.98);
}

.viz-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  filter: grayscale(1);
}

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.comp-idle, .comp-error {
  padding: 40px;
  text-align: center;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  border: 1px dashed rgba(255, 255, 255, 0.1);
}

.comp-error {
  color: var(--error);
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.05);
}

.comp-error .material-symbols-outlined { font-size: 32px; margin-bottom: 8px; }

.docs-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 500px;
  margin: 0 auto 20px auto;
  text-align: left;
}

.doc-badge {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(255, 255, 255, 0.03);
  padding: 10px 16px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.doc-num {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-tertiary);
  text-transform: uppercase;
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 6px;
  border-radius: 4px;
}

.doc-title {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.idle-hint {
  color: var(--text-tertiary);
  font-size: 13px;
  margin: 0;
}

/* Results Formatting */
.comp-results {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.res-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.res-card {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.res-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.res-card__header h4 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.summary-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
  margin: 0;
}

.engine-tag {
  align-self: flex-start;
  font-size: 10px;
  font-weight: 600;
  background: rgba(204, 255, 0, 0.1);
  color: #ccff00;
  padding: 2px 8px;
  border-radius: 4px;
  margin-top: 8px;
}

.empty-res {
  font-size: 13px;
  color: var(--text-tertiary);
  font-style: italic;
}

/* Items */
.syn-list { display: flex; flex-direction: column; gap: 12px; }
.syn-item {
  background: rgba(255, 255, 255, 0.02);
  padding: 12px;
  border-radius: 8px;
  border-left: 3px solid var(--success);
}
.syn-item strong { display: block; color: var(--text-primary); font-size: 13px; margin-bottom: 4px; }
.syn-item p { margin: 0; font-size: 13px; color: var(--text-secondary); line-height: 1.5; }

.method-card {
  background: rgba(255, 255, 255, 0.02);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}
.method-theme {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  color: var(--os-brand);
  background: rgba(3, 105, 161, 0.2);
  padding: 2px 6px;
  border-radius: 4px;
  margin-bottom: 6px;
}
.method-card p { margin: 0; font-size: 13px; color: var(--text-secondary); line-height: 1.4; }

.conflict-card {
  background: rgba(239, 68, 68, 0.05);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgba(239, 68, 68, 0.2);
}
.conflict-finding { margin: 0 0 8px 0; font-size: 13px; color: var(--text-primary); }
.conflict-claims { display: flex; flex-direction: column; gap: 6px; margin-bottom: 8px;}
.claim { display: flex; gap: 8px; font-size: 12px; color: var(--text-secondary); }
.claim-label { font-weight: 600; color: var(--warning); min-width: 45px;}
.conflict-res {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  background: rgba(0,0,0,0.2);
  padding: 8px;
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-tertiary);
  font-style: italic;
}
.icon-small { font-size: 14px; margin-top: 1px;}
</style>

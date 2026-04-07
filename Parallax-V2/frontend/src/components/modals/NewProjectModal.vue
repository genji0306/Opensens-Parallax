<script setup lang="ts">
import { ref, computed } from 'vue'
import ActionButton from '@/components/shared/ActionButton.vue'

defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  create: [data: { query: string; sources: string[] }]
}>()

const step = ref(1)
const query = ref('')
const description = ref('')

const allSources = [
  { id: 'arxiv', label: 'arXiv', icon: 'science' },
  { id: 'semantic_scholar', label: 'Semantic Scholar', icon: 'school' },
  { id: 'openalex', label: 'OpenAlex', icon: 'public' },
  { id: 'crossref', label: 'CrossRef', icon: 'link' },
  { id: 'pubmed', label: 'PubMed', icon: 'medication' },
  { id: 'biorxiv', label: 'bioRxiv', icon: 'biotech' },
  { id: 'core', label: 'CORE', icon: 'library_books' },
  { id: 'europe_pmc', label: 'Europe PMC', icon: 'language' },
  { id: 'doaj', label: 'DOAJ', icon: 'lock_open' },
  { id: 'openreview', label: 'OpenReview', icon: 'rate_review' },
  { id: 'ieee', label: 'IEEE', icon: 'electrical_services' },
  { id: 'acm', label: 'ACM', icon: 'computer' },
  { id: 'springer', label: 'Springer', icon: 'menu_book' },
]

const selectedSources = ref<string[]>(['arxiv', 'semantic_scholar', 'openalex', 'crossref'])

function toggleSource(id: string) {
  const idx = selectedSources.value.indexOf(id)
  if (idx >= 0) {
    selectedSources.value.splice(idx, 1)
  } else {
    selectedSources.value.push(id)
  }
}

const canNext = computed(() => query.value.trim().length > 5)
const canCreate = computed(() => canNext.value && selectedSources.value.length > 0)

function goNext() {
  if (step.value === 1 && canNext.value) step.value = 2
}

function goBack() {
  if (step.value === 2) step.value = 1
}

function handleCreate() {
  if (!canCreate.value) return
  emit('create', {
    query: query.value.trim(),
    sources: [...selectedSources.value],
  })
  reset()
}

function handleClose() {
  reset()
  emit('close')
}

function reset() {
  step.value = 1
  query.value = ''
  description.value = ''
  selectedSources.value = ['arxiv', 'semantic_scholar', 'openalex']
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="open" class="modal-overlay" @click.self="handleClose">
        <div class="modal-card">
          <!-- Header -->
          <div class="modal-card__header">
            <span class="material-symbols-outlined modal-card__header-icon">add_circle</span>
            <span class="modal-card__header-title">New Research Project</span>
            <button class="modal-card__close" @click="handleClose">
              <span class="material-symbols-outlined">close</span>
            </button>
          </div>

          <!-- Step indicator -->
          <div class="modal-card__steps">
            <span
              class="modal-card__step-dot"
              :class="{ 'modal-card__step-dot--active': step === 1 }"
            />
            <span
              class="modal-card__step-dot"
              :class="{ 'modal-card__step-dot--active': step === 2 }"
            />
          </div>

          <!-- Step 1: Research question -->
          <div v-if="step === 1" class="modal-card__body">
            <label class="modal-label">
              Research Question
              <span class="modal-label__required">*</span>
            </label>
            <p class="modal-hint">A specific, well-scoped question works best. The pipeline will search literature, debate hypotheses, and draft a paper around this topic.</p>
            <textarea
              v-model="query"
              class="modal-textarea"
              placeholder="e.g., What are the effects of high-temperature superconductors on quantum computing architectures?"
              rows="3"
            />
            <span class="modal-char-count font-mono" :class="{ 'modal-char-count--short': query.trim().length > 0 && query.trim().length <= 5 }">
              {{ query.trim().length }} chars{{ query.trim().length <= 5 && query.trim().length > 0 ? ' — too short' : '' }}
            </span>

            <label class="modal-label modal-label--mt">Additional Context <span class="modal-label__optional">(optional)</span></label>
            <textarea
              v-model="description"
              class="modal-textarea"
              placeholder="Constraints, target domain, specific methods to explore..."
              rows="2"
            />
          </div>

          <!-- Step 2: Source selection -->
          <div v-if="step === 2" class="modal-card__body">
            <label class="modal-label">Select Sources</label>
            <p class="modal-hint">Choose which academic databases to search. Pre-selected sources cover the broadest range for most topics.</p>

            <div class="source-grid">
              <button
                v-for="src in allSources"
                :key="src.id"
                class="source-chip"
                :class="{ 'source-chip--selected': selectedSources.includes(src.id) }"
                @click="toggleSource(src.id)"
              >
                <span class="material-symbols-outlined source-chip__icon">{{ src.icon }}</span>
                <span class="source-chip__label">{{ src.label }}</span>
                <span
                  v-if="selectedSources.includes(src.id)"
                  class="material-symbols-outlined source-chip__check"
                >
                  check
                </span>
              </button>
            </div>

            <p class="modal-hint modal-hint--count">
              {{ selectedSources.length }} source{{ selectedSources.length !== 1 ? 's' : '' }} selected
            </p>
          </div>

          <!-- Footer -->
          <div class="modal-card__footer">
            <ActionButton
              v-if="step === 2"
              variant="ghost"
              size="sm"
              icon="arrow_back"
              @click="goBack"
            >
              Back
            </ActionButton>
            <span v-else class="modal-card__spacer" />

            <div class="modal-card__footer-actions">
              <ActionButton variant="ghost" size="sm" @click="handleClose">
                Cancel
              </ActionButton>

              <ActionButton
                v-if="step === 1"
                variant="primary"
                size="sm"
                icon="arrow_forward"
                :disabled="!canNext"
                @click="goNext"
              >
                Next
              </ActionButton>

              <ActionButton
                v-if="step === 2"
                variant="primary"
                size="sm"
                icon="rocket_launch"
                :disabled="!canCreate"
                @click="handleCreate"
              >
                Create Project
              </ActionButton>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* ── Overlay ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  padding: 16px;
}

/* ── Card ── */
.modal-card {
  width: 100%;
  max-width: 520px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Header ── */
.modal-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border-secondary);
}

.modal-card__header-icon {
  font-size: 20px;
  color: var(--os-brand);
  font-variation-settings: 'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 20;
}

.modal-card__header-title {
  flex: 1;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.modal-card__close {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  transition: color var(--transition-fast), background var(--transition-fast);
}

.modal-card__close:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.modal-card__close .material-symbols-outlined {
  font-size: 20px;
}

/* ── Step dots ── */
.modal-card__steps {
  display: flex;
  justify-content: center;
  gap: 8px;
  padding: 12px 0 4px;
}

.modal-card__step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--border-primary);
  transition: background var(--transition-normal), transform var(--transition-normal);
}

.modal-card__step-dot--active {
  background: var(--os-brand);
  transform: scale(1.2);
}

/* ── Body ── */
.modal-card__body {
  padding: 12px 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.modal-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.modal-label--mt {
  margin-top: 10px;
}

.modal-label__required {
  color: var(--error);
}

.modal-textarea {
  width: 100%;
  margin-top: 4px;
  padding: 10px 12px;
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.modal-textarea::placeholder {
  color: var(--text-tertiary);
}

.modal-textarea:focus {
  outline: none;
  border-color: var(--os-brand);
  box-shadow: 0 0 0 3px rgba(var(--os-brand-rgb), 0.12);
}

.modal-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 2px 0 8px;
}

.modal-hint--count {
  margin-top: 8px;
  font-family: var(--font-mono);
  font-size: 11px;
}

.modal-label__optional {
  font-weight: 400;
  color: var(--text-tertiary);
  text-transform: none;
  letter-spacing: normal;
}

.modal-char-count {
  font-size: 10px;
  color: var(--text-tertiary);
  text-align: right;
}

.modal-char-count--short {
  color: var(--warning);
}

/* ── Source grid ── */
.source-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.source-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-family: var(--font-sans);
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast),
    box-shadow var(--transition-fast);
}

.source-chip:hover {
  border-color: var(--os-brand-subtle);
  background: var(--bg-hover);
}

.source-chip--selected {
  background: var(--os-brand-light);
  border-color: var(--os-brand);
}

.source-chip--selected:hover {
  background: var(--os-brand-light);
}

.source-chip__icon {
  font-size: 18px;
  color: var(--text-tertiary);
}

.source-chip--selected .source-chip__icon {
  color: var(--os-brand);
}

.source-chip__label {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  text-align: left;
}

.source-chip__check {
  font-size: 16px;
  color: var(--os-brand);
  font-variation-settings: 'FILL' 1, 'wght' 600, 'GRAD' 0, 'opsz' 20;
}

/* ── Footer ── */
.modal-card__footer {
  display: flex;
  align-items: center;
  padding: 12px 20px 16px;
  border-top: 1px solid var(--border-secondary);
}

.modal-card__spacer {
  flex: 1;
}

.modal-card__footer-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

/* ── Transition ── */
.modal-fade-enter-active {
  transition: opacity 0.2s ease;
}
.modal-fade-leave-active {
  transition: opacity 0.15s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-active .modal-card {
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease;
}
.modal-fade-leave-active .modal-card {
  transition: transform 0.15s ease, opacity 0.15s ease;
}
.modal-fade-enter-from .modal-card {
  transform: translateY(16px) scale(0.97);
  opacity: 0;
}
.modal-fade-leave-to .modal-card {
  transform: translateY(8px) scale(0.98);
  opacity: 0;
}
</style>

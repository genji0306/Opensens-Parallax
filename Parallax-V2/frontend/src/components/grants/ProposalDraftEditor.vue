<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import GlassPanel from '@/components/shared/GlassPanel.vue'
import { useGrantsStore } from '@/stores/grants'
import type { ProposalSection } from '@/types/grants'

defineEmits<{ (e: 'next'): void }>()

const store = useGrantsStore()

const proposal = computed(() => store.activeProposal)
const drafting = computed(() => Boolean(store.loading.draft))
const sectionLoading = computed(() => Boolean(store.loading.section))

const activeKey = ref<string>('')
const manualContent = ref<string>('')
const reviseInstructions = ref<string>('')

const activeSection = computed<ProposalSection | null>(() => {
  if (!proposal.value || !activeKey.value) return null
  return proposal.value.plan.sections.find(s => s.key === activeKey.value) ?? null
})

watch(
  () => proposal.value?.proposal_id,
  () => {
    activeKey.value = proposal.value?.plan.sections[0]?.key ?? ''
  },
  { immediate: true },
)

watch(
  () => activeSection.value,
  section => {
    manualContent.value = section?.content ?? ''
    reviseInstructions.value = ''
  },
  { immediate: true },
)

async function draftAll(): Promise<void> {
  if (!proposal.value) return
  await store.runDrafter(proposal.value.proposal_id)
}

async function draftOne(): Promise<void> {
  if (!proposal.value || !activeKey.value) return
  await store.regenerateSection(proposal.value.proposal_id, activeKey.value)
}

async function revise(): Promise<void> {
  if (!proposal.value || !activeKey.value) return
  await store.regenerateSection(
    proposal.value.proposal_id,
    activeKey.value,
    reviseInstructions.value,
  )
  reviseInstructions.value = ''
}

async function saveManual(): Promise<void> {
  if (!proposal.value || !activeKey.value) return
  await store.editSectionContent(
    proposal.value.proposal_id,
    activeKey.value,
    manualContent.value,
  )
}
</script>

<template>
  <GlassPanel title="Draft" icon="edit_note">
    <div v-if="!proposal" class="empty">
      No proposal selected.
    </div>

    <div v-else class="draft">
      <div class="draft__toolbar">
        <button class="btn-primary" :disabled="drafting" @click="draftAll">
          <span class="material-icons">{{ drafting ? 'hourglass_top' : 'auto_awesome' }}</span>
          {{ drafting ? 'Drafting…' : 'Draft all sections' }}
        </button>
        <button class="btn-ghost" @click="$emit('next')">
          <span class="material-icons">inventory_2</span>
          Package proposal
        </button>
      </div>

      <div class="draft__body">
        <nav class="section-nav">
          <button
            v-for="s in proposal.plan.sections"
            :key="s.key"
            class="section-nav__item"
            :class="{
              'is-active': s.key === activeKey,
              'is-drafted': s.status === 'drafted' || !!s.content,
            }"
            @click="activeKey = s.key"
          >
            <span class="section-nav__title">{{ s.title }}</span>
            <span v-if="s.content" class="section-nav__badge">
              <span class="material-icons">check</span>
            </span>
          </button>
        </nav>

        <div v-if="activeSection" class="section-editor">
          <header>
            <h3>{{ activeSection.title }}</h3>
            <div v-if="activeSection.word_limit" class="hint">
              Word limit: {{ activeSection.word_limit }}
            </div>
          </header>
          <p v-if="activeSection.guidance" class="guidance">{{ activeSection.guidance }}</p>

          <textarea
            v-model="manualContent"
            rows="16"
            placeholder="Draft content will appear here. Generate it, or write your own."
          />
          <div class="section-editor__actions">
            <button class="btn-ghost" :disabled="sectionLoading" @click="draftOne">
              <span class="material-icons">auto_awesome</span>
              Regenerate
            </button>
            <button class="btn-primary" @click="saveManual">
              <span class="material-icons">save</span>
              Save edit
            </button>
          </div>

          <div class="revise">
            <label>Revise with instructions</label>
            <textarea
              v-model="reviseInstructions"
              rows="3"
              placeholder="e.g. shorten by 20%, add a concrete example from our pilot study…"
            />
            <button class="btn-ghost" :disabled="sectionLoading || !reviseInstructions" @click="revise">
              <span class="material-icons">sync</span>
              Rewrite with instructions
            </button>
          </div>
        </div>
      </div>
    </div>
  </GlassPanel>
</template>

<style scoped>
.empty {
  padding: 2rem 0;
  text-align: center;
  color: var(--color-text-muted, #8e95a8);
  font-size: 0.9rem;
}

.draft__toolbar {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 1rem;
  justify-content: space-between;
  flex-wrap: wrap;
}

.draft__body {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 1rem;
}

@media (max-width: 900px) {
  .draft__body {
    grid-template-columns: 1fr;
  }
}

.section-nav {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.section-nav__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.35rem;
  padding: 0.55rem 0.75rem;
  background: transparent;
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.06));
  border-radius: 8px;
  color: inherit;
  font: inherit;
  font-size: 0.82rem;
  text-align: left;
  cursor: pointer;
  transition: background 120ms ease;
}

.section-nav__item:hover {
  background: rgba(255, 255, 255, 0.04);
}

.section-nav__item.is-active {
  background: rgba(122, 162, 255, 0.14);
  border-color: rgba(122, 162, 255, 0.4);
}

.section-nav__badge {
  width: 1.1rem;
  height: 1.1rem;
  border-radius: 50%;
  background: rgba(120, 220, 160, 0.22);
  color: #78dca0;
  display: grid;
  place-items: center;
}

.section-nav__badge .material-icons {
  font-size: 0.8rem;
}

.section-editor header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.6rem;
  margin-bottom: 0.25rem;
}

.section-editor h3 {
  margin: 0;
  font-size: 1rem;
}

.hint {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-accent, #7aa2ff);
}

.guidance {
  margin: 0 0 0.6rem;
  font-size: 0.82rem;
  color: var(--color-text-muted, #8e95a8);
  line-height: 1.45;
}

.section-editor textarea {
  width: 100%;
  background: var(--color-surface, rgba(255, 255, 255, 0.04));
  color: inherit;
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.08));
  border-radius: 8px;
  padding: 0.7rem 0.85rem;
  font: inherit;
  font-size: 0.88rem;
  line-height: 1.55;
  resize: vertical;
}

.section-editor__actions {
  display: flex;
  gap: 0.4rem;
  margin-top: 0.5rem;
  justify-content: flex-end;
}

.btn-primary,
.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.45rem 0.8rem;
  border-radius: 6px;
  font: inherit;
  font-size: 0.82rem;
  cursor: pointer;
  border: 1px solid transparent;
}

.btn-primary {
  background: var(--color-accent, #7aa2ff);
  color: #0b0f18;
  font-weight: 600;
}

.btn-primary:disabled,
.btn-ghost:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn-ghost {
  background: transparent;
  color: inherit;
  border-color: var(--color-border, rgba(255, 255, 255, 0.12));
}

.revise {
  margin-top: 1rem;
  padding: 0.75rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.06));
  border-radius: 8px;
}

.revise label {
  display: block;
  font-size: 0.74rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted, #8e95a8);
  margin-bottom: 0.3rem;
}

.revise textarea {
  width: 100%;
  margin-bottom: 0.4rem;
}
</style>

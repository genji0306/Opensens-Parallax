<script setup lang="ts">
import { computed } from 'vue'

import GlassPanel from '@/components/shared/GlassPanel.vue'
import { useGrantsStore } from '@/stores/grants'

const store = useGrantsStore()

const proposal = computed(() => store.activeProposal)
const kit = computed(() => proposal.value?.submission_kit ?? null)
const packaging = computed(() => Boolean(store.loading.package))

async function runPackager(): Promise<void> {
  if (!proposal.value) return
  await store.runPackager(proposal.value.proposal_id)
}

async function copyAssembled(): Promise<void> {
  if (!kit.value) return
  await navigator.clipboard.writeText(kit.value.sections_markdown)
}

async function download(): Promise<void> {
  if (!kit.value || !proposal.value) return
  const blob = new Blob(
    [
      `# Proposal — ${proposal.value.proposal_id}\n\n`,
      `## Cover letter\n\n${kit.value.cover_letter}\n\n`,
      `## Sections\n\n${kit.value.sections_markdown}\n\n`,
      `## Submission instructions\n\n${kit.value.instructions}\n`,
    ],
    { type: 'text/markdown' },
  )
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `proposal-${proposal.value.proposal_id}.md`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <GlassPanel title="Submission Kit" icon="inventory_2">
    <div v-if="!proposal" class="empty">
      No proposal selected.
    </div>

    <div v-else>
      <div class="kit__toolbar">
        <button class="btn-primary" :disabled="packaging" @click="runPackager">
          <span class="material-icons">{{ packaging ? 'hourglass_top' : 'inventory_2' }}</span>
          {{ kit ? 'Regenerate kit' : 'Assemble kit' }}
        </button>
        <button class="btn-ghost" :disabled="!kit" @click="copyAssembled">
          <span class="material-icons">content_copy</span>
          Copy assembled
        </button>
        <button class="btn-ghost" :disabled="!kit" @click="download">
          <span class="material-icons">download</span>
          Download .md
        </button>
      </div>

      <div v-if="!kit" class="empty">
        Kit not assembled yet. The packager produces a draft + funder-specific submission instructions.
      </div>

      <div v-else class="kit">
        <section>
          <h4>Cover letter</h4>
          <pre>{{ kit.cover_letter }}</pre>
        </section>

        <section>
          <h4>Submission instructions (funder-specific)</h4>
          <pre>{{ kit.instructions }}</pre>
        </section>

        <section v-if="kit.checklist.length">
          <h4>Checklist</h4>
          <ul class="checklist">
            <li v-for="(item, i) in kit.checklist" :key="i">
              <span class="checklist__dot" :class="{ done: item.status === 'done' }"></span>
              {{ item.item }}
              <span v-if="item.notes" class="checklist__notes">— {{ item.notes }}</span>
            </li>
          </ul>
        </section>

        <section>
          <h4>Assembled sections</h4>
          <pre>{{ kit.sections_markdown }}</pre>
        </section>
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

.kit__toolbar {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.btn-primary,
.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.45rem 0.85rem;
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

.kit {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

h4 {
  margin: 0 0 0.3rem;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-muted, #8e95a8);
}

pre {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.06));
  border-radius: 8px;
  padding: 0.8rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8rem;
  line-height: 1.55;
  max-height: 420px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}

.checklist {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.checklist li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.checklist__dot {
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 50%;
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.2));
}

.checklist__dot.done {
  background: #78dca0;
  border-color: #78dca0;
}

.checklist__notes {
  color: var(--color-text-muted, #8e95a8);
  font-size: 0.78rem;
}
</style>

<script setup lang="ts">
import { ref } from 'vue'

import GlassPanel from '@/components/shared/GlassPanel.vue'
import { useGrantsStore } from '@/stores/grants'
import type { GrantSource } from '@/types/grants'

const store = useGrantsStore()

const addingCustom = ref(false)
const customName = ref('')
const customUrl = ref('')

async function toggle(source: GrantSource, value: boolean): Promise<void> {
  await store.toggleSource(source.source_id, value)
}

async function addCustom(): Promise<void> {
  if (!customUrl.value.trim()) return
  await store.addSource({
    name: customName.value.trim() || 'Custom source',
    listing_url: customUrl.value.trim(),
    kind: 'generic',
    enabled: true,
  })
  customName.value = ''
  customUrl.value = ''
  addingCustom.value = false
}

async function remove(source: GrantSource): Promise<void> {
  if (!confirm(`Remove source "${source.name}"?`)) return
  await store.removeSource(source.source_id)
}

function kindLabel(kind: string): string {
  return {
    fundsforngos: 'FundsforNGOs',
    grants_gov: 'Grants.gov',
    cordis: 'CORDIS',
    horizon_europe: 'Horizon Europe',
    generic: 'Custom',
  }[kind] ?? kind
}
</script>

<template>
  <GlassPanel title="Sources" icon="public">
    <div class="sources">
      <div
        v-for="src in store.sources"
        :key="src.source_id"
        class="source-row"
        :class="{ 'is-off': !src.enabled }"
      >
        <div class="source-row__meta">
          <div class="source-row__name">{{ src.name }}</div>
          <div class="source-row__sub">
            <span class="kind-chip">{{ kindLabel(src.kind) }}</span>
            <a :href="src.listing_url" target="_blank" rel="noopener">{{ src.listing_url }}</a>
          </div>
          <div v-if="src.last_crawled_at" class="source-row__crawled">
            Last crawled {{ new Date(src.last_crawled_at).toLocaleString() }}
          </div>
        </div>
        <div class="source-row__actions">
          <label class="toggle">
            <input
              type="checkbox"
              :checked="src.enabled"
              @change="toggle(src, ($event.target as HTMLInputElement).checked)"
            />
            <span>{{ src.enabled ? 'Enabled' : 'Disabled' }}</span>
          </label>
          <button class="icon-btn" @click="remove(src)" title="Remove">
            <span class="material-icons">close</span>
          </button>
        </div>
      </div>

      <div v-if="!addingCustom" class="add-source">
        <button class="btn-ghost" @click="addingCustom = true">
          <span class="material-icons">add</span>
          Add custom source
        </button>
      </div>

      <div v-else class="add-source__form">
        <input v-model="customName" placeholder="Source name" />
        <input v-model="customUrl" placeholder="https://funder.org/grants" />
        <div>
          <button class="btn-ghost" @click="addingCustom = false">Cancel</button>
          <button class="btn-primary" @click="addCustom">Add</button>
        </div>
      </div>
    </div>
  </GlassPanel>
</template>

<style scoped>
.sources {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.source-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.06));
  border-radius: 8px;
  transition: opacity 150ms ease;
}

.source-row.is-off {
  opacity: 0.55;
}

.source-row__meta {
  flex: 1;
  min-width: 0;
}

.source-row__name {
  font-weight: 600;
  font-size: 0.9rem;
  margin-bottom: 0.15rem;
}

.source-row__sub {
  font-size: 0.75rem;
  display: flex;
  gap: 0.4rem;
  align-items: center;
  color: var(--color-text-muted, #8e95a8);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-row__sub a {
  color: inherit;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-row__sub a:hover {
  text-decoration: underline;
}

.source-row__crawled {
  font-size: 0.7rem;
  opacity: 0.7;
  margin-top: 0.2rem;
}

.kind-chip {
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  background: rgba(122, 162, 255, 0.16);
  color: var(--color-accent, #7aa2ff);
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}

.source-row__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  color: var(--color-text-muted, #8e95a8);
  cursor: pointer;
}

.icon-btn {
  background: transparent;
  border: none;
  color: inherit;
  opacity: 0.6;
  cursor: pointer;
}

.icon-btn:hover {
  opacity: 1;
  color: #ff8e8e;
}

.add-source .btn-ghost {
  width: 100%;
  justify-content: center;
  padding: 0.6rem;
  border: 1px dashed var(--color-border, rgba(255, 255, 255, 0.15));
  border-radius: 8px;
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 0.85rem;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  cursor: pointer;
}

.add-source__form {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.6rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.08));
  border-radius: 8px;
}

.add-source__form input {
  background: var(--color-surface, rgba(255, 255, 255, 0.04));
  color: inherit;
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.08));
  border-radius: 6px;
  padding: 0.45rem 0.6rem;
  font: inherit;
  font-size: 0.82rem;
}

.add-source__form > div {
  display: flex;
  justify-content: flex-end;
  gap: 0.35rem;
}

.btn-primary,
.btn-ghost {
  padding: 0.35rem 0.7rem;
  border-radius: 6px;
  font: inherit;
  font-size: 0.8rem;
  cursor: pointer;
  border: 1px solid transparent;
}

.btn-primary {
  background: var(--color-accent, #7aa2ff);
  color: #0b0f18;
  font-weight: 600;
}

.btn-ghost {
  background: transparent;
  color: inherit;
  border-color: var(--color-border, rgba(255, 255, 255, 0.12));
}
</style>

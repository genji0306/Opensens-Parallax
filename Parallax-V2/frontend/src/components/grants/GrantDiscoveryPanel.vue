<script setup lang="ts">
import { computed, ref } from 'vue'

import GlassPanel from '@/components/shared/GlassPanel.vue'
import { useGrantsStore } from '@/stores/grants'

const store = useGrantsStore()

const maxPages = ref(25)

const running = computed(() => store.discoveryStatus.running || Boolean(store.loading.discover))
const lastRun = computed(() => store.discoveryStatus.lastRun)
const lastCount = computed(() => store.discoveryStatus.lastCount)
const error = computed(() => store.errors.discover)

const topOpportunities = computed(() => store.opportunities.slice(0, 10))

async function triggerCrawl(): Promise<void> {
  await store.runDiscovery({ max_pages: maxPages.value })
}

async function runMatch(): Promise<void> {
  await store.runMatch()
}
</script>

<template>
  <GlassPanel title="Discover" icon="travel_explore">
    <div class="discovery">
      <div class="discovery__controls">
        <label>
          <span>Pages per source</span>
          <input v-model.number="maxPages" type="number" min="5" max="100" />
        </label>
        <button class="btn-primary" :disabled="running" @click="triggerCrawl">
          <span class="material-icons">{{ running ? 'hourglass_top' : 'rocket_launch' }}</span>
          {{ running ? 'Crawling…' : 'Start discovery' }}
        </button>
        <button
          class="btn-ghost"
          :disabled="running || store.opportunities.length === 0 || !store.activeProfileId"
          @click="runMatch"
        >
          <span class="material-icons">insights</span>
          Score matches
        </button>
      </div>

      <div v-if="error" class="error">
        <span class="material-icons">error</span>{{ error }}
      </div>

      <div class="discovery__status">
        <div v-if="lastRun">
          <strong>{{ lastCount }}</strong> opportunities discovered in the last run
          <span>({{ new Date(lastRun).toLocaleString() }})</span>
        </div>
        <div v-else>No discovery runs yet.</div>
      </div>

      <div v-if="topOpportunities.length > 0" class="discovery__preview">
        <h4>Most recent</h4>
        <ul>
          <li v-for="opp in topOpportunities" :key="opp.opportunity_id">
            <a :href="opp.call_url || opp.source_url" target="_blank" rel="noopener">
              {{ opp.title }}
            </a>
            <span v-if="opp.funder" class="preview__funder">· {{ opp.funder }}</span>
            <span v-if="opp.deadline" class="preview__deadline">· {{ opp.deadline }}</span>
          </li>
        </ul>
      </div>
    </div>
  </GlassPanel>
</template>

<style scoped>
.discovery {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.discovery__controls {
  display: flex;
  align-items: flex-end;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.discovery__controls label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.76rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted, #8e95a8);
}

.discovery__controls input {
  background: var(--color-surface, rgba(255, 255, 255, 0.04));
  color: inherit;
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.08));
  border-radius: 6px;
  padding: 0.5rem 0.65rem;
  font: inherit;
  font-size: 0.88rem;
  width: 110px;
  text-transform: none;
  letter-spacing: normal;
}

.btn-primary,
.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.55rem 0.95rem;
  border-radius: 6px;
  font: inherit;
  font-size: 0.85rem;
  cursor: pointer;
  border: 1px solid transparent;
}

.btn-primary {
  background: var(--color-accent, #7aa2ff);
  color: #0b0f18;
  font-weight: 600;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-ghost {
  background: transparent;
  color: inherit;
  border-color: var(--color-border, rgba(255, 255, 255, 0.12));
}

.btn-ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error {
  color: #ff8e8e;
  font-size: 0.82rem;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.discovery__status {
  font-size: 0.82rem;
  color: var(--color-text-muted, #8e95a8);
}

.discovery__status strong {
  color: var(--color-accent, #7aa2ff);
  font-weight: 700;
}

.discovery__preview h4 {
  margin: 0 0 0.4rem;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-muted, #8e95a8);
}

.discovery__preview ul {
  margin: 0;
  padding-left: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.discovery__preview li {
  font-size: 0.85rem;
  line-height: 1.4;
}

.discovery__preview a {
  color: inherit;
  text-decoration: none;
}

.discovery__preview a:hover {
  color: var(--color-accent, #7aa2ff);
  text-decoration: underline;
}

.preview__funder,
.preview__deadline {
  color: var(--color-text-muted, #8e95a8);
  font-size: 0.78rem;
  margin-left: 0.3rem;
}
</style>

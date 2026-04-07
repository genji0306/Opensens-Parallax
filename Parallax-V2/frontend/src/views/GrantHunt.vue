<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { useGrantsStore, STAGE_ORDER } from '@/stores/grants'
import { getProfileTemplate } from '@/api/grants'
import GrantProfileEditor from '@/components/grants/GrantProfileEditor.vue'
import GrantSourceManager from '@/components/grants/GrantSourceManager.vue'
import GrantDiscoveryPanel from '@/components/grants/GrantDiscoveryPanel.vue'
import GrantMatchList from '@/components/grants/GrantMatchList.vue'
import ProposalPlanView from '@/components/grants/ProposalPlanView.vue'
import ProposalDraftEditor from '@/components/grants/ProposalDraftEditor.vue'
import SubmissionKitView from '@/components/grants/SubmissionKitView.vue'
import GlassPanel from '@/components/shared/GlassPanel.vue'

type StageKey = typeof STAGE_ORDER[number]

const store = useGrantsStore()

const activeStage = ref<StageKey>('discover')
const creatingProfile = ref(false)
const newProfileName = ref('')
const newProfileMarkdown = ref('')

const stages: Array<{ key: StageKey; label: string; icon: string }> = [
  { key: 'discover', label: 'Discover', icon: 'travel_explore' },
  { key: 'match', label: 'Match', icon: 'insights' },
  { key: 'plan', label: 'Plan', icon: 'format_list_numbered' },
  { key: 'draft', label: 'Draft', icon: 'edit_note' },
  { key: 'package', label: 'Package', icon: 'inventory_2' },
]

const hasProfile = computed(() => store.profiles.length > 0)
const matchedCount = computed(() => store.matches.length)
const proposalCount = computed(() => store.proposals.length)

async function handleCreateProfile(): Promise<void> {
  if (!newProfileName.value.trim()) return
  await store.createProfile({
    name: newProfileName.value.trim(),
    markdown: newProfileMarkdown.value,
  })
  creatingProfile.value = false
  newProfileName.value = ''
  newProfileMarkdown.value = ''
}

async function openNewProfileDialog(): Promise<void> {
  creatingProfile.value = true
  try {
    const res = await getProfileTemplate()
    newProfileMarkdown.value = res.template ?? ''
  } catch {
    newProfileMarkdown.value = ''
  }
}

function gotoStage(stage: StageKey): void {
  activeStage.value = stage
}

onMounted(async () => {
  await store.bootstrap()
  if (!store.profiles.length) {
    activeStage.value = 'discover'
  }
})
</script>

<template>
  <div class="grant-hunt">
    <header class="grant-hunt__header">
      <div class="grant-hunt__title">
        <span class="material-icons">payments</span>
        <h1>Grant Hunt</h1>
        <span class="grant-hunt__subtitle">
          Discover funding → match your profile → plan, draft, and package the proposal
        </span>
      </div>

      <div class="grant-hunt__profile-switch">
        <label>Profile</label>
        <select
          :value="store.activeProfileId ?? ''"
          @change="e => store.selectProfile((e.target as HTMLSelectElement).value)"
          :disabled="!hasProfile"
        >
          <option v-if="!hasProfile" value="">— No profile yet —</option>
          <option
            v-for="p in store.profiles"
            :key="p.profile_id"
            :value="p.profile_id"
          >
            {{ p.name }}
          </option>
        </select>
        <button class="btn-primary" @click="openNewProfileDialog">
          <span class="material-icons">add</span>
          New Profile
        </button>
      </div>
    </header>

    <!-- Stage tracker -->
    <nav class="stage-tracker" aria-label="Grant hunt stages">
      <button
        v-for="(s, idx) in stages"
        :key="s.key"
        class="stage-tracker__step"
        :class="{ 'is-active': activeStage === s.key }"
        @click="gotoStage(s.key)"
      >
        <span class="stage-tracker__index">{{ idx + 1 }}</span>
        <span class="material-icons">{{ s.icon }}</span>
        <span class="stage-tracker__label">{{ s.label }}</span>
      </button>
    </nav>

    <!-- KPI strip -->
    <section class="kpi-strip">
      <div class="kpi">
        <div class="kpi__value">{{ store.profiles.length }}</div>
        <div class="kpi__label">Profiles</div>
      </div>
      <div class="kpi">
        <div class="kpi__value">{{ store.enabledSources.length }}</div>
        <div class="kpi__label">Enabled sources</div>
      </div>
      <div class="kpi">
        <div class="kpi__value">{{ store.opportunities.length }}</div>
        <div class="kpi__label">Opportunities</div>
      </div>
      <div class="kpi">
        <div class="kpi__value">{{ matchedCount }}</div>
        <div class="kpi__label">Ranked matches</div>
      </div>
      <div class="kpi">
        <div class="kpi__value">{{ proposalCount }}</div>
        <div class="kpi__label">Proposals</div>
      </div>
    </section>

    <!-- Main content per stage -->
    <main class="grant-hunt__body">
      <!-- Profile editor is always visible on the left -->
      <aside class="grant-hunt__sidebar">
        <GlassPanel title="Applicant Profile" icon="badge">
          <GrantProfileEditor />
        </GlassPanel>
      </aside>

      <section class="grant-hunt__stage">
        <div v-if="activeStage === 'discover'">
          <GrantSourceManager />
          <GrantDiscoveryPanel />
        </div>

        <div v-else-if="activeStage === 'match'">
          <GrantMatchList @open-proposal="gotoStage('plan')" />
        </div>

        <div v-else-if="activeStage === 'plan'">
          <ProposalPlanView @next="gotoStage('draft')" />
        </div>

        <div v-else-if="activeStage === 'draft'">
          <ProposalDraftEditor @next="gotoStage('package')" />
        </div>

        <div v-else-if="activeStage === 'package'">
          <SubmissionKitView />
        </div>
      </section>
    </main>

    <!-- New profile dialog -->
    <div v-if="creatingProfile" class="dialog-backdrop" @click.self="creatingProfile = false">
      <GlassPanel title="New applicant profile" icon="badge" class="dialog">
        <div class="dialog__body">
          <label>
            <span>Profile name</span>
            <input
              v-model="newProfileName"
              placeholder="e.g. Opensens Labs"
              autofocus
            />
          </label>
          <label>
            <span>Markdown context (edit the template)</span>
            <textarea v-model="newProfileMarkdown" rows="18" />
          </label>
          <p class="dialog__hint">
            The markdown is the source of truth. The matcher reads this directly;
            you can edit it any time to refine how your profile is understood.
          </p>
        </div>
        <div class="dialog__actions">
          <button class="btn-ghost" @click="creatingProfile = false">Cancel</button>
          <button class="btn-primary" @click="handleCreateProfile">
            <span class="material-icons">check</span>
            Create profile
          </button>
        </div>
      </GlassPanel>
    </div>
  </div>
</template>

<style scoped>
.grant-hunt {
  padding: 1.25rem 1.75rem 2.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  max-width: 1680px;
  margin: 0 auto;
}

.grant-hunt__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.grant-hunt__title {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.grant-hunt__title .material-icons {
  font-size: 1.9rem;
  align-self: center;
  color: var(--color-accent, #7aa2ff);
}

.grant-hunt__title h1 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
}

.grant-hunt__subtitle {
  font-size: 0.85rem;
  color: var(--color-text-muted, #8e95a8);
}

.grant-hunt__profile-switch {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.grant-hunt__profile-switch label {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted, #8e95a8);
}

.grant-hunt__profile-switch select {
  background: var(--color-surface, rgba(255, 255, 255, 0.04));
  color: inherit;
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.08));
  padding: 0.4rem 0.7rem;
  border-radius: 6px;
  min-width: 220px;
  font: inherit;
}

.btn-primary,
.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.45rem 0.9rem;
  border-radius: 6px;
  font: inherit;
  font-size: 0.85rem;
  border: 1px solid transparent;
  cursor: pointer;
}

.btn-primary {
  background: var(--color-accent, #7aa2ff);
  color: #0b0f18;
  font-weight: 600;
}

.btn-primary:hover {
  filter: brightness(1.08);
}

.btn-ghost {
  background: transparent;
  color: inherit;
  border-color: var(--color-border, rgba(255, 255, 255, 0.12));
}

.btn-ghost:hover {
  background: rgba(255, 255, 255, 0.04);
}

/* Stage tracker */
.stage-tracker {
  display: flex;
  gap: 0.6rem;
  padding: 0.75rem;
  background: var(--color-surface-raised, rgba(255, 255, 255, 0.03));
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.06));
  border-radius: 14px;
  overflow-x: auto;
}

.stage-tracker__step {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.6rem 1rem;
  border-radius: 10px;
  background: transparent;
  color: inherit;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease, transform 120ms ease;
  font: inherit;
  font-size: 0.88rem;
  min-width: 130px;
}

.stage-tracker__step:hover {
  background: rgba(255, 255, 255, 0.04);
}

.stage-tracker__step.is-active {
  background: rgba(122, 162, 255, 0.12);
  border-color: rgba(122, 162, 255, 0.38);
  transform: translateY(-1px);
}

.stage-tracker__index {
  font-weight: 700;
  font-size: 0.72rem;
  width: 1.2rem;
  height: 1.2rem;
  border-radius: 50%;
  background: rgba(122, 162, 255, 0.18);
  color: var(--color-accent, #7aa2ff);
  display: grid;
  place-items: center;
}

.stage-tracker__step .material-icons {
  font-size: 1.1rem;
}

/* KPIs */
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.75rem;
}

.kpi {
  background: var(--color-surface-raised, rgba(255, 255, 255, 0.03));
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.06));
  border-radius: 12px;
  padding: 0.85rem 1rem;
}

.kpi__value {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--color-text, inherit);
}

.kpi__label {
  font-size: 0.74rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-muted, #8e95a8);
}

/* Body layout */
.grant-hunt__body {
  display: grid;
  grid-template-columns: minmax(320px, 380px) 1fr;
  gap: 1.25rem;
}

@media (max-width: 1100px) {
  .grant-hunt__body {
    grid-template-columns: 1fr;
  }
}

.grant-hunt__stage {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Dialog */
.dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(8, 10, 18, 0.72);
  display: grid;
  place-items: center;
  z-index: 100;
  backdrop-filter: blur(4px);
}

.dialog {
  width: min(720px, calc(100vw - 2rem));
  max-height: calc(100vh - 4rem);
  overflow: auto;
}

.dialog__body {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.dialog__body label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.78rem;
  color: var(--color-text-muted, #8e95a8);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.dialog__body input,
.dialog__body textarea {
  background: var(--color-surface, rgba(255, 255, 255, 0.04));
  color: inherit;
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.08));
  border-radius: 8px;
  padding: 0.55rem 0.75rem;
  font: inherit;
  font-size: 0.9rem;
  text-transform: none;
  letter-spacing: normal;
}

.dialog__body textarea {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.82rem;
  line-height: 1.5;
  min-height: 320px;
  resize: vertical;
}

.dialog__hint {
  margin: 0;
  font-size: 0.78rem;
  color: var(--color-text-muted, #8e95a8);
}

.dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
}
</style>

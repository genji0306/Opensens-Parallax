<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { useGrantsStore } from '@/stores/grants'

const store = useGrantsStore()

const editing = ref(false)
const draftMarkdown = ref('')
const draftName = ref('')

const profile = computed(() => store.activeProfile)

const summary = computed<string>(() => {
  const p = profile.value
  if (!p) return ''
  const parsed = (p.parsed_fields as Record<string, unknown>) || {}
  const bits: string[] = []
  if (typeof parsed.name === 'string' && parsed.name) bits.push(parsed.name)
  if (typeof parsed.stage === 'string' && parsed.stage) bits.push(parsed.stage)
  if (typeof parsed.country === 'string' && parsed.country) bits.push(parsed.country)
  if (typeof parsed.sector === 'string' && parsed.sector) bits.push(parsed.sector)
  return bits.join(' · ')
})

function startEdit(): void {
  if (!profile.value) return
  draftMarkdown.value = profile.value.markdown
  draftName.value = profile.value.name
  editing.value = true
}

async function save(): Promise<void> {
  if (!profile.value) return
  await store.updateProfile(profile.value.profile_id, {
    name: draftName.value,
    markdown: draftMarkdown.value,
  })
  editing.value = false
}

async function remove(): Promise<void> {
  if (!profile.value) return
  if (!confirm(`Delete profile "${profile.value.name}"?`)) return
  await store.removeProfile(profile.value.profile_id)
}

watch(
  () => profile.value?.profile_id,
  () => {
    editing.value = false
  },
)
</script>

<template>
  <div class="profile-editor">
    <div v-if="!profile" class="empty">
      <p>No profile selected.</p>
      <p class="empty__hint">Create one to get started.</p>
    </div>

    <div v-else>
      <div v-if="!editing">
        <div class="profile-editor__meta">
          <h3>{{ profile.name }}</h3>
          <p class="profile-editor__summary">{{ summary || 'Profile filled, no structured summary yet.' }}</p>
        </div>

        <pre class="profile-editor__markdown">{{ profile.markdown }}</pre>

        <div class="profile-editor__actions">
          <button class="btn-ghost" @click="startEdit">
            <span class="material-icons">edit</span>
            Edit
          </button>
          <button class="btn-ghost danger" @click="remove">
            <span class="material-icons">delete</span>
            Delete
          </button>
        </div>
      </div>

      <div v-else class="profile-editor__form">
        <label>
          <span>Name</span>
          <input v-model="draftName" />
        </label>
        <label>
          <span>Markdown</span>
          <textarea v-model="draftMarkdown" rows="22" />
        </label>
        <div class="profile-editor__actions">
          <button class="btn-ghost" @click="editing = false">Cancel</button>
          <button class="btn-primary" @click="save">Save</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.profile-editor h3 {
  margin: 0 0 0.25rem;
  font-size: 1rem;
}

.profile-editor__summary {
  margin: 0 0 0.75rem;
  font-size: 0.8rem;
  color: var(--color-text-muted, #8e95a8);
}

.profile-editor__markdown {
  background: rgba(0, 0, 0, 0.22);
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.06));
  border-radius: 8px;
  padding: 0.75rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.76rem;
  line-height: 1.5;
  max-height: 320px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.profile-editor__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.4rem;
  margin-top: 0.75rem;
}

.btn-primary,
.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.35rem 0.7rem;
  border-radius: 6px;
  font: inherit;
  font-size: 0.8rem;
  border: 1px solid transparent;
  cursor: pointer;
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

.btn-ghost.danger {
  color: #ff8e8e;
  border-color: rgba(255, 142, 142, 0.4);
}

.profile-editor__form label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.76rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted, #8e95a8);
  margin-bottom: 0.6rem;
}

.profile-editor__form input,
.profile-editor__form textarea {
  background: var(--color-surface, rgba(255, 255, 255, 0.04));
  color: inherit;
  border: 1px solid var(--color-border, rgba(255, 255, 255, 0.08));
  border-radius: 6px;
  padding: 0.5rem 0.7rem;
  font: inherit;
  font-size: 0.82rem;
  text-transform: none;
  letter-spacing: normal;
}

.profile-editor__form textarea {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.78rem;
  line-height: 1.5;
  min-height: 280px;
  resize: vertical;
}

.empty {
  color: var(--color-text-muted, #8e95a8);
  font-size: 0.85rem;
  text-align: center;
  padding: 1.25rem 0;
}

.empty__hint {
  margin-top: 0.3rem;
  font-size: 0.78rem;
  opacity: 0.75;
}
</style>

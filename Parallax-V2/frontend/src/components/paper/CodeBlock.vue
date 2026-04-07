<script setup lang="ts">
const props = withDefaults(defineProps<{
  code: string
  language?: string
  filename?: string
}>(), {
  language: 'python',
  filename: undefined,
})

import { ref } from 'vue'
const copied = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

async function copy() {
  try {
    await navigator.clipboard.writeText(props.code)
    copied.value = true
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => { copied.value = false }, 2000)
  } catch { /* ignore */ }
}
</script>

<template>
  <div class="code-block">
    <div class="cb-header">
      <span class="cb-lang">{{ language }}</span>
      <span v-if="filename" class="cb-filename font-mono">{{ filename }}</span>
      <button class="cb-copy" :class="{ 'cb-copy--done': copied }" @click="copy">
        <span class="material-symbols-outlined" style="font-size: 13px">
          {{ copied ? 'check' : 'content_copy' }}
        </span>
        {{ copied ? 'Copied' : 'Copy' }}
      </button>
    </div>
    <pre class="cb-pre"><code>{{ code }}</code></pre>
  </div>
</template>

<style scoped>
.code-block {
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-primary);
}

.cb-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-secondary);
}

.cb-lang {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--os-brand);
  padding: 1px 6px;
  background: var(--os-brand-light);
  border-radius: var(--radius-sm);
}

.cb-filename {
  font-size: 11px;
  color: var(--text-tertiary);
  flex: 1;
}

.cb-copy {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-family: var(--font-sans);
  font-size: 11px;
  color: var(--text-tertiary);
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
  margin-left: auto;
}

.cb-copy:hover { color: var(--text-primary); background: var(--bg-hover); }
.cb-copy--done { color: var(--success) !important; }

.cb-pre {
  margin: 0;
  padding: 14px 16px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.65;
  color: var(--text-secondary);
  white-space: pre;
  overflow-x: auto;
  max-height: 400px;
}

.cb-pre code {
  font-family: inherit;
  font-size: inherit;
  color: inherit;
  background: none;
}
</style>

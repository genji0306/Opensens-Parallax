<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { marked } from 'marked'

const props = withDefaults(defineProps<{
  draft: string
  wordCount?: number | null
}>(), {
  wordCount: null,
})

const viewMode = ref<'rendered' | 'raw'>('rendered')
const copied = ref(false)
let copyTimer: ReturnType<typeof setTimeout> | null = null

// Configure marked for paper-quality rendering
onMounted(() => {
  marked.setOptions({
    async: false,
    gfm: true,
    breaks: false,
  })
})

const renderedHtml = computed<string>(() => {
  if (!props.draft) return '<p class="empty-hint-inline">No draft content available.</p>'
  try {
    const result = marked.parse(props.draft)
    return typeof result === 'string' ? result : String(result)
  } catch {
    return `<pre class="fallback-raw">${escapeHtml(props.draft)}</pre>`
  }
})

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

const estimatedReadTime = computed<string>(() => {
  const wc = props.wordCount ?? (props.draft?.split(/\s+/).length ?? 0)
  const mins = Math.max(1, Math.round(wc / 220))
  return `~${mins} min read`
})

async function copyDraft() {
  if (!props.draft) return
  try {
    await navigator.clipboard.writeText(props.draft)
    copied.value = true
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // Clipboard API not available
  }
}
</script>

<template>
  <div class="manuscript-viewer">
    <!-- Header bar -->
    <div class="mv-header">
      <div class="mv-meta">
        <span v-if="wordCount !== null" class="mv-stat font-mono">{{ wordCount.toLocaleString() }} words</span>
        <span class="mv-stat mv-stat--dim">{{ estimatedReadTime }}</span>
      </div>
      <div class="mv-controls">
        <!-- View toggle -->
        <div class="mv-toggle" role="group">
          <button
            class="mv-toggle__btn"
            :class="{ 'mv-toggle__btn--active': viewMode === 'rendered' }"
            @click="viewMode = 'rendered'"
          >
            <span class="material-symbols-outlined" style="font-size: 14px">article</span>
            Rendered
          </button>
          <button
            class="mv-toggle__btn"
            :class="{ 'mv-toggle__btn--active': viewMode === 'raw' }"
            @click="viewMode = 'raw'"
          >
            <span class="material-symbols-outlined" style="font-size: 14px">code</span>
            Raw
          </button>
        </div>
        <!-- Copy button -->
        <button class="mv-copy-btn" :class="{ 'mv-copy-btn--done': copied }" @click="copyDraft">
          <span class="material-symbols-outlined" style="font-size: 14px">
            {{ copied ? 'check' : 'content_copy' }}
          </span>
          {{ copied ? 'Copied!' : 'Copy' }}
        </button>
      </div>
    </div>

    <!-- Content area -->
    <div class="mv-body">
      <!-- Rendered Markdown -->
      <div
        v-if="viewMode === 'rendered'"
        class="mv-prose"
        v-html="renderedHtml"
      />
      <!-- Raw text -->
      <pre v-else class="mv-raw">{{ draft || 'No content available.' }}</pre>
    </div>
  </div>
</template>

<style scoped>
.manuscript-viewer {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* ── Header ── */
.mv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  flex-wrap: wrap;
}

.mv-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mv-stat {
  font-size: 11px;
  color: var(--text-secondary);
}

.mv-stat--dim {
  color: var(--text-tertiary);
}

.mv-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Toggle button group */
.mv-toggle {
  display: flex;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.mv-toggle__btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 500;
  color: var(--text-tertiary);
  background: none;
  border: none;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
  white-space: nowrap;
}

.mv-toggle__btn:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.mv-toggle__btn--active {
  background: var(--os-brand);
  color: var(--text-on-brand);
}

.mv-toggle__btn--active:hover {
  background: var(--os-brand-hover);
}

/* Copy button */
.mv-copy-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 500;
  color: var(--text-tertiary);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
}

.mv-copy-btn:hover {
  color: var(--os-brand);
  border-color: var(--os-brand);
}

.mv-copy-btn--done {
  color: var(--success);
  border-color: var(--success);
  background: rgba(34, 197, 94, 0.08);
}

/* ── Body ── */
.mv-body {
  max-height: 560px;
  overflow-y: auto;
  border-radius: var(--radius-md);
  background: var(--bg-primary);
  border: 1px solid var(--border-secondary);
}

/* ── Raw view ── */
.mv-raw {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  padding: 16px;
}

/* ── Rendered Prose ── */
.mv-prose {
  padding: 20px 24px;
  color: var(--text-primary);
  line-height: 1.75;
  font-size: 14px;
}

/* Heading hierarchy */
:deep(.mv-prose h1) {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-secondary);
  letter-spacing: -0.01em;
}

:deep(.mv-prose h2) {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 24px 0 10px;
  letter-spacing: -0.01em;
}

:deep(.mv-prose h3) {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 20px 0 8px;
}

:deep(.mv-prose h4),
:deep(.mv-prose h5),
:deep(.mv-prose h6) {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 16px 0 6px;
}

/* Paragraphs */
:deep(.mv-prose p) {
  margin: 0 0 12px;
  color: var(--text-secondary);
}

/* Lists */
:deep(.mv-prose ul),
:deep(.mv-prose ol) {
  margin: 0 0 12px;
  padding-left: 24px;
  color: var(--text-secondary);
}

:deep(.mv-prose li) {
  margin-bottom: 4px;
  line-height: 1.65;
}

/* Inline code */
:deep(.mv-prose code) {
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--bg-tertiary);
  color: var(--os-brand);
  padding: 1px 5px;
  border-radius: 4px;
  border: 1px solid var(--border-secondary);
}

/* Code blocks */
:deep(.mv-prose pre) {
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  overflow-x: auto;
  margin: 12px 0;
}

:deep(.mv-prose pre code) {
  background: none;
  border: none;
  padding: 0;
  color: var(--text-secondary);
  font-size: 12px;
}

/* Blockquotes (abstracts, highlights) */
:deep(.mv-prose blockquote) {
  border-left: 3px solid var(--os-brand);
  margin: 12px 0;
  padding: 8px 16px;
  background: var(--os-brand-light);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  color: var(--text-secondary);
  font-style: italic;
}

/* Tables */
:deep(.mv-prose table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  margin: 12px 0;
}

:deep(.mv-prose th) {
  text-align: left;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-tertiary);
  padding: 6px 10px;
  border-bottom: 1px solid var(--border-primary);
}

:deep(.mv-prose td) {
  padding: 7px 10px;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-secondary);
  vertical-align: top;
}

/* Strong / em */
:deep(.mv-prose strong) {
  font-weight: 600;
  color: var(--text-primary);
}

:deep(.mv-prose em) {
  color: var(--text-secondary);
}

/* Horizontal rules (section separators) */
:deep(.mv-prose hr) {
  border: none;
  border-top: 1px solid var(--border-secondary);
  margin: 20px 0;
}

/* Links */
:deep(.mv-prose a) {
  color: var(--os-brand);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.empty-hint-inline {
  color: var(--text-tertiary);
  font-size: 12px;
  font-style: italic;
  padding: 16px;
}

.fallback-raw {
  font-family: var(--font-mono);
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-secondary);
}
</style>

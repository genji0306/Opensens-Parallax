<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useDebugStore } from '@/stores/debug'
import { useSystemStore } from '@/stores/system'
import { useProjectsStore } from '@/stores/projects'
import { usePipelineStore } from '@/stores/pipeline'
import type { RequestLog } from '@/stores/debug'

const debug = useDebugStore()
const system = useSystemStore()
const projects = useProjectsStore()
const pipeline = usePipelineStore()

const activeTab = ref<'requests' | 'stores' | 'health'>('requests')
const now = ref(Date.now())
let tick: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  tick = setInterval(() => { now.value = Date.now() }, 500)
})
onUnmounted(() => {
  if (tick) clearInterval(tick)
})

// Keyboard shortcut
function handleKey(e: KeyboardEvent) {
  if (e.ctrlKey && e.shiftKey && e.key === 'D') {
    e.preventDefault()
    debug.toggle()
  }
}
onMounted(() => window.addEventListener('keydown', handleKey))
onUnmounted(() => window.removeEventListener('keydown', handleKey))

const backendStatus = computed(() => system.backendOnline ? 'Online' : 'Offline')
const backendClass = computed(() => system.backendOnline ? 'tag--ok' : 'tag--err')

function elapsed(log: RequestLog): string {
  if (log.duration != null) return `${log.duration}ms`
  return `${now.value - log.startedAt}ms...`
}

function statusClass(log: RequestLog): string {
  if (log.status === 'ok') return 'req--ok'
  if (log.status === 'error') return 'req--err'
  return 'req--pending'
}

function formatSize(bytes?: number): string {
  if (bytes == null) return '--'
  if (bytes < 1024) return `${bytes}B`
  return `${(bytes / 1024).toFixed(1)}KB`
}

function shortUrl(url: string): string {
  return url.replace('/api/research/', '/')
}
</script>

<template>
  <Teleport to="body">
    <!-- Toggle button (always visible in dev) -->
    <button
      class="debug-toggle"
      :class="{ 'debug-toggle--errors': debug.errorCount > 0 }"
      title="Debug Panel (Ctrl+Shift+D)"
      @click="debug.toggle()"
    >
      <span style="font-size: 14px">
        {{ debug.errorCount > 0 ? debug.errorCount : debug.pendingCount > 0 ? '...' : 'D' }}
      </span>
    </button>

    <!-- Panel -->
    <Transition name="panel">
      <div v-if="debug.visible" class="debug-panel">
        <div class="dp-header">
          <span class="dp-title">Debug</span>
          <div class="dp-tabs">
            <button :class="{ active: activeTab === 'requests' }" @click="activeTab = 'requests'">
              Requests
              <span v-if="debug.pendingCount" class="dp-badge dp-badge--pending">{{ debug.pendingCount }}</span>
              <span v-if="debug.errorCount" class="dp-badge dp-badge--err">{{ debug.errorCount }}</span>
            </button>
            <button :class="{ active: activeTab === 'stores' }" @click="activeTab = 'stores'">Stores</button>
            <button :class="{ active: activeTab === 'health' }" @click="activeTab = 'health'">Health</button>
          </div>
          <button class="dp-close" @click="debug.toggle()">x</button>
        </div>

        <!-- ── Requests Tab ── -->
        <div v-if="activeTab === 'requests'" class="dp-body">
          <div class="dp-summary">
            <span class="tag tag--ok">{{ debug.okCount }} ok</span>
            <span class="tag tag--err">{{ debug.errorCount }} err</span>
            <span class="tag tag--pending">{{ debug.pendingCount }} pending</span>
            <span class="tag">avg {{ debug.avgDuration }}ms</span>
            <button class="dp-btn" @click="debug.clear()">Clear</button>
          </div>
          <div class="dp-list">
            <div
              v-for="log in debug.requests"
              :key="log.id"
              class="req-row"
              :class="statusClass(log)"
            >
              <span class="req-method">{{ log.method }}</span>
              <span class="req-url" :title="log.url">{{ shortUrl(log.url) }}</span>
              <span class="req-status">
                {{ log.statusCode ?? (log.status === 'pending' ? '...' : '--') }}
              </span>
              <span class="req-time">{{ elapsed(log) }}</span>
              <span class="req-size">{{ formatSize(log.size) }}</span>
              <span v-if="log.error" class="req-error" :title="log.error">{{ log.error }}</span>
            </div>
            <div v-if="debug.requests.length === 0" class="dp-empty">No requests yet</div>
          </div>
        </div>

        <!-- ── Stores Tab ── -->
        <div v-if="activeTab === 'stores'" class="dp-body">
          <div class="store-section">
            <div class="store-name">projects</div>
            <div class="store-row"><span>loading</span><span :class="projects.loading ? 'val-active' : 'val-off'">{{ projects.loading }}</span></div>
            <div class="store-row"><span>error</span><span :class="projects.error ? 'val-err' : 'val-off'">{{ projects.error ?? 'null' }}</span></div>
            <div class="store-row"><span>recent.length</span><span>{{ projects.recent.length }}</span></div>
            <div class="store-row"><span>all.length</span><span>{{ projects.all.length }}</span></div>
          </div>
          <div class="store-section">
            <div class="store-name">system</div>
            <div class="store-row"><span>backendOnline</span><span :class="system.backendOnline ? 'val-ok' : 'val-err'">{{ system.backendOnline }}</span></div>
            <div class="store-row"><span>loading</span><span :class="system.loading ? 'val-active' : 'val-off'">{{ system.loading }}</span></div>
            <div class="store-row"><span>providers</span><span>{{ system.providers ? system.providers.active_provider : 'null' }}</span></div>
            <div class="store-row"><span>tools.length</span><span>{{ system.tools.length }}</span></div>
            <div class="store-row"><span>sessionCost</span><span>${{ system.sessionCost.toFixed(2) }}</span></div>
          </div>
          <div class="store-section">
            <div class="store-name">pipeline</div>
            <div class="store-row"><span>activeRunId</span><span>{{ pipeline.activeRunId ?? 'null' }}</span></div>
            <div class="store-row"><span>title</span><span>{{ pipeline.projectTitle || 'null' }}</span></div>
            <div class="store-row"><span>status</span><span :class="pipeline.projectStatus === 'failed' ? 'val-err' : pipeline.projectStatus === 'completed' ? 'val-ok' : 'val-active'">{{ pipeline.projectStatus || 'null' }}</span></div>
            <div class="store-row"><span>pipelineError</span><span :class="pipeline.projectError ? 'val-err' : 'val-off'">{{ pipeline.projectError ?? 'null' }}</span></div>
            <div class="store-row"><span>loading</span><span :class="pipeline.loading ? 'val-active' : 'val-off'">{{ pipeline.loading }}</span></div>
            <div class="store-row"><span>error</span><span :class="pipeline.error ? 'val-err' : 'val-off'">{{ pipeline.error ?? 'null' }}</span></div>
            <div class="store-row"><span>progress</span><span>{{ pipeline.progressPercent }}%</span></div>
            <div class="store-row"><span>stages done</span><span>{{ pipeline.completedStageCount }}</span></div>
          </div>
        </div>

        <!-- ── Health Tab ── -->
        <div v-if="activeTab === 'health'" class="dp-body">
          <div class="health-grid">
            <div class="health-card">
              <div class="health-label">Backend</div>
              <div class="health-value" :class="backendClass">{{ backendStatus }}</div>
              <div class="health-detail">:5002 Flask API</div>
            </div>
            <div class="health-card">
              <div class="health-label">LLM Provider</div>
              <div class="health-value" :class="system.providers ? 'tag--ok' : 'tag--err'">
                {{ system.providers?.active_provider ?? 'N/A' }}
              </div>
              <div class="health-detail">{{ system.providers?.active_model ?? '--' }}</div>
            </div>
            <div class="health-card">
              <div class="health-label">Proxy</div>
              <div class="health-value" :class="system.providers?.proxy ? 'tag--ok' : 'tag--err'">
                {{ system.providers?.proxy?.status ?? 'N/A' }}
              </div>
              <div class="health-detail">{{ system.providers?.proxy?.url ?? '--' }}</div>
            </div>
            <div class="health-card">
              <div class="health-label">Tools</div>
              <div class="health-value">{{ system.tools.length }} loaded</div>
              <div class="health-detail">
                <span v-for="t in system.tools" :key="t.name" class="tool-chip" :class="`tool--${t.status}`">
                  {{ t.name }}
                </span>
                <span v-if="system.tools.length === 0">--</span>
              </div>
            </div>
            <div class="health-card">
              <div class="health-label">AutoResearch</div>
              <div class="health-value">
                {{ system.autoResearchStatus?.daemon_status ?? 'N/A' }}
              </div>
              <div class="health-detail">Queue: {{ system.autoResearchStatus?.queue_depth ?? '--' }}</div>
            </div>
          </div>
          <div class="health-actions">
            <button class="dp-btn" @click="system.stopPolling(); system.startPolling()">Force Refresh</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* ── Toggle Button ── */
.debug-toggle {
  position: fixed;
  bottom: 36px;
  right: 12px;
  z-index: 9999;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 1px solid var(--border-primary);
  background: var(--bg-elevated);
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.5;
  transition: opacity 0.15s, background 0.15s, border-color 0.15s;
}
.debug-toggle:hover { opacity: 1; border-color: var(--os-brand); }
.debug-toggle--errors { opacity: 1; background: var(--error); color: #fff; border-color: var(--error); }

/* ── Panel ── */
.debug-panel {
  position: fixed;
  bottom: 36px;
  right: 12px;
  z-index: 9998;
  width: 480px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-elevated);
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  box-shadow: 0 12px 40px rgba(0,0,0,0.25);
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-primary);
  overflow: hidden;
}

.dp-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-secondary);
  flex-shrink: 0;
}
.dp-title { font-weight: 700; font-size: 11px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.06em; }
.dp-tabs { display: flex; gap: 2px; margin-left: auto; }
.dp-tabs button {
  font-family: var(--font-mono);
  font-size: 10px;
  padding: 3px 8px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
}
.dp-tabs button:hover { background: var(--bg-hover); color: var(--text-primary); }
.dp-tabs button.active { background: var(--os-brand); color: #fff; }

.dp-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 0 4px;
  border-radius: 3px;
  line-height: 1.4;
}
.dp-badge--pending { background: var(--warning); color: #000; }
.dp-badge--err { background: var(--error); color: #fff; }

.dp-close {
  font-family: var(--font-mono);
  font-size: 12px;
  background: none;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 3px;
  margin-left: 4px;
}
.dp-close:hover { background: var(--bg-hover); color: var(--text-primary); }

.dp-body {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}

/* ── Summary Bar ── */
.dp-summary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}
.tag--ok { background: rgba(34, 197, 94, 0.15); color: var(--success); }
.tag--err { background: rgba(239, 68, 68, 0.15); color: var(--error); }
.tag--pending { background: rgba(245, 158, 11, 0.15); color: var(--warning); }

.dp-btn {
  font-family: var(--font-mono);
  font-size: 10px;
  padding: 2px 8px;
  border: 1px solid var(--border-primary);
  border-radius: 4px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  cursor: pointer;
  margin-left: auto;
}
.dp-btn:hover { border-color: var(--os-brand); color: var(--os-brand); }

/* ── Request List ── */
.dp-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.req-row {
  display: grid;
  grid-template-columns: 36px 1fr 30px 50px 40px;
  gap: 6px;
  align-items: center;
  padding: 3px 6px;
  border-radius: 3px;
  transition: background 0.1s;
}
.req-row:hover { background: var(--bg-hover); }

.req--ok .req-method { color: var(--success); }
.req--err .req-method { color: var(--error); }
.req--err { background: rgba(239, 68, 68, 0.04); }
.req--pending .req-method { color: var(--warning); }

.req-method { font-weight: 700; font-size: 10px; }
.req-url { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-secondary); }
.req-status { text-align: center; font-weight: 600; }
.req-time { text-align: right; color: var(--text-tertiary); }
.req-size { text-align: right; color: var(--text-tertiary); font-size: 10px; }
.req-error {
  grid-column: 2 / -1;
  color: var(--error);
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dp-empty {
  text-align: center;
  color: var(--text-tertiary);
  padding: 20px;
}

/* ── Stores Tab ── */
.store-section {
  margin-bottom: 8px;
  border: 1px solid var(--border-secondary);
  border-radius: 4px;
  overflow: hidden;
}
.store-name {
  font-weight: 700;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 4px 8px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}
.store-row {
  display: flex;
  justify-content: space-between;
  padding: 2px 8px;
  border-top: 1px solid var(--border-secondary);
}
.store-row span:first-child { color: var(--text-tertiary); }
.store-row span:last-child { font-weight: 600; }

.val-ok { color: var(--success); }
.val-err { color: var(--error); }
.val-active { color: var(--warning); }
.val-off { color: var(--text-tertiary); }

/* ── Health Tab ── */
.health-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-bottom: 8px;
}
.health-card {
  padding: 8px 10px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: 4px;
}
.health-label { font-size: 10px; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 2px; }
.health-value { font-size: 12px; font-weight: 700; margin-bottom: 2px; }
.health-detail { font-size: 10px; color: var(--text-tertiary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.health-actions { display: flex; gap: 6px; }

.tool-chip {
  display: inline-block;
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 3px;
  margin-right: 3px;
}
.tool--online { background: rgba(34, 197, 94, 0.15); color: var(--success); }
.tool--degraded { background: rgba(245, 158, 11, 0.15); color: var(--warning); }
.tool--offline { background: rgba(239, 68, 68, 0.15); color: var(--error); }

/* ── Transition ── */
.panel-enter-active { transition: opacity 0.15s, transform 0.15s; }
.panel-leave-active { transition: opacity 0.1s, transform 0.1s; }
.panel-enter-from, .panel-leave-to { opacity: 0; transform: translateY(8px) scale(0.97); }

@media (max-width: 520px) {
  .debug-panel { width: calc(100vw - 24px); left: 12px; right: 12px; }
}
</style>

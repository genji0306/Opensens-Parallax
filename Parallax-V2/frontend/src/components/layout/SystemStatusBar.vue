<script setup lang="ts">
import { computed } from 'vue'
import { useSystemStore } from '@/stores/system'
import StatusBadge from '@/components/shared/StatusBadge.vue'

const system = useSystemStore()

const llmStatus = computed<'online' | 'degraded' | 'offline'>(() => {
  if (system.loading) return 'degraded'
  if (!system.providers) return 'offline'
  return 'online'
})

const llmLabel = computed(() => {
  if (system.loading) return 'LLM: Connecting...'
  if (!system.providers) return 'LLM: Offline'
  return `LLM: ${system.providers.active_provider}/${system.providers.active_model}`
})

const proxyStatus = computed<'online' | 'degraded' | 'offline'>(() => {
  if (!system.providers?.proxy) return 'offline'
  const s = system.providers.proxy.status
  if (s === 'online' || s === 'ok' || s === 'connected' || s === 'active') return 'online'
  if (s === 'configured') return 'degraded'
  if (s === 'unconfigured' || s === 'offline') return 'offline'
  return 'degraded'
})

const proxyLabel = computed(() => {
  if (!system.providers?.proxy) return 'Proxy: N/A'
  return `Proxy: ${system.providers.proxy.status}`
})

const scienceClawStatus = computed<'online' | 'degraded' | 'offline'>(() => {
  const tool = system.tools.find(t => t.name.toLowerCase().includes('scienceclaw'))
  if (!tool) return 'offline'
  return tool.status
})

const autoResearchLabel = computed(() => {
  if (!system.autoResearchStatus) return 'Queue: --'
  const ar = system.autoResearchStatus
  return `Queue: ${ar.queue_depth} | ${ar.daemon_status}`
})

const autoResearchBadge = computed<'online' | 'degraded' | 'offline'>(() => {
  if (!system.autoResearchStatus) return 'offline'
  const s = system.autoResearchStatus.daemon_status
  if (s === 'running') return 'online'
  if (s === 'idle') return 'degraded'
  return 'offline'
})

const sessionCost = computed(() =>
  `$${system.sessionCost.toFixed(2)}`
)
</script>

<template>
  <footer class="status-bar">
    <span class="status-bar__brand font-mono">PARALLAX</span>
    <div class="status-bar__divider" />

    <div class="status-bar__group" :title="llmLabel">
      <StatusBadge :status="llmStatus" size="sm" />
      <span class="status-bar__label">{{ system.providers?.active_model || 'LLM' }}</span>
    </div>

    <div class="status-bar__divider" />

    <div class="status-bar__group" :title="proxyLabel">
      <StatusBadge :status="proxyStatus" size="sm" />
      <span class="status-bar__label">Proxy</span>
    </div>

    <div class="status-bar__divider" />

    <div class="status-bar__group">
      <StatusBadge :status="scienceClawStatus" size="sm" />
      <span class="status-bar__label">ScienceClaw</span>
    </div>

    <div class="status-bar__divider" />

    <div class="status-bar__group" :title="autoResearchLabel">
      <StatusBadge :status="autoResearchBadge" size="sm" />
      <span class="status-bar__label">Queue{{ system.autoResearchStatus ? `: ${system.autoResearchStatus.queue_depth}` : '' }}</span>
    </div>

    <div class="status-bar__spacer" />

    <div class="status-bar__group">
      <span class="status-bar__cost font-mono">{{ sessionCost }}</span>
    </div>
  </footer>
</template>

<style scoped>
.status-bar {
  display: flex;
  align-items: center;
  height: 28px;
  padding: 0 16px;
  background: var(--bg-tertiary);
  border-top: 1px solid var(--border-secondary);
  flex-shrink: 0;
  z-index: 100;
  overflow-x: auto;
  transition:
    background var(--transition-normal),
    border-color var(--transition-normal);
}

.status-bar__group {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
}

.status-bar__divider {
  width: 1px;
  height: 12px;
  margin: 0 12px;
  background: var(--border-primary);
  flex-shrink: 0;
}

.status-bar__spacer {
  flex: 1;
}

.status-bar__brand {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--os-brand);
  flex-shrink: 0;
}

.status-bar__label {
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.status-bar__cost {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-tertiary);
  letter-spacing: -0.01em;
}

/* Hide overflow labels on very small screens */
@media (max-width: 640px) {
  .status-bar {
    padding: 0 8px;
    gap: 0;
  }

  .status-bar__divider {
    margin: 0 6px;
  }
}
</style>

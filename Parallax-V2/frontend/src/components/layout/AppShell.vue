<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useSystemStore } from '@/stores/system'
import { useV3Store } from '@/stores/v3'
import AppHeader from './AppHeader.vue'
import SystemStatusBar from './SystemStatusBar.vue'
import DebugPanel from './DebugPanel.vue'
import EventTimeline from './EventTimeline.vue'

const system = useSystemStore()
const v3 = useV3Store()
const showTimeline = ref(false)

onMounted(() => {
  system.startPolling()
  v3.loadTemplates()
})

onUnmounted(() => {
  system.stopPolling()
  v3.disconnectEventStream()
})
</script>

<template>
  <div class="app-shell">
    <AppHeader />
    <main class="app-shell__content">
      <slot />
    </main>
    <EventTimeline v-if="showTimeline" />
    <SystemStatusBar />
    <DebugPanel />

    <!-- Timeline toggle button -->
    <button
      class="app-shell__timeline-toggle"
      :class="{ 'app-shell__timeline-toggle--active': showTimeline }"
      title="Toggle DRVP event timeline"
      @click="showTimeline = !showTimeline"
    >
      <span class="material-symbols-outlined">terminal</span>
      <span v-if="v3.events.length > 0" class="app-shell__event-count">{{ v3.events.length }}</span>
    </button>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  min-height: 0;
  background: var(--bg-primary);
  transition: background var(--transition-normal);
  position: relative;
}

.app-shell__content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
}

.app-shell__timeline-toggle {
  position: fixed;
  bottom: 36px;
  right: 16px;
  width: 36px;
  height: 36px;
  border: 1px solid var(--border-primary, #333);
  border-radius: 8px;
  background: var(--bg-elevated, #1a1a1a);
  color: var(--text-secondary, #888);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  transition: all 0.15s ease;
}

.app-shell__timeline-toggle:hover {
  color: var(--text-primary, #fff);
  background: var(--bg-hover, #222);
}

.app-shell__timeline-toggle--active {
  color: var(--os-brand, #3b82f6);
  border-color: var(--os-brand, #3b82f6);
}

.app-shell__timeline-toggle .material-symbols-outlined {
  font-size: 18px;
}

.app-shell__event-count {
  position: absolute;
  top: -4px;
  right: -4px;
  font-size: 9px;
  font-weight: 700;
  color: #fff;
  background: var(--os-brand, #3b82f6);
  border-radius: 8px;
  padding: 0 4px;
  min-width: 14px;
  text-align: center;
  line-height: 14px;
}
</style>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useSystemStore } from '@/stores/system'
import AppHeader from './AppHeader.vue'
import SystemStatusBar from './SystemStatusBar.vue'
import DebugPanel from './DebugPanel.vue'

const system = useSystemStore()

onMounted(() => {
  system.startPolling()
})

onUnmounted(() => {
  system.stopPolling()
})
</script>

<template>
  <div class="app-shell">
    <AppHeader />
    <main class="app-shell__content">
      <slot />
    </main>
    <SystemStatusBar />
    <DebugPanel />
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
</style>

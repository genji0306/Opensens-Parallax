<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useUiStore } from '@/stores/ui'

const props = withDefaults(defineProps<{
  simulationId: string
  height?: number
}>(), {
  height: 500,
})

const ui = useUiStore()
const iframeRef = ref<HTMLIFrameElement | null>(null)
const loading = ref(true)

const agentOfficeUrl = computed(() => {
  const base = import.meta.env.VITE_AGENT_OFFICE_URL || 'http://localhost:5180'
  return `${base}/#/debate/${props.simulationId}?embed=true&theme=${ui.theme}`
})

function handleLoad() {
  loading.value = false
}

// ── Theme sync via postMessage ──
function sendThemeMessage() {
  if (iframeRef.value?.contentWindow) {
    iframeRef.value.contentWindow.postMessage(
      { type: 'parallax:theme', theme: ui.theme },
      '*',
    )
  }
}

watch(() => ui.theme, () => {
  sendThemeMessage()
})

// Listen for messages from iframe
function handleMessage(event: MessageEvent) {
  if (event.data?.type === 'agent-office:ready') {
    sendThemeMessage()
  }
}

onMounted(() => {
  window.addEventListener('message', handleMessage)
})

onUnmounted(() => {
  window.removeEventListener('message', handleMessage)
})
</script>

<template>
  <div class="debate-embed" :style="{ height: `${height}px` }">
    <!-- Loading overlay -->
    <Transition name="fade">
      <div v-if="loading" class="debate-embed__loading">
        <span class="material-symbols-outlined spin">progress_activity</span>
        <span>Loading Agent Office...</span>
      </div>
    </Transition>

    <iframe
      ref="iframeRef"
      :src="agentOfficeUrl"
      class="debate-embed__iframe"
      :style="{ height: `${height}px` }"
      frameborder="0"
      allow="autoplay; fullscreen"
      @load="handleLoad"
    />
  </div>
</template>

<style scoped>
.debate-embed {
  position: relative;
  width: 100%;
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
}

.debate-embed__iframe {
  width: 100%;
  border: none;
  display: block;
}

.debate-embed__loading {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-size: 13px;
}

.spin {
  font-size: 24px;
  color: var(--os-brand);
  animation: embed-spin 1s linear infinite;
}

@keyframes embed-spin {
  to { transform: rotate(360deg); }
}

/* ── Fade Transition ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

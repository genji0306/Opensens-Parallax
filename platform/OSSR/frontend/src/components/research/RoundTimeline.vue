<template>
  <div class="round-timeline">
    <div class="timeline-controls">
      <button class="tl-btn" @click="$emit('prev')" :disabled="currentRound <= 1" title="Previous round">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
      </button>

      <button class="tl-btn play-btn" @click="$emit(isPlaying ? 'pause' : 'play')" :disabled="maxRound === 0">
        <svg v-if="!isPlaying" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <polygon points="6 3 20 12 6 21"/>
        </svg>
        <svg v-else viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <rect x="5" y="4" width="4" height="16"/>
          <rect x="15" y="4" width="4" height="16"/>
        </svg>
      </button>

      <button class="tl-btn" @click="$emit('next')" :disabled="currentRound >= maxRound" title="Next round">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
      </button>
    </div>

    <div class="timeline-slider-wrap">
      <span class="round-label">Round</span>
      <input
        type="range"
        class="timeline-slider"
        :min="1"
        :max="maxRound || 1"
        :value="currentRound"
        :disabled="maxRound === 0"
        @input="$emit('seek', parseInt($event.target.value))"
      />
      <span class="round-display">{{ currentRound }}/{{ maxRound || '?' }}</span>
    </div>

    <div class="timeline-meta">
      <select class="speed-select" v-model="speed" @change="$emit('speed-change', speed)">
        <option value="1">1x</option>
        <option value="2">2x</option>
        <option value="4">4x</option>
      </select>

      <span v-if="isLive" class="live-dot">
        <span class="dot-pulse"></span>
        Live
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  maxRound: { type: Number, default: 0 },
  currentRound: { type: Number, default: 0 },
  isLive: { type: Boolean, default: false },
  isPlaying: { type: Boolean, default: false },
})

defineEmits(['seek', 'play', 'pause', 'next', 'prev', 'speed-change'])

const speed = ref('1')
</script>

<style scoped>
.round-timeline {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 6px 16px;
  height: 42px;
  border-top: 1px solid var(--border-primary);
  background: var(--bg-secondary);
  flex-shrink: 0;
}

.timeline-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}

.tl-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.tl-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.tl-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.play-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--os-brand);
  border-color: var(--os-brand);
  color: var(--text-on-brand);
}
.play-btn:hover:not(:disabled) {
  background: var(--os-brand-hover);
  color: var(--text-on-brand);
}

.timeline-slider-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.round-label {
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.timeline-slider {
  flex: 1;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: var(--border-primary);
  border-radius: 2px;
  outline: none;
}
.timeline-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--os-brand);
  cursor: pointer;
  border: 2px solid var(--bg-primary);
  box-shadow: var(--shadow-sm);
}
.timeline-slider:disabled::-webkit-slider-thumb {
  opacity: 0.4;
  cursor: not-allowed;
}

.round-display {
  font-size: 12px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 36px;
  text-align: right;
}

.timeline-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.speed-select {
  font-size: 11px;
  padding: 2px 6px;
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-family: var(--font-mono);
  cursor: pointer;
}

.live-dot {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--os-brand);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.dot-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--os-brand);
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}
</style>

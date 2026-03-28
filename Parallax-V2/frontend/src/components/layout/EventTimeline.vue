<script setup lang="ts">
/**
 * EventTimeline — horizontal DRVP event stream in the bottom panel.
 *
 * Shows real-time events from the V3 Gateway: phase transitions, LLM calls,
 * budget warnings, approvals, and agent activity.
 */
import { computed, onMounted, onUnmounted } from 'vue'
import { useV3Store } from '@/stores/v3'
import type { V3DRVPEvent } from '@/api/v3'

const v3 = useV3Store()

onMounted(() => {
  v3.connectEventStream()
})

onUnmounted(() => {
  v3.disconnectEventStream()
})

// ── Event Styling ────────────────────────────────────────────

const EVENT_ICONS: Record<string, string> = {
  'phase.started': '▶',
  'phase.completed': '✓',
  'phase.failed': '✗',
  'phase.restarted': '↺',
  'ideas.ready': '💡',
  'score.received': '📊',
  'feedback.loop': '🔄',
  'pipeline.completed': '🏁',
  'pipeline.failed': '❌',
  'pipeline.created': '🆕',
  'approval.required': '⏸',
  'approval.granted': '✅',
  'approval.denied': '🚫',
  'budget.warning': '⚠',
  'budget.exhausted': '🛑',
  'llm.call.started': '🤖',
  'llm.call.completed': '🤖',
  'connected': '🔗',
}

const EVENT_COLORS: Record<string, string> = {
  'phase.started': 'text-blue-400',
  'phase.completed': 'text-green-400',
  'phase.failed': 'text-red-400',
  'phase.restarted': 'text-yellow-400',
  'pipeline.completed': 'text-green-300',
  'pipeline.failed': 'text-red-300',
  'approval.required': 'text-amber-400',
  'approval.granted': 'text-green-400',
  'approval.denied': 'text-red-400',
  'budget.warning': 'text-amber-500',
  'budget.exhausted': 'text-red-500',
}

function getIcon(type: string): string {
  return EVENT_ICONS[type] || '·'
}

function getColor(type: string): string {
  return EVENT_COLORS[type] || 'text-zinc-400'
}

function formatTime(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ''
  }
}

function formatPayload(event: V3DRVPEvent): string {
  const p = event.payload
  if (event.event_type === 'phase.started' || event.event_type === 'phase.completed') {
    return p.phase_type as string || ''
  }
  if (event.event_type === 'budget.warning') {
    return `$${p.spent} / $${p.cap}`
  }
  if (event.event_type === 'score.received') {
    return `score=${p.score}`
  }
  if (event.event_type === 'pipeline.created') {
    return `${p.phase_count} phases`
  }
  return ''
}

const displayEvents = computed(() => v3.recentEvents)
</script>

<template>
  <div class="event-timeline">
    <div class="event-timeline__header">
      <span class="event-timeline__title">
        DRVP Events
        <span
          class="event-timeline__dot"
          :class="v3.eventStreamConnected ? 'event-timeline__dot--live' : 'event-timeline__dot--off'"
        />
      </span>
      <span class="event-timeline__stats">
        <span v-if="v3.totalCostUsd > 0" class="event-timeline__cost">
          ${{ v3.totalCostUsd.toFixed(2) }}
        </span>
        <span v-if="v3.pendingApprovalCount > 0" class="event-timeline__approvals">
          {{ v3.pendingApprovalCount }} pending
        </span>
        <span class="event-timeline__count">{{ v3.events.length }} events</span>
      </span>
    </div>

    <div class="event-timeline__scroll">
      <div
        v-for="event in displayEvents"
        :key="event.event_id"
        class="event-timeline__item"
        :class="getColor(event.event_type)"
      >
        <span class="event-timeline__icon">{{ getIcon(event.event_type) }}</span>
        <span class="event-timeline__type">{{ event.event_type }}</span>
        <span class="event-timeline__detail">{{ formatPayload(event) }}</span>
        <span class="event-timeline__time">{{ formatTime(event.timestamp) }}</span>
      </div>

      <div v-if="displayEvents.length === 0" class="event-timeline__empty">
        {{ v3.eventStreamConnected ? 'Waiting for events...' : 'Not connected' }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.event-timeline {
  background: var(--color-surface-1, #111);
  border-top: 1px solid var(--color-border, #333);
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  font-size: 0.7rem;
  line-height: 1.4;
  max-height: 160px;
  display: flex;
  flex-direction: column;
}

.event-timeline__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 12px;
  background: var(--color-surface-2, #1a1a1a);
  border-bottom: 1px solid var(--color-border, #333);
  flex-shrink: 0;
}

.event-timeline__title {
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-secondary, #888);
  display: flex;
  align-items: center;
  gap: 6px;
}

.event-timeline__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.event-timeline__dot--live {
  background: #22c55e;
  box-shadow: 0 0 4px #22c55e;
}

.event-timeline__dot--off {
  background: #666;
}

.event-timeline__stats {
  display: flex;
  gap: 12px;
  color: var(--color-text-secondary, #888);
}

.event-timeline__cost {
  color: #f59e0b;
  font-weight: 600;
}

.event-timeline__approvals {
  color: #ef4444;
  font-weight: 600;
}

.event-timeline__scroll {
  overflow-y: auto;
  flex: 1;
  padding: 2px 0;
}

.event-timeline__item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 12px;
  white-space: nowrap;
}

.event-timeline__item:hover {
  background: var(--color-surface-2, #1a1a1a);
}

.event-timeline__icon {
  width: 16px;
  text-align: center;
  flex-shrink: 0;
}

.event-timeline__type {
  min-width: 140px;
  color: inherit;
}

.event-timeline__detail {
  flex: 1;
  color: var(--color-text-secondary, #888);
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-timeline__time {
  color: var(--color-text-tertiary, #555);
  flex-shrink: 0;
}

.event-timeline__empty {
  padding: 8px 12px;
  color: var(--color-text-tertiary, #555);
  font-style: italic;
}
</style>

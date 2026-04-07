<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { useGrantsStore } from '@/stores/grants'
import type { AlertType, GrantAlert } from '@/types/grants'

const emit = defineEmits<{
  (e: 'navigate-opportunity', id: string): void
}>()

const store = useGrantsStore()

const open = ref(false)
const bellRef = ref<HTMLElement | null>(null)

const recentAlerts = computed<GrantAlert[]>(() =>
  [...store.alerts]
    .sort((a, b) => new Date(b.fired_at).getTime() - new Date(a.fired_at).getTime())
    .slice(0, 20),
)

function toggleDropdown(): void {
  open.value = !open.value
}

function closeDropdown(): void {
  open.value = false
}

// Close on outside click
function handleOutsideClick(e: MouseEvent): void {
  if (bellRef.value && !bellRef.value.contains(e.target as Node)) {
    open.value = false
  }
}

onMounted(() => {
  document.addEventListener('mousedown', handleOutsideClick)
})

onUnmounted(() => {
  document.removeEventListener('mousedown', handleOutsideClick)
})

// ── Alert formatting ────────────────────────────────────────────────
function alertIcon(type: AlertType): string {
  switch (type) {
    case 'new_match': return 'stars'
    case 'deadline_t1': return 'warning'
    case 'deadline_t3': return 'alarm'
    case 'deadline_t7': return 'schedule'
    case 'deadline_t14': return 'event'
    case 'watchlist_opened': return 'lock_open'
    case 'source_failure': return 'error_outline'
    default: return 'notifications'
  }
}

function alertIconColor(type: AlertType): string {
  switch (type) {
    case 'new_match': return '#7aa2ff'
    case 'deadline_t1': return '#ef4444'
    case 'deadline_t3': return '#ef4444'
    case 'deadline_t7': return '#f59e0b'
    case 'deadline_t14': return '#f59e0b'
    case 'watchlist_opened': return '#22c55e'
    case 'source_failure': return '#6b7280'
    default: return '#9ca3af'
  }
}

function alertMessage(alert: GrantAlert): string {
  const title = (alert.data?.title as string) ?? 'Grant opportunity'
  switch (alert.alert_type) {
    case 'new_match':
      return `New high-fit grant: ${title}`
    case 'deadline_t14':
      return `Deadline in 14 days: ${title}`
    case 'deadline_t7':
      return `Deadline in 7 days: ${title}`
    case 'deadline_t3':
      return `Deadline in 3 days! ${title}`
    case 'deadline_t1':
      return `TOMORROW: ${title}`
    case 'watchlist_opened':
      return `Now open for applications: ${title}`
    case 'source_failure':
      return `Source failed to crawl: ${title}`
    default:
      return title
  }
}

function isUrgent(alert: GrantAlert): boolean {
  return alert.alert_type === 'deadline_t1' || alert.alert_type === 'deadline_t3'
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

async function handleAlertClick(alert: GrantAlert): Promise<void> {
  if (!alert.seen_at) {
    await store.markAlertSeen(alert.alert_id)
  }
  if (alert.target_id) {
    emit('navigate-opportunity', alert.target_id)
  }
  closeDropdown()
}

async function markAllSeen(): Promise<void> {
  await store.markAllAlertsSeen()
}
</script>

<template>
  <div ref="bellRef" class="alert-bell">
    <button
      class="bell-btn"
      :class="{ 'bell-btn--has-unseen': store.unseenAlertCount > 0 }"
      @click="toggleDropdown"
      :aria-label="`Alerts — ${store.unseenAlertCount} unseen`"
      :aria-expanded="open"
    >
      <span class="material-icons">notifications</span>
      <span
        v-if="store.unseenAlertCount > 0"
        class="bell-badge"
        aria-hidden="true"
      >
        {{ store.unseenAlertCount > 99 ? '99+' : store.unseenAlertCount }}
      </span>
    </button>

    <!-- Dropdown -->
    <div v-if="open" class="alert-dropdown" role="menu">
      <header class="alert-dropdown__header">
        <span class="alert-dropdown__title">Alerts</span>
        <button
          v-if="store.unseenAlertCount > 0"
          class="mark-all-btn"
          @click="markAllSeen"
        >
          Mark all seen
        </button>
      </header>

      <div class="alert-list" role="list">
        <button
          v-for="alert in recentAlerts"
          :key="alert.alert_id"
          class="alert-item"
          :class="{
            'alert-item--unseen': !alert.seen_at,
            'alert-item--urgent': isUrgent(alert),
          }"
          role="menuitem"
          @click="handleAlertClick(alert)"
        >
          <span
            class="alert-item__icon material-icons"
            :style="{ color: alertIconColor(alert.alert_type) }"
          >
            {{ alertIcon(alert.alert_type) }}
          </span>
          <div class="alert-item__body">
            <p class="alert-item__message">{{ alertMessage(alert) }}</p>
            <time class="alert-item__time" :datetime="alert.fired_at">
              {{ timeAgo(alert.fired_at) }}
            </time>
          </div>
          <span v-if="!alert.seen_at" class="alert-item__dot" aria-hidden="true" />
        </button>

        <div v-if="recentAlerts.length === 0" class="alert-empty">
          No alerts yet
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.alert-bell {
  position: relative;
  display: inline-flex;
}

/* ── Bell button ──────────────────────────────────────────────────── */
.bell-btn {
  position: relative;
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: transparent;
  cursor: pointer;
  color: #9ca3af;
  transition: background 100ms, color 100ms;
}

.bell-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #d1d5db;
}

.bell-btn--has-unseen {
  color: #7aa2ff;
  border-color: rgba(122, 162, 255, 0.3);
}

.bell-btn .material-icons {
  font-size: 1.15rem;
}

.bell-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 16px;
  height: 16px;
  border-radius: 100px;
  background: #ef4444;
  color: #fff;
  font-size: 0.6rem;
  font-weight: 700;
  display: grid;
  place-items: center;
  padding: 0 3px;
  line-height: 1;
  border: 1.5px solid #030712;
}

/* ── Dropdown ─────────────────────────────────────────────────────── */
.alert-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 340px;
  max-height: 420px;
  display: flex;
  flex-direction: column;
  background: #0d1117;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.6);
  z-index: 500;
  overflow: hidden;
}

.alert-dropdown__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 0.875rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.02);
  flex-shrink: 0;
}

.alert-dropdown__title {
  font-size: 0.82rem;
  font-weight: 600;
  color: #d1d5db;
}

.mark-all-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  font: inherit;
  font-size: 0.72rem;
  color: #7aa2ff;
  transition: opacity 100ms;
}

.mark-all-btn:hover {
  opacity: 0.8;
}

/* ── Alert list ───────────────────────────────────────────────────── */
.alert-list {
  overflow-y: auto;
  flex: 1;
}

.alert-item {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  padding: 0.6rem 0.875rem;
  background: transparent;
  border: none;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  cursor: pointer;
  text-align: left;
  transition: background 80ms;
  color: inherit;
  font: inherit;
  position: relative;
}

.alert-item:last-child {
  border-bottom: none;
}

.alert-item:hover {
  background: rgba(255, 255, 255, 0.04);
}

.alert-item--unseen {
  background: rgba(122, 162, 255, 0.04);
}

.alert-item--urgent .alert-item__message {
  color: #fca5a5;
}

.alert-item__icon {
  font-size: 1.05rem;
  margin-top: 1px;
  flex-shrink: 0;
}

.alert-item__body {
  flex: 1;
  min-width: 0;
}

.alert-item__message {
  margin: 0;
  font-size: 0.8rem;
  color: #d1d5db;
  line-height: 1.4;
  word-break: break-word;
}

.alert-item__time {
  display: block;
  font-size: 0.7rem;
  color: #6b7280;
  margin-top: 0.15rem;
}

.alert-item__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #7aa2ff;
  flex-shrink: 0;
  margin-top: 4px;
}

.alert-empty {
  padding: 1.5rem;
  text-align: center;
  font-size: 0.82rem;
  color: #6b7280;
}
</style>

<template>
  <div class="analyst-feed">
    <div class="feed-title">Analyst Feed</div>
    <div v-if="filteredEntries.length === 0" class="feed-empty">
      No analyst notes yet.
    </div>
    <div ref="feedList" class="feed-list">
      <div
        v-for="entry in filteredEntries"
        :key="entry.feed_id || entry.round_num"
        class="feed-card"
        :class="{ current: entry.round_num === currentRound }"
      >
        <div class="feed-round">Round {{ entry.round_num }}</div>
        <div class="feed-narrative">{{ entry.narrative }}</div>
        <div v-if="entry.key_events?.length" class="feed-events">
          <span v-for="(evt, i) in entry.key_events" :key="i" class="event-tag">{{ evt }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'

const props = defineProps({
  entries: { type: Array, default: () => [] },
  currentRound: { type: Number, default: 0 },
})

const feedList = ref(null)

const filteredEntries = computed(() => {
  return props.entries
    .filter(e => e.round_num <= (props.currentRound || Infinity))
    .sort((a, b) => b.round_num - a.round_num)
})

watch(() => props.entries.length, () => {
  nextTick(() => {
    if (feedList.value) feedList.value.scrollTop = 0
  })
})
</script>

<style scoped>
.analyst-feed {
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  padding: 10px;
}

.feed-title {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--text-tertiary);
  margin-bottom: 8px;
}

.feed-empty {
  font-size: 12px;
  color: var(--text-tertiary);
  font-style: italic;
}

.feed-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 240px;
  overflow-y: auto;
}

.feed-card {
  padding: 8px;
  background: var(--bg-primary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-sm);
  transition: border-color var(--transition-fast);
}
.feed-card.current {
  border-color: var(--os-brand);
}

.feed-round {
  font-size: 10px;
  font-weight: 600;
  color: var(--os-brand);
  font-family: var(--font-mono);
  margin-bottom: 4px;
}

.feed-narrative {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
}

.feed-events {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.event-tag {
  font-size: 10px;
  padding: 1px 6px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-pill);
  color: var(--text-secondary);
}
</style>

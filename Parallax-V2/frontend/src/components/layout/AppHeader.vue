<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useUiStore } from '@/stores/ui'
import { useSystemStore } from '@/stores/system'
import StatusBadge from '@/components/shared/StatusBadge.vue'

const route = useRoute()
const ui = useUiStore()
const system = useSystemStore()
const navItems = [
  { name: 'command-center', label: 'Command Center', icon: 'dashboard' },
  { name: 'paper-lab', label: 'Paper Lab', icon: 'description' },
  { name: 'grant-hunt', label: 'Grant Hunt', icon: 'payments' },
  { name: 'history', label: 'History', icon: 'history' },
] as const

const sessionCost = computed(() => {
  return `$${system.sessionCost.toFixed(2)}`
})

const overallStatus = computed<'online' | 'degraded' | 'offline'>(() => {
  if (!system.providers) return 'offline'
  const hasOffline = system.tools.some(t => t.status === 'offline')
  const hasDegraded = system.tools.some(t => t.status === 'degraded')
  if (hasOffline) return 'degraded'
  if (hasDegraded) return 'degraded'
  return 'online'
})

const themeIcon = computed(() =>
  ui.theme === 'dark' ? 'light_mode' : 'dark_mode'
)
</script>

<template>
  <header class="app-header">
    <!-- Left: Brand -->
    <div class="app-header__brand">
      <span class="app-header__logo">Parallax</span>
      <span class="app-header__subtitle">Research Command Center</span>
    </div>

    <!-- Center: Navigation -->
    <nav class="app-header__nav">
      <router-link
        v-for="item in navItems"
        :key="item.name"
        :to="{ name: item.name }"
        class="app-header__nav-link"
        :class="{ 'app-header__nav-link--active': route.name === item.name }"
      >
        <span class="material-symbols-outlined app-header__nav-icon">{{ item.icon }}</span>
        <span class="app-header__nav-label">{{ item.label }}</span>
      </router-link>
    </nav>

    <!-- Right: Controls -->
    <div class="app-header__controls">
      <span class="app-header__cost font-mono">{{ sessionCost }}</span>

      <button
        class="app-header__icon-btn"
        :title="`Switch to ${ui.theme === 'dark' ? 'light' : 'dark'} theme`"
        @click="ui.toggleTheme()"
      >
        <span class="material-symbols-outlined">{{ themeIcon }}</span>
      </button>

      <StatusBadge :status="overallStatus" size="sm" />
    </div>
  </header>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  height: 60px;
  padding: 0 24px;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-primary);
  flex-shrink: 0;
  z-index: 100;
  transition:
    background var(--transition-normal),
    border-color var(--transition-normal);
}

/* ── Brand ── */
.app-header__brand {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-shrink: 0;
}

.app-header__logo {
  font-size: 18px;
  font-weight: 700;
  color: var(--os-brand);
  letter-spacing: -0.03em;
}

.app-header__subtitle {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* ── Navigation ── */
.app-header__nav {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 0 auto;
}

.app-header__nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  text-decoration: none;
  transition:
    color var(--transition-fast),
    background var(--transition-fast);
}

.app-header__nav-link:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.app-header__nav-link--active {
  color: var(--os-brand);
  background: var(--os-brand-light);
}

.app-header__nav-icon {
  font-size: 18px;
}

.app-header__nav-label {
  /* Hide label on small screens, show icon only */
}

/* ── Controls ── */
.app-header__controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.app-header__cost {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-tertiary);
  padding: 4px 10px;
  border-radius: var(--radius-pill);
  letter-spacing: -0.01em;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.app-header__icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast);
}

.app-header__icon-btn:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.app-header__icon-btn .material-symbols-outlined {
  font-size: 20px;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .app-header {
    padding: 0 12px;
  }

  .app-header__subtitle {
    display: none;
  }

  .app-header__nav-label {
    display: none;
  }

  .app-header__nav-link {
    padding: 6px 10px;
  }
}
</style>

import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

export type Theme = 'light' | 'dark'
export type Locale = 'en' | 'zh'

function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'dark'
  const stored = localStorage.getItem('parallax-theme')
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function getInitialLocale(): Locale {
  if (typeof window === 'undefined') return 'en'
  const stored = localStorage.getItem('parallax-locale')
  if (stored === 'en' || stored === 'zh') return stored
  return 'en'
}

export const useUiStore = defineStore('ui', () => {
  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  const theme = ref<Theme>(getInitialTheme())
  const sidebarOpen = ref(true)
  const locale = ref<Locale>(getInitialLocale())

  // ---------------------------------------------------------------------------
  // Sync theme to DOM + localStorage
  // ---------------------------------------------------------------------------
  function applyTheme(t: Theme): void {
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.theme = t
      document.documentElement.classList.toggle('dark', t === 'dark')
    }
    localStorage.setItem('parallax-theme', t)
  }

  // Apply immediately on store creation
  applyTheme(theme.value)

  watch(theme, (t) => {
    applyTheme(t)
  })

  watch(locale, (l) => {
    localStorage.setItem('parallax-locale', l)
  })

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------
  function toggleTheme(): void {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  function setTheme(t: Theme): void {
    theme.value = t
  }

  function toggleSidebar(): void {
    sidebarOpen.value = !sidebarOpen.value
  }

  return {
    theme,
    sidebarOpen,
    locale,
    toggleTheme,
    setTheme,
    toggleSidebar,
  }
})

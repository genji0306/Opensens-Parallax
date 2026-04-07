import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export interface RequestLog {
  id: number
  method: string
  url: string
  status: 'pending' | 'ok' | 'error'
  statusCode?: number
  duration?: number
  error?: string
  startedAt: number
  size?: number
}

let nextId = 1

export const useDebugStore = defineStore('debug', () => {
  const visible = ref(false)
  const requests = ref<RequestLog[]>([])
  const maxLogs = 50

  const pendingCount = computed(() => requests.value.filter(r => r.status === 'pending').length)
  const errorCount = computed(() => requests.value.filter(r => r.status === 'error').length)
  const okCount = computed(() => requests.value.filter(r => r.status === 'ok').length)

  const avgDuration = computed(() => {
    const completed = requests.value.filter(r => r.duration != null)
    if (completed.length === 0) return 0
    return Math.round(completed.reduce((sum, r) => sum + r.duration!, 0) / completed.length)
  })

  function toggle() {
    visible.value = !visible.value
  }

  function logRequest(method: string, url: string): number {
    const id = nextId++
    requests.value.unshift({
      id,
      method: method.toUpperCase(),
      url,
      status: 'pending',
      startedAt: Date.now(),
    })
    // Trim old entries
    if (requests.value.length > maxLogs) {
      requests.value = requests.value.slice(0, maxLogs)
    }
    return id
  }

  function resolveRequest(id: number, statusCode: number, size?: number) {
    const entry = requests.value.find(r => r.id === id)
    if (entry) {
      entry.status = 'ok'
      entry.statusCode = statusCode
      entry.duration = Date.now() - entry.startedAt
      entry.size = size
    }
  }

  function rejectRequest(id: number, error: string, statusCode?: number) {
    const entry = requests.value.find(r => r.id === id)
    if (entry) {
      entry.status = 'error'
      entry.error = error
      entry.statusCode = statusCode
      entry.duration = Date.now() - entry.startedAt
    }
  }

  function clear() {
    requests.value = []
  }

  return {
    visible,
    requests,
    pendingCount,
    errorCount,
    okCount,
    avgDuration,
    toggle,
    logRequest,
    resolveRequest,
    rejectRequest,
    clear,
  }
})

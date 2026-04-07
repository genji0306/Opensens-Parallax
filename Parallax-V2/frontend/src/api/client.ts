import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import type { ApiResponse } from '@/types/api'

// ── Axios Instance ─────────────────────────────────────────────────────

const service: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 8_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

/** Short timeout for non-critical status checks */
export const STATUS_TIMEOUT = 4_000

/** Longer timeout for heavy pipeline operations (drafting, experiments, etc.) */
export const LONG_TIMEOUT = 300_000

export function createAbortController(): AbortController {
  return new AbortController()
}

// ── Debug log bridge ──────────────────────────────────────────────────
// Interceptors feed the debug store. The store is resolved lazily after
// Pinia is installed (first request always happens after app.mount()).

type DebugStoreApi = {
  logRequest(method: string, url: string): number
  resolveRequest(id: number, statusCode: number, size?: number): void
  rejectRequest(id: number, error: string, statusCode?: number): void
}

let _debug: DebugStoreApi | null | false = null // null = not resolved yet, false = failed

function getDebug(): DebugStoreApi | null {
  if (_debug === false) return null
  if (_debug) return _debug
  try {
    // Pinia is ready by the time the first request fires
    const { useDebugStore } = await_import_sync()
    _debug = useDebugStore()
    return _debug
  } catch {
    _debug = false
    return null
  }
}

// We store the module reference once the dynamic import resolves.
let _debugModule: typeof import('@/stores/debug') | null = null
// Kick off the import immediately — it will resolve before first network request.
import('@/stores/debug').then(m => { _debugModule = m }).catch(() => { _debug = false })

function await_import_sync(): typeof import('@/stores/debug') {
  if (!_debugModule) throw new Error('not ready')
  return _debugModule
}

// ── Interceptors ──────────────────────────────────────────────────────

interface ConfigWithDebug extends InternalAxiosRequestConfig {
  _debugId?: number
}

service.interceptors.request.use(
  (config: ConfigWithDebug) => {
    const d = getDebug()
    if (d) {
      config._debugId = d.logRequest(config.method || 'GET', config.url || '')
    }
    return config
  },
  (error) => Promise.reject(error),
)

service.interceptors.response.use(
  (response) => {
    const d = getDebug()
    const cfg = response.config as ConfigWithDebug
    if (d && cfg._debugId) {
      const size = typeof response.data === 'string'
        ? response.data.length
        : JSON.stringify(response.data).length
      d.resolveRequest(cfg._debugId, response.status, size)
    }

    // Business-level error
    const res = response.data
    if (!res.success && res.success !== undefined) {
      if (d && cfg._debugId) {
        d.rejectRequest(cfg._debugId, res.error || res.message || 'API error', response.status)
      }
      return Promise.reject(new Error(res.error || res.message || 'Error'))
    }
    return response
  },
  (error) => {
    const d = getDebug()
    const cfg = (error.config || {}) as ConfigWithDebug
    if (d && cfg._debugId) {
      let msg = 'Unknown error'
      if (error.code === 'ECONNABORTED') msg = 'Timeout'
      else if (error.code === 'ERR_NETWORK') msg = 'Network error'
      else if (error.code === 'ERR_CANCELED') msg = 'Canceled'
      else if (error.response) msg = `HTTP ${error.response.status}`
      else if (error.message) msg = error.message
      d.rejectRequest(cfg._debugId, msg, error.response?.status)
    }
    return Promise.reject(error)
  },
)

// ── Retry Helper ───────────────────────────────────────────────────────

export async function requestWithRetry<T>(
  requestFn: () => Promise<AxiosResponse<ApiResponse<T>>>,
  maxRetries = 3,
  delay = 1000,
): Promise<AxiosResponse<ApiResponse<T>>> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      if (i === maxRetries - 1) throw error
      await new Promise((resolve) => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
  throw new Error('Retry exhausted')
}

// ── Typed Helpers ──────────────────────────────────────────────────────

export async function apiGet<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const res = await service.get<ApiResponse<T>>(url, config)
  return res.data.data
}

export async function apiPost<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const res = await service.post<ApiResponse<T>>(url, data, config)
  return res.data.data
}

export default service

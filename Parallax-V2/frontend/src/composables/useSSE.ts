import { ref, watch, onUnmounted, type Ref } from 'vue'
import type { SSEEvent } from '@/types/api'

export type SSEStatus = 'idle' | 'connected' | 'error'

export interface UseSSEReturn<T> {
  data: Ref<T | null>
  status: Ref<SSEStatus>
  close: () => void
}

/**
 * Generic typed SSE composable.
 *
 * Connects to `url` when it becomes a non-null string, parses each `data:`
 * line as JSON of shape `SSEEvent<T>`, and exposes the latest parsed payload
 * via `data`. Automatically reconnects when `url` changes and cleans up on
 * component unmount.
 */
export function useSSE<T = unknown>(
  url: Ref<string | null>,
  options?: {
    onEvent?: (event: SSEEvent<T>) => void
    withCredentials?: boolean
  },
): UseSSEReturn<T> {
  const data = ref<T | null>(null) as Ref<T | null>
  const status = ref<SSEStatus>('idle')
  let source: EventSource | null = null

  function close(nextStatus: SSEStatus = 'idle'): void {
    if (source) {
      source.close()
      source = null
    }
    status.value = nextStatus
  }

  function connect(endpoint: string): void {
    close()

    source = new EventSource(endpoint, {
      withCredentials: options?.withCredentials ?? false,
    })

    source.onopen = () => {
      status.value = 'connected'
    }

    source.onmessage = (ev: MessageEvent) => {
      try {
        const parsed: SSEEvent<T> = JSON.parse(ev.data)
        const payload = parsed.payload ?? parsed.data ?? (parsed as unknown as T)
        data.value = payload
        options?.onEvent?.(parsed)
      } catch {
        // Non-JSON message — ignore silently
      }
    }

    source.onerror = () => {
      close('error')
    }
  }

  watch(
    url,
    (newUrl) => {
      if (newUrl) {
        connect(newUrl)
      } else {
        close()
      }
    },
    { immediate: true },
  )

  onUnmounted(close)

  return { data, status, close }
}

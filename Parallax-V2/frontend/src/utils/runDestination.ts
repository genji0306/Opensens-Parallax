import { classifyRunKind } from '@/utils/runKind'

export interface RunDestinationRoute {
  name: string
  params?: Record<string, string>
  query?: Record<string, string>
}

export type RunDestination =
  | { kind: 'route'; to: RunDestinationRoute }
  | { kind: 'external'; href: string }

interface ResolveRunDestinationInput {
  runId: string
  type?: string | null
  source?: string | null
  uploadId?: string | null
  reportBaseUrl?: string
}

function trimTrailingSlash(value: string): string {
  return value.endsWith('/') ? value.slice(0, -1) : value
}

export function resolveRunDestination(input: ResolveRunDestinationInput): RunDestination {
  const runKind = classifyRunKind({
    type: input.type,
    runId: input.runId,
    source: input.source,
  })

  if (runKind === 'paper') {
    return {
      kind: 'route',
      to: {
        name: 'paper-lab',
        query: { upload_id: input.uploadId ?? input.runId },
      },
    }
  }

  if (runKind === 'report') {
    const baseURL = trimTrailingSlash(input.reportBaseUrl ?? '')
    return {
      kind: 'external',
      href: `${baseURL}/api/research/report/${encodeURIComponent(input.runId)}/view?format=markdown`,
    }
  }

  if (runKind === 'debate_sim') {
    return {
      kind: 'route',
      to: {
        name: 'debate-analysis',
        params: { runId: input.runId },
      },
    }
  }

  return {
    kind: 'route',
    to: {
      name: 'project',
      params: { runId: input.runId },
    },
  }
}

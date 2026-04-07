export type RunKind = 'ais' | 'debate_sim' | 'paper' | 'report' | 'unknown'

interface RunKindInput {
  type?: string | null
  runId?: string | null
  source?: string | null
}

/**
 * Classify a run into a frontend behavior bucket so we don't call
 * AIS-only endpoints for non-AIS runs.
 */
export function classifyRunKind(input: RunKindInput): RunKind {
  const type = (input.type ?? '').toLowerCase().trim()
  const runId = (input.runId ?? '').trim()
  const source = (input.source ?? '').toLowerCase().trim()

  if (type === 'paper' || type === 'paper_rehab') return 'paper'
  if (type === 'report') return 'report'
  if (type === 'ais') return 'ais'
  if (type === 'debate') return 'debate_sim'

  if (runId.startsWith('ais_run_')) return 'ais'
  if (runId.startsWith('ossr_sim_') || runId.startsWith('sim_')) return 'debate_sim'

  // Platform-generated runs are typically AIS if no stronger signal exists.
  if (source === 'platform' && runId.length > 0) return 'ais'

  return 'unknown'
}

export function isAisRunKind(kind: RunKind): boolean {
  return kind === 'ais'
}

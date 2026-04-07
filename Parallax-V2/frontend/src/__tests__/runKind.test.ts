import { describe, expect, it } from 'vitest'
import { classifyRunKind } from '@/utils/runKind'
import { resolveRunDestination } from '@/utils/runDestination'

describe('runKind classification', () => {
  it('classifies by explicit type', () => {
    expect(classifyRunKind({ type: 'ais', runId: 'x' })).toBe('ais')
    expect(classifyRunKind({ type: 'paper', runId: 'x' })).toBe('paper')
    expect(classifyRunKind({ type: 'report', runId: 'x' })).toBe('report')
    expect(classifyRunKind({ type: 'debate', runId: 'x' })).toBe('debate_sim')
  })

  it('classifies by run id prefixes', () => {
    expect(classifyRunKind({ runId: 'ais_run_123' })).toBe('ais')
    expect(classifyRunKind({ runId: 'ossr_sim_123' })).toBe('debate_sim')
    expect(classifyRunKind({ runId: 'sim_123' })).toBe('debate_sim')
  })

  it('falls back to platform source for untyped ids', () => {
    expect(classifyRunKind({ runId: 'legacy_001', source: 'platform' })).toBe('ais')
  })

  it('returns unknown for unmatched runs', () => {
    expect(classifyRunKind({ runId: 'abc_123', source: 'cli' })).toBe('unknown')
  })
})

describe('run destination resolution', () => {
  it('routes paper runs to paper-lab', () => {
    const destination = resolveRunDestination({
      runId: 'upload_123',
      type: 'paper',
      uploadId: 'upload_123',
    })
    expect(destination.kind).toBe('route')
    if (destination.kind === 'route') {
      expect(destination.to.name).toBe('paper-lab')
      expect(destination.to.query).toEqual({ upload_id: 'upload_123' })
    }
  })

  it('builds report external URL', () => {
    const destination = resolveRunDestination({
      runId: 'report_123',
      type: 'report',
      reportBaseUrl: 'http://localhost:5002/',
    })
    expect(destination.kind).toBe('external')
    if (destination.kind === 'external') {
      expect(destination.href).toBe('http://localhost:5002/api/research/report/report_123/view?format=markdown')
    }
  })

  it('routes debate simulations to debate-analysis route', () => {
    const destination = resolveRunDestination({
      runId: 'ossr_sim_123',
      type: 'debate',
    })
    expect(destination.kind).toBe('route')
    if (destination.kind === 'route') {
      expect(destination.to.name).toBe('debate-analysis')
      expect(destination.to.params).toEqual({ runId: 'ossr_sim_123' })
    }
  })
})
